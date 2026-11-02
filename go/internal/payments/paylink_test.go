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

type paylinkReq struct {
	Method, Path, Account, Body string
}

// paylinkFake records every request and answers like Stripe for payment links.
type paylinkFake struct {
	mu      sync.Mutex
	srv     *httptest.Server
	reqs    []paylinkReq
	status  int
	links   map[string]map[string]any
	created map[string]any
}

func newPaylinkFake(t *testing.T) *paylinkFake {
	t.Helper()
	f := &paylinkFake{
		links:   map[string]map[string]any{},
		created: map[string]any{"id": "plink_1", "url": "https://buy.stripe.test/plink_1"},
	}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		f.mu.Lock()
		defer f.mu.Unlock()
		f.reqs = append(f.reqs, paylinkReq{r.Method, r.URL.Path, r.Header.Get("Stripe-Account"), string(raw)})
		w.Header().Set("Content-Type", "application/json")
		if f.status != 0 {
			w.WriteHeader(f.status)
			_, _ = w.Write([]byte(`{"error":{"message":"Invalid value","code":"parameter_invalid_empty"}}`))
			return
		}
		var out map[string]any
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/v1/payment_links":
			out = f.created
		case r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/v1/payment_links/"):
			out = f.links[strings.TrimPrefix(r.URL.Path, "/v1/payment_links/")]
		}
		if out == nil {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		_ = json.NewEncoder(w).Encode(out)
	}))
	t.Cleanup(f.srv.Close)
	return f
}

// configure changes the fake's answers under its lock.
func (f *paylinkFake) configure(fn func(f *paylinkFake)) {
	f.mu.Lock()
	defer f.mu.Unlock()
	fn(f)
}

func (f *paylinkFake) requests() []paylinkReq {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]paylinkReq(nil), f.reqs...)
}

func paylinkOnboarder(pool *pgxpool.Pool, env func(string) string, f *paylinkFake) *StripeOnboarder {
	ob := NewStripeOnboarder(pool, env, func() time.Time { return testNow })
	ob.APIBase = f.srv.URL
	return ob
}

// paylinkSeed: onboardSeed (hosts 1 and 3), host 4 with a pending account,
// host 1 with a complete test account; requests 1 (card, host 1), 2 (qr, host 1),
// 3 (card, host 3, no account), 4 (card, host 4, pending).
func paylinkSeed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	onboardSeed(t, pool)
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES
			(4, 'pending', 'x', NOW(), 'host', 1, 0)`,
		`INSERT INTO stripe_account (owner_user_id, stripe_account_id, mode, onboarding_state, created_at, updated_at) VALUES
			(1, 'acct_paylink1', 'test', 'complete', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'),
			(4, 'acct_pending4', 'test', 'pending', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO payment_request (id, owner_user_id, reason, amount_czk, rail, status, expires_at, created_at, updated_at) VALUES
			(1, 1, 'repair', 250, 'card', 'sent', '2026-12-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00'),
			(2, 1, 'cleaning', 90, 'qr', 'sent', '2026-12-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00'),
			(3, 3, 'damage', 500, 'card', 'sent', '2026-12-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00'),
			(4, 4, 'late_checkout', 120, 'card', 'sent', '2026-12-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00')`,
	}
	for _, q := range stmts {
		if _, err := pool.Exec(context.Background(), q); err != nil {
			t.Fatal(err)
		}
	}
}

func paylinkStored(t *testing.T, pool *pgxpool.Pool, id int64) string {
	t.Helper()
	var s string
	if err := pool.QueryRow(context.Background(),
		`SELECT COALESCE(stripe_payment_link_id, '') FROM payment_request WHERE id = $1`, id).Scan(&s); err != nil {
		t.Fatal(err)
	}
	return s
}

func TestSendPaymentLinkSkipsWithoutCall(t *testing.T) {
	pool := testPool(t)
	paylinkSeed(t, pool)
	fake := newPaylinkFake(t)
	ob := paylinkOnboarder(pool, onboardEnv("test", onboardTestKey, nil), fake)
	ctx := context.Background()
	if u, err := ob.SendPaymentLink(ctx, 999); u != "" || err != nil {
		t.Errorf("missing request: got %q, %v, want \"\", nil", u, err)
	}
	if _, err := ob.SendPaymentLink(ctx, 2); err == nil {
		t.Error("qr rail: want an error")
	}
	if u, err := ob.SendPaymentLink(ctx, 3); u != "" || err != nil {
		t.Errorf("no account: got %q, %v, want \"\", nil", u, err)
	}
	if u, err := ob.SendPaymentLink(ctx, 4); u != "" || err != nil {
		t.Errorf("pending account: got %q, %v, want \"\", nil", u, err)
	}
	if n := len(fake.requests()); n != 0 {
		t.Errorf("requests = %d, want 0", n)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM lock_api_usage`); n != 0 {
		t.Errorf("usage rows = %d, want 0", n)
	}
}

func TestSendPaymentLinkStripeOff(t *testing.T) {
	pool := testPool(t)
	paylinkSeed(t, pool)
	fake := newPaylinkFake(t)
	ctx := context.Background()
	// Key missing in test mode: the guard refuses before any call.
	ob := paylinkOnboarder(pool, onboardEnv("test", "  ", nil), fake)
	if _, err := ob.SendPaymentLink(ctx, 1); !errors.Is(err, ErrStripeOff) {
		t.Errorf("no key: got %v, want ErrStripeOff", err)
	}
	// Mode off finds no account row for mode 'off' (Python order), so no error.
	off := paylinkOnboarder(pool, onboardEnv("off", onboardTestKey, nil), fake)
	if u, err := off.SendPaymentLink(ctx, 1); u != "" || err != nil {
		t.Errorf("mode off: got %q, %v, want \"\", nil", u, err)
	}
	if n := len(fake.requests()); n != 0 {
		t.Errorf("requests = %d, want 0", n)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM lock_api_usage`); n != 0 {
		t.Errorf("usage rows = %d, want 0", n)
	}
}

func TestSendPaymentLinkFresh(t *testing.T) {
	pool := testPool(t)
	paylinkSeed(t, pool)
	fake := newPaylinkFake(t)
	ob := paylinkOnboarder(pool, onboardEnv("test", onboardTestKey, nil), fake)
	u, err := ob.SendPaymentLink(context.Background(), 1)
	if err != nil || u != "https://buy.stripe.test/plink_1" {
		t.Fatalf("got %q, %v, want the created url", u, err)
	}
	reqs := fake.requests()
	if len(reqs) != 1 || reqs[0].Method != "POST" || reqs[0].Path != "/v1/payment_links" {
		t.Fatalf("requests = %+v, want one POST /v1/payment_links", reqs)
	}
	if reqs[0].Account != "acct_paylink1" {
		t.Errorf("Stripe-Account = %q, want acct_paylink1", reqs[0].Account)
	}
	got, err := url.ParseQuery(reqs[0].Body)
	if err != nil {
		t.Fatal(err)
	}
	want := url.Values{
		"line_items[0][quantity]":                           {"1"},
		"line_items[0][price_data][currency]":               {"czk"},
		"line_items[0][price_data][unit_amount]":            {"25000"},
		"line_items[0][price_data][product_data][name]":     {"Příspěvek na opravu (žádost č. 1)"},
		"restrictions[completed_sessions][limit]":           {"1"},
		"metadata[payment_request_id]":                      {"1"},
		"payment_intent_data[metadata][payment_request_id]": {"1"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("form = %v, want %v", got, want)
	}
	if s := paylinkStored(t, pool, 1); s != "plink_1" {
		t.Errorf("stored link = %q, want plink_1", s)
	}
	if n := onboardInt(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'payment_link_created'`); n != 1 {
		t.Errorf("audit rows = %d, want 1", n)
	}
	if n := onboardInt(t, pool, `SELECT COALESCE(SUM(calls), 0) FROM lock_api_usage`); n != 1 {
		t.Errorf("calls = %d, want 1", n)
	}
}

func TestSendPaymentLinkResend(t *testing.T) {
	pool := testPool(t)
	paylinkSeed(t, pool)
	fake := newPaylinkFake(t)
	ob := paylinkOnboarder(pool, onboardEnv("test", onboardTestKey, nil), fake)
	ctx := context.Background()
	if _, err := ob.SendPaymentLink(ctx, 1); err != nil {
		t.Fatal(err)
	}
	// Active stored link: one GET, no POST, the same url, one more count.
	fake.configure(func(f *paylinkFake) {
		f.links["plink_1"] = map[string]any{"id": "plink_1", "url": "https://buy.stripe.test/plink_1", "active": true}
	})
	before := len(fake.requests())
	u, err := ob.SendPaymentLink(ctx, 1)
	if err != nil || u != "https://buy.stripe.test/plink_1" {
		t.Fatalf("active resend: got %q, %v", u, err)
	}
	reqs := fake.requests()[before:]
	if len(reqs) != 1 || reqs[0].Method != "GET" || reqs[0].Path != "/v1/payment_links/plink_1" || reqs[0].Account != "acct_paylink1" {
		t.Errorf("active resend requests = %+v, want one GET of plink_1", reqs)
	}
	if n := onboardInt(t, pool, `SELECT COALESCE(SUM(calls), 0) FROM lock_api_usage`); n != 2 {
		t.Errorf("calls after active resend = %d, want 2", n)
	}
	// Inactive stored link: GET then POST, the new id is stored, one count.
	fake.configure(func(f *paylinkFake) {
		f.links["plink_1"] = map[string]any{"id": "plink_1", "url": "https://buy.stripe.test/plink_1", "active": false}
		f.created = map[string]any{"id": "plink_2", "url": "https://buy.stripe.test/plink_2"}
	})
	before = len(fake.requests())
	u, err = ob.SendPaymentLink(ctx, 1)
	if err != nil || u != "https://buy.stripe.test/plink_2" {
		t.Fatalf("inactive resend: got %q, %v", u, err)
	}
	reqs = fake.requests()[before:]
	if len(reqs) != 2 || reqs[0].Method != "GET" || reqs[1].Method != "POST" {
		t.Errorf("inactive resend requests = %+v, want GET then POST", reqs)
	}
	if s := paylinkStored(t, pool, 1); s != "plink_2" {
		t.Errorf("stored link = %q, want plink_2", s)
	}
	if n := onboardInt(t, pool, `SELECT COALESCE(SUM(calls), 0) FROM lock_api_usage`); n != 3 {
		t.Errorf("calls after inactive resend = %d, want 3", n)
	}
}

func TestSendPaymentLinkStripeErrorHidesKey(t *testing.T) {
	pool := testPool(t)
	paylinkSeed(t, pool)
	fake := newPaylinkFake(t)
	fake.configure(func(f *paylinkFake) { f.status = http.StatusBadRequest })
	ob := paylinkOnboarder(pool, onboardEnv("test", onboardTestKey, nil), fake)
	u, err := ob.SendPaymentLink(context.Background(), 1)
	if err == nil || u != "" {
		t.Fatalf("got %q, %v, want an error and no url", u, err)
	}
	if strings.Contains(err.Error(), onboardTestKey) {
		t.Errorf("error text names the secret key: %v", err)
	}
	if s := paylinkStored(t, pool, 1); s != "" {
		t.Errorf("stored link = %q after a failed send, want none", s)
	}
}
