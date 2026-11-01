package payments

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

var testNow = time.Unix(1790000000, 0)

func signFor(secret string, ts int64, body []byte) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(strconv.FormatInt(ts, 10) + "."))
	m.Write(body)
	return hex.EncodeToString(m.Sum(nil))
}

func TestVerifySignature(t *testing.T) {
	body := []byte(`{"id":"evt_1","type":"x"}`)
	const secret = "whsec_test"
	ts := testNow.Unix()
	good := signFor(secret, ts, body)
	cases := []struct {
		name   string
		header string
		secret string
		now    time.Time
		ok     bool
	}{
		{"valid", fmt.Sprintf("t=%d,v1=%s", ts, good), secret, testNow, true},
		{"two v1 one matching", fmt.Sprintf("t=%d,v1=deadbeef,v1=%s", ts, good), secret, testNow, true},
		{"wrong secret", fmt.Sprintf("t=%d,v1=%s", ts, good), "whsec_other", testNow, false},
		{"old timestamp 301 s", fmt.Sprintf("t=%d,v1=%s", ts-301, signFor(secret, ts-301, body)), secret, testNow, false},
		{"missing t", fmt.Sprintf("v1=%s", good), secret, testNow, false},
		{"no v1", fmt.Sprintf("t=%d", ts), secret, testNow, false},
	}
	for _, c := range cases {
		err := verifySignature(body, c.header, c.secret, c.now)
		if (err == nil) != c.ok {
			t.Errorf("%s: got %v, want ok=%v", c.name, err, c.ok)
		}
	}
}

func TestOnboardingState(t *testing.T) {
	cases := []struct {
		want string
		acct map[string]any
	}{
		{"disabled", map[string]any{"requirements": map[string]any{"disabled_reason": "under_review"}}},
		{"rejected", map[string]any{"requirements": map[string]any{"disabled_reason": "rejected.fraud"}}},
		{"rejected", map[string]any{"requirements": map[string]any{"errors": []any{map[string]any{"code": "verification_rejected_fraud"}}}}},
		{"action_required", map[string]any{"requirements": map[string]any{"disabled_reason": "requirements.past_due", "past_due": []any{"x"}}}},
		{"pending", map[string]any{"disabled": true}},
		{"complete", map[string]any{"charges_enabled": true, "requirements": map[string]any{}}},
		{"action_required", map[string]any{"charges_enabled": true, "requirements": map[string]any{"currently_due": []any{"x"}}}},
		{"pending", map[string]any{"requirements": map[string]any{}}},
	}
	for _, c := range cases {
		if got := onboardingState(c.acct); got != c.want {
			t.Errorf("state %s: got %s", c.want, got)
		}
	}
}

func TestRequirementsJSON(t *testing.T) {
	req := map[string]any{
		"currently_due":   []any{"business_profile.url", "external_account \u00fc"},
		"past_due":        []any{},
		"eventually_due":  []any{"tos_acceptance.date"},
		"disabled_reason": "requirements.pending_verification",
		"errors":          []any{},
	}
	// Python: json.dumps of the same subset, run once with the function copied from stripe_connect.py.
	want := `{"currently_due": ["business_profile.url", "external_account \u00fc"], "eventually_due": ["tos_acceptance.date"], "disabled_reason": "requirements.pending_verification"}`
	got := requirementsJSON(req)
	if got == nil || *got != want {
		t.Fatalf("requirementsJSON: got %q, want %q", deref(got), want)
	}
	if requirementsJSON(map[string]any{"past_due": []any{}}) != nil {
		t.Errorf("empty subset must be NULL")
	}
}

func deref(s *string) string {
	if s == nil {
		return "<nil>"
	}
	return *s
}

// webhookEnv returns a getenv for the handler under test.
func webhookEnv(mode, secret string) func(string) string {
	return func(k string) string {
		switch k {
		case "UBYHOST_STRIPE_MODE":
			return mode
		case "UBYHOST_STRIPE_WEBHOOK_SECRET":
			return secret
		}
		return ""
	}
}

func post(t *testing.T, h http.HandlerFunc, body []byte, sig string) int {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/webhooks/stripe", strings.NewReader(string(body)))
	req.RemoteAddr = "192.0.2.1:1234"
	if sig != "" {
		req.Header.Set("Stripe-Signature", sig)
	}
	rec := httptest.NewRecorder()
	h(rec, req)
	return rec.Code
}

func signedPost(t *testing.T, h http.HandlerFunc, body []byte) int {
	return post(t, h, body, fmt.Sprintf("t=%d,v1=%s", testNow.Unix(), signFor("whsec_test", testNow.Unix(), body)))
}

func count(t *testing.T, pool *pgxpool.Pool, q string, args ...any) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func containsDetail(details []string, want string) bool {
	for _, d := range details {
		if d == want {
			return true
		}
	}
	return false
}

func seedHost(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	const ts = "2026-01-01T00:00:00+00:00"
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at)
		VALUES (1, 'host', 'x', '`+ts+`')`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO stripe_account (owner_user_id, stripe_account_id, mode,
		created_at, updated_at) VALUES (1, 'acct_1', 'test', '`+ts+`', '`+ts+`')`); err != nil {
		t.Fatal(err)
	}
}

func seedRequest(t *testing.T, pool *pgxpool.Pool, id int, status, link string) {
	t.Helper()
	const ts = "2026-10-01T00:00:00+00:00"
	if _, err := pool.Exec(context.Background(), `INSERT INTO payment_request (id, owner_user_id, reason,
		amount_czk, rail, status, expires_at, created_at, updated_at, stripe_payment_link_id)
		VALUES ($1, 1, 'custom', 100, 'card', $2, '2026-12-31', '`+ts+`', '`+ts+`', $3)`, id, status, link); err != nil {
		t.Fatal(err)
	}
}

func TestWebhookDatabase(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	mode := func(m, s string) http.HandlerFunc {
		return WebhookHandler(pool, webhookEnv(m, s), func() time.Time { return testNow })
	}

	// Mode off: 200 ignored, no event row.
	if got := signedPost(t, mode("off", ""), []byte(`{"id":"evt_off","type":"x"}`)); got != 200 {
		t.Errorf("mode off: %d", got)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event`); n != 0 {
		t.Errorf("mode off wrote %d event rows", n)
	}
	// Mode on without secret: 500.
	if got := signedPost(t, mode("test", ""), []byte(`{"id":"evt_x","type":"x"}`)); got != 500 {
		t.Errorf("no secret: %d", got)
	}
	// Bad signature: 400.
	if got := post(t, mode("test", "whsec_test"), []byte(`{"id":"evt_bad"}`), "t=1,v1=00"); got != 400 {
		t.Errorf("bad signature: %d", got)
	}

	// account.updated: mirrors once, audits once; replay adds nothing.
	acct := []byte(`{"id":"evt_acct","type":"account.updated","data":{"object":{"id":"acct_1",` +
		`"charges_enabled":true,"payouts_enabled":true,"requirements":{"currently_due":[]}}}}`)
	h := mode("test", "whsec_test")
	if got := signedPost(t, h, acct); got != 200 {
		t.Fatalf("account.updated: %d", got)
	}
	if got := signedPost(t, h, acct); got != 200 {
		t.Fatalf("replay: %d", got)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_acct'`); n != 1 {
		t.Errorf("replay event rows: %d", n)
	}
	if n := len(auditDetails(t, pool, "stripe_account_state")); n != 1 {
		t.Errorf("account audits after replay: %d", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_account WHERE onboarding_state = 'complete'`); n != 1 {
		t.Errorf("account not mirrored to complete")
	}
	// Same state again under a new event id, one minute later, with new
	// requirements: the row is updated (requirements_json, updated_at), no audit.
	later := testNow.Add(time.Minute)
	again := []byte(`{"id":"evt_acct2","type":"account.updated","data":{"object":{"id":"acct_1",` +
		`"charges_enabled":true,"payouts_enabled":true,"requirements":{"currently_due":[],"eventually_due":["tos_acceptance.date"]}}}}`)
	later2 := WebhookHandler(pool, webhookEnv("test", "whsec_test"), func() time.Time { return later })
	if got := post(t, later2, again, fmt.Sprintf("t=%d,v1=%s", testNow.Unix(), signFor("whsec_test", testNow.Unix(), again))); got != 200 {
		t.Fatalf("same state again: %d", got)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_account WHERE requirements_json = '{"eventually_due": ["tos_acceptance.date"]}' AND updated_at = $1`, stampAt(later)); n != 1 {
		t.Errorf("same state not mirrored (requirements_json or updated_at)")
	}
	if n := len(auditDetails(t, pool, "stripe_account_state")); n != 1 {
		t.Errorf("same state audited again: %d", n)
	}

	// checkout.session.completed with payment_status paid, from draft: sent,
	// paid, then the paid audit.
	seedRequest(t, pool, 1, "draft", "plink_1")
	paid := []byte(`{"id":"evt_paid","type":"checkout.session.completed","data":{"object":{"payment_status":"paid","payment_link":"plink_1"}}}`)
	if got := signedPost(t, h, paid); got != 200 {
		t.Fatalf("paid: %d", got)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 1 AND status = 'paid' AND paid_at IS NOT NULL`); n != 1 {
		t.Errorf("request not paid with paid_at")
	}
	if n := len(auditDetails(t, pool, "payment_request_status")); n != 2 {
		t.Errorf("status audits: %d", n)
	}
	if d := auditDetails(t, pool, "payment_request_paid"); len(d) != 1 || d[0] != "id=1 via=stripe_webhook amount=100 CZK" {
		t.Errorf("paid audit: %v", d)
	}
	// Already paid: untouched.
	signedPost(t, h, []byte(`{"id":"evt_paid2","type":"checkout.session.completed","data":{"object":{"payment_status":"paid","payment_link":"plink_1"}}}`))
	if n := len(auditDetails(t, pool, "payment_request_paid")); n != 1 {
		t.Errorf("already paid was audited again")
	}

	// Old type payment_link.paid is recorded only, even with an object.id.
	seedRequest(t, pool, 2, "sent", "plink_2")
	signedPost(t, h, []byte(`{"id":"evt_old","type":"payment_link.paid","data":{"object":{"payment_status":"paid","id":"plink_2"}}}`))
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 2 AND status = 'sent'`); n != 1 {
		t.Errorf("payment_link.paid changed the request")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_old'`); n != 1 {
		t.Errorf("payment_link.paid not recorded")
	}

	// payment_status unpaid writes nothing.
	seedRequest(t, pool, 3, "sent", "plink_3")
	signedPost(t, h, []byte(`{"id":"evt_unpaid","type":"checkout.session.completed","data":{"object":{"payment_status":"unpaid","payment_link":"plink_3"}}}`))
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 3 AND status = 'sent'`); n != 1 {
		t.Errorf("unpaid checkout changed the request")
	}

	// A bank method settles later: async_payment_succeeded pays.
	seedRequest(t, pool, 4, "sent", "plink_4")
	signedPost(t, h, []byte(`{"id":"evt_async","type":"checkout.session.async_payment_succeeded","data":{"object":{"payment_status":"paid","payment_link":"plink_4"}}}`))
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 4 AND status = 'paid'`); n != 1 {
		t.Errorf("async_payment_succeeded did not pay")
	}

	// An expired row paid late: expired->paid audit, then the paid audit.
	seedRequest(t, pool, 5, "expired", "plink_5")
	signedPost(t, h, []byte(`{"id":"evt_late","type":"checkout.session.completed","data":{"object":{"payment_status":"paid","payment_link":"plink_5"}}}`))
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 5 AND status = 'paid' AND paid_at IS NOT NULL`); n != 1 {
		t.Errorf("expired request not paid late")
	}
	if d := auditDetails(t, pool, "payment_request_status"); !containsDetail(d, "id=5 expired->paid") {
		t.Errorf("late payment status audit missing: %v", d)
	}
	if d := auditDetails(t, pool, "payment_request_paid"); !containsDetail(d, "id=5 via=stripe_webhook amount=100 CZK") {
		t.Errorf("late payment paid audit missing: %v", d)
	}
	// Unknown type: recorded only.
	signedPost(t, h, []byte(`{"id":"evt_other","type":"customer.created","data":{"object":{}}}`))
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_other'`); n != 1 {
		t.Errorf("unknown type not recorded")
	}
}

func TestWebhookRateLimit(t *testing.T) {
	pool := testPool(t)
	h := WebhookHandler(pool, webhookEnv("off", ""), func() time.Time { return testNow })
	for i := 0; i < webhookLimit; i++ {
		if got := post(t, h, []byte(`{}`), ""); got != 200 {
			t.Fatalf("request %d: %d", i+1, got)
		}
	}
	if got := post(t, h, []byte(`{}`), ""); got != 429 {
		t.Errorf("601st request: %d, want 429", got)
	}
}
