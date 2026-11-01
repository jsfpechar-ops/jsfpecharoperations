package payments

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const onboardTestKey = "sk_test_onboarder_secret_0123"

type stripeReq struct {
	Method, Path, Auth, Version, ContentType, Body string
}

// stripeFake records every request and answers like Stripe. Fields are guarded
// by mu because the server runs on its own goroutine.
type stripeFake struct {
	mu      sync.Mutex
	srv     *httptest.Server
	reqs    []stripeReq
	status  int
	account map[string]any
}

func newStripeFake(t *testing.T) *stripeFake {
	t.Helper()
	f := &stripeFake{account: map[string]any{
		"id": "acct_test1", "charges_enabled": false, "payouts_enabled": false,
		"requirements": map[string]any{},
	}}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		f.mu.Lock()
		defer f.mu.Unlock()
		f.reqs = append(f.reqs, stripeReq{r.Method, r.URL.Path, r.Header.Get("Authorization"),
			r.Header.Get("Stripe-Version"), r.Header.Get("Content-Type"), string(raw)})
		w.Header().Set("Content-Type", "application/json")
		if f.status != 0 {
			w.WriteHeader(f.status)
			_, _ = w.Write([]byte(`{"error":{"message":"Invalid value","code":"parameter_invalid_empty"}}`))
			return
		}
		switch r.URL.Path {
		case "/v2/core/accounts":
			_ = json.NewEncoder(w).Encode(map[string]any{"id": "acct_test1"})
		case "/v1/account_links":
			_ = json.NewEncoder(w).Encode(map[string]any{"url": "https://connect.stripe.test/setup/abc"})
		case "/v1/accounts/acct_test1":
			_ = json.NewEncoder(w).Encode(f.account)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func (f *stripeFake) requests() []stripeReq {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]stripeReq(nil), f.reqs...)
}

func (f *stripeFake) set(status int, account map[string]any) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.status = status
	if account != nil {
		f.account = account
	}
}

func onboardEnv(mode, key string, extra map[string]string) func(string) string {
	env := map[string]string{"UBYHOST_STRIPE_MODE": mode, "UBYHOST_STRIPE_SECRET_KEY": key}
	for k, v := range extra {
		env[k] = v
	}
	return func(k string) string { return env[k] }
}

func newOnboarder(pool *pgxpool.Pool, getenv func(string) string, f *stripeFake) *StripeOnboarder {
	ob := NewStripeOnboarder(pool, getenv, func() time.Time { return testNow })
	ob.APIBase = f.srv.URL
	return ob
}

func onboardInt(t *testing.T, pool *pgxpool.Pool, q string, args ...any) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// onboardSeed: host 1 with a company entity and no contact email; host 3 with
// no legal entity.
func onboardSeed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES
			(1, 'host', 'x', NOW(), 'host', 1, 0),
			(3, 'nolegal', 'x', NOW(), 'host', 1, 0)`,
		`INSERT INTO legal_entity (id, owner_user_id, name, business_type, created_at, contact_email, vat_status, invoice_due_days)
			VALUES (1, 1, 'Test Company s.r.o.', 'company', '2026-01-01T00:00:00+00:00', NULL, 'none', 14)`,
	}
	for _, q := range stmts {
		if _, err := pool.Exec(context.Background(), q); err != nil {
			t.Fatal(err)
		}
	}
}

func TestStripeOnboarderOffMakesNoCall(t *testing.T) {
	pool := testPool(t)
	onboardSeed(t, pool)
	fake := newStripeFake(t)
	cases := map[string]func(string) string{
		"mode off":  onboardEnv("off", onboardTestKey, nil),
		"empty key": onboardEnv("test", "  ", nil),
	}
	for name, env := range cases {
		ob := newOnboarder(pool, env, fake)
		if _, err := ob.OnboardingLink(context.Background(), 1, "https://ubyhost.example"); !errors.Is(err, ErrStripeOff) {
			t.Errorf("%s: got %v, want ErrStripeOff", name, err)
		}
	}
	if n := len(fake.requests()); n != 0 {
		t.Errorf("requests = %d, want 0", n)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM lock_api_usage`); n != 0 {
		t.Errorf("usage rows = %d, want 0", n)
	}
}

func TestStripeOnboarderNoEntity(t *testing.T) {
	pool := testPool(t)
	onboardSeed(t, pool)
	fake := newStripeFake(t)
	ob := newOnboarder(pool, onboardEnv("test", onboardTestKey, nil), fake)
	if _, err := ob.OnboardingLink(context.Background(), 3, "https://ubyhost.example"); !errors.Is(err, ErrNoEntity) {
		t.Fatalf("got %v, want ErrNoEntity", err)
	}
	if n := len(fake.requests()); n != 0 {
		t.Errorf("requests = %d, want 0", n)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM lock_api_usage`); n != 0 {
		t.Errorf("usage rows = %d, want 0", n)
	}
}

func TestStripeOnboarderLinksAndReturn(t *testing.T) {
	pool := testPool(t)
	onboardSeed(t, pool)
	ctx := context.Background()
	const base = "https://ubyhost.example"
	fake := newStripeFake(t)
	ob := newOnboarder(pool, onboardEnv("test", onboardTestKey, nil), fake)

	// Return before any account exists.
	if _, err := ob.HandleReturn(ctx, 3); !errors.Is(err, ErrNoAccount) {
		t.Errorf("return without row: got %v, want ErrNoAccount", err)
	}

	// First link: creates the account, then the link.
	link, err := ob.OnboardingLink(ctx, 1, base)
	if err != nil {
		t.Fatal(err)
	}
	if link != "https://connect.stripe.test/setup/abc" {
		t.Errorf("link = %q", link)
	}
	reqs := fake.requests()
	if len(reqs) != 2 {
		t.Fatalf("requests = %d, want 2", len(reqs))
	}
	create := reqs[0]
	if create.Method != http.MethodPost || create.Path != "/v2/core/accounts" ||
		create.ContentType != "application/json" {
		t.Errorf("create request: %+v", create)
	}
	if create.Auth != "Bearer "+onboardTestKey || create.Version != "2026-09-30.endive" {
		t.Errorf("create headers: auth/version wrong")
	}
	var got map[string]any
	if err := json.Unmarshal([]byte(create.Body), &got); err != nil {
		t.Fatal(err)
	}
	want := map[string]any{
		"contact_email": nil,
		"display_name":  "Test Company s.r.o.",
		"dashboard":     "full",
		"identity": map[string]any{
			"country":          "CZ",
			"entity_type":      "company",
			"business_details": map[string]any{"registered_name": "Test Company s.r.o."},
		},
		"configuration": map[string]any{"merchant": map[string]any{
			"capabilities": map[string]any{"card_payments": map[string]any{"requested": true}},
		}},
		"defaults": map[string]any{
			"currency": "czk",
			"responsibilities": map[string]any{
				"fees_collector":   "stripe",
				"losses_collector": "stripe",
			},
		},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("v2 body = %v, want %v", got, want)
	}
	linkReq := reqs[1]
	if linkReq.Path != "/v1/account_links" || linkReq.ContentType != "application/x-www-form-urlencoded" {
		t.Errorf("link request: %+v", linkReq)
	}
	form, _ := url.ParseQuery(linkReq.Body)
	if form.Get("account") != "acct_test1" || form.Get("type") != "account_onboarding" ||
		form.Get("refresh_url") != base+"/payments/connect/start" ||
		form.Get("return_url") != base+"/payments/connect/return" {
		t.Errorf("link form: %v", form)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM stripe_account WHERE owner_user_id = 1 AND stripe_account_id = 'acct_test1' AND onboarding_state = 'pending'`); n != 1 {
		t.Errorf("stripe_account rows = %d, want 1", n)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'stripe_account_created' AND owner_user_id = 1`); n != 1 {
		t.Errorf("stripe_account_created audit = %d, want 1", n)
	}
	if n := onboardInt(t, pool, `SELECT calls FROM lock_api_usage WHERE month = '2026-09' AND provider = 'stripe'`); n != 2 {
		t.Errorf("calls after first link = %d, want 2", n)
	}

	// Second link: reuses the row, one more call.
	if _, err := ob.OnboardingLink(ctx, 1, base); err != nil {
		t.Fatal(err)
	}
	if n := len(fake.requests()); n != 3 {
		t.Errorf("requests after second link = %d, want 3", n)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM stripe_account WHERE owner_user_id = 1`); n != 1 {
		t.Errorf("stripe_account rows after reuse = %d, want 1", n)
	}

	// Budget at the limit: off before any request, and no count.
	capped := newOnboarder(pool, onboardEnv("test", onboardTestKey, map[string]string{
		"UBYHOST_STRIPE_MONTHLY_API_CALLS": "3",
	}), fake)
	if _, err := capped.OnboardingLink(ctx, 1, base); !errors.Is(err, ErrStripeOff) {
		t.Errorf("at budget: got %v, want ErrStripeOff", err)
	}
	if n := len(fake.requests()); n != 3 {
		t.Errorf("requests at budget = %d, want 3", n)
	}
	if n := onboardInt(t, pool, `SELECT calls FROM lock_api_usage WHERE month = '2026-09' AND provider = 'stripe'`); n != 3 {
		t.Errorf("calls at budget = %d, want 3", n)
	}

	// Return with a row: mirrors the account as complete.
	fake.set(0, map[string]any{
		"id": "acct_test1", "charges_enabled": true, "payouts_enabled": true, "requirements": map[string]any{},
	})
	if _, err := ob.HandleReturn(ctx, 1); err != nil {
		t.Fatal(err)
	}
	last := fake.requests()[3]
	if last.Method != http.MethodGet || last.Path != "/v1/accounts/acct_test1" {
		t.Errorf("return request: %+v", last)
	}
	var state string
	if err := pool.QueryRow(ctx, `SELECT onboarding_state FROM stripe_account WHERE owner_user_id = 1`).Scan(&state); err != nil {
		t.Fatal(err)
	}
	if state != "complete" {
		t.Errorf("state after return = %q, want complete", state)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'stripe_account_state' AND owner_user_id = 1`); n != 1 {
		t.Errorf("stripe_account_state audit = %d, want 1", n)
	}

	// A Stripe 400 is an error that does not carry the key.
	fake.set(http.StatusBadRequest, nil)
	_, err = ob.OnboardingLink(ctx, 1, base)
	if err == nil {
		t.Fatal("400: want error")
	}
	if strings.Contains(err.Error(), onboardTestKey) || !strings.Contains(err.Error(), "400") {
		t.Errorf("400 error text: %q", err.Error())
	}
}
