package billingweb

// Test helpers for the handler tests (brief 1555 on): a seeded database, a
// signed session cookie and a CSRF pair. Nothing here reaches a network.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const testSecret = "billingweb-test-secret-not-for-real-use"
const testVersion = "test-accepted"

// testNow is the fixed server clock of the handler tests: 2026-11-13 12:00 UTC.
var testNow = time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)

func testEnvMap(extra map[string]string) func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_TERMS_VERSION":   testVersion,
		"UBYHOST_PRIVACY_VERSION": testVersion,
		"UBYHOST_DPA_VERSION":     testVersion,
		"UBYHOST_BILLING_ENABLED": "1",
	}
	for k, v := range extra {
		env[k] = v
	}
	return func(k string) string { return env[k] }
}

// testUser seeds user_account rows 1 and 2 (hosts) and 3 (admin), each with
// every legal document accepted.
func seedUsers(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	for _, u := range []struct {
		id         int
		name, role string
	}{{1, "host1", "host"}, {2, "host2", "host"}, {3, "admin1", "admin"}} {
		if _, err := pool.Exec(ctx,
			`INSERT INTO user_account (id, username, display_name, password_hash, role, must_change_password, created_at, email)
			 VALUES ($1, $2, $2, 'x', $3, 0, '2026-01-01T00:00:00+00:00', $2 || '@example.test')`,
			u.id, u.name, u.role); err != nil {
			t.Fatal(err)
		}
		for _, doc := range []string{"terms", "privacy", "dpa"} {
			if _, err := pool.Exec(ctx,
				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method)
				 VALUES ($1, $2, $3, '2026-01-01', 'clickwrap')`, u.id, doc, testVersion); err != nil {
				t.Fatal(err)
			}
		}
	}
}

func mustExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", sql, err)
	}
}

// seedAccount inserts a billing_account row for owner with the given status.
func seedAccount(t *testing.T, pool *pgxpool.Pool, owner int, status, plan, interval string) {
	t.Helper()
	mustExec(t, pool,
		`INSERT INTO billing_account (owner_user_id, status, plan, billing_interval, apartments_billed, updated_at)
		 VALUES ($1, $2, NULLIF($3, ''), NULLIF($4, ''), 1, '2026-11-01T00:00:00+00:00')`,
		owner, status, plan, interval)
}

// seedInvoice inserts one platform_invoice with a stored PDF (the bytes "%PDF-test").
func seedInvoice(t *testing.T, pool *pgxpool.Pool, id int, owner any, number, kind string, total int64) []byte {
	t.Helper()
	blob := []byte("%PDF-test " + number)
	sum := sha256.Sum256(blob)
	mustExec(t, pool,
		`INSERT INTO platform_invoice (id, owner_user_id, kind, seq_year, seq_no, number, vs, issue_date, due_date,
		   period_from, period_to, total_haler, snapshot_json, created_at, pdf_blob, pdf_sha256)
		 VALUES ($1::bigint, $2, $3, 2026, $1::bigint, $4, '2026' || lpad($1::bigint::text, 4, '0'), '2026-11-01', '2026-11-15',
		   to_char(date '2026-01-01' + $1::int, 'YYYY-MM-DD'), '2026-11-30', $5,
		   '{"invoice": {"buyer_name": "Buyer s.r.o.", "buyer_ico": "", "buyer_dic": ""}, "items": [{"description": "Plan", "gross_haler": 119000}]}',
		   '2026-11-01T00:00:00+00:00', $6, $7)`,
		id, owner, kind, number, total, blob, hex.EncodeToString(sum[:]))
	return blob
}

func csrfPair(t *testing.T, at time.Time) (*http.Cookie, string) {
	t.Helper()
	cookie := "billingweb-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "ubyhost_csrf", Value: cookie}, token
}

// sessionFor is auth.issue_session for the seeded accounts: host1, host2, admin1,
// or admin_imp (admin1 previewing host1's workspace).
func sessionFor(who string, at time.Time) string {
	payload := map[string]any{"sv": 1, "iat": at.Unix()}
	switch who {
	case "host1":
		payload["uid"] = 1
	case "host2":
		payload["uid"] = 2
	case "admin1":
		payload["uid"] = 3
	case "admin_imp":
		payload["uid"] = 3
		payload["as"] = 1
		payload["ast"] = at.Unix()
	}
	return session.Sign(testSecret, payload, at)
}

func testMux(pool *pgxpool.Pool, getenv func(string) string) *http.ServeMux {
	return testMuxWith(newDeps(pool, getenv, func() time.Time { return testNow }))
}

func testMuxWith(d deps) *http.ServeMux {
	mux := http.NewServeMux()
	for _, r := range newRoutes(d) {
		mux.Handle(r.Pattern, r.Handler)
	}
	return mux
}

// do sends one request. who "" is signed out. A POST carries a valid CSRF pair
// unless noCSRF is set.
func do(t *testing.T, mux http.Handler, method, path string, form url.Values, who string, noCSRF bool) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if method == http.MethodPost {
		req = httptest.NewRequest(method, path, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if !noCSRF {
			ck, token := csrfPair(t, testNow)
			req.AddCookie(ck)
			req.Header.Set("X-CSRF-Token", token)
		}
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	if who != "" {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(who, testNow)})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// location parses the Location header of a redirect.
func location(t *testing.T, rec *httptest.ResponseRecorder) *url.URL {
	t.Helper()
	u, err := url.Parse(rec.Header().Get("Location"))
	if err != nil {
		t.Fatal(err)
	}
	return u
}

func queryString(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) string {
	t.Helper()
	var s *string
	if err := pool.QueryRow(context.Background(), sql, args...).Scan(&s); err != nil {
		t.Fatalf("%s: %v", sql, err)
	}
	if s == nil {
		return "<null>"
	}
	return *s
}
