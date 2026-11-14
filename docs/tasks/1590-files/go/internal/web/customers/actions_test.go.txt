package customers

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// Tests of the operator POST actions (briefs 1590 and 1591). The expected rows
// are written out by hand from the Python functions named at each test, over
// the golden seed of brief 1360 (users 1 admin, 2 to 16 hosts; billing
// accounts in every state). "Today" is testNow, 2026-11-13.

// actEnv is the handler environment: the golden legal versions and a mail backend
// that queues (UBYHOST_MAIL_BACKEND=console).
func actEnv(versions map[string]string) func(string) string {
	base := testGetenv(versions)
	return func(k string) string {
		if k == "UBYHOST_MAIL_BACKEND" {
			return "console"
		}
		return base(k)
	}
}

// actCall is one POST of a form. uid 0 is signed out; impersonating makes the
// admin (uid 1) look at workspace 2.
type actCall struct {
	path          string
	form          string
	uid           int64
	sv            int64
	lang          string
	impersonating bool
	noToken       bool
	origin        string
}

func actServe(t *testing.T, mux *http.ServeMux, c actCall) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("POST", c.path, strings.NewReader(c.form))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfValue})
	if c.lang != "" {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: c.lang})
	}
	if c.uid != 0 {
		payload := map[string]any{"uid": c.uid, "sv": c.sv}
		if c.impersonating {
			payload["as"], payload["ast"] = 2, testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	}
	if !c.noToken {
		req.Header.Set("X-CSRF-Token", csrfToken(t))
	}
	if c.origin != "" {
		req.Header.Set("Origin", c.origin)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// flashOf splits a redirect's Location into path, msg and err (decoded).
func flashOf(t *testing.T, rec *httptest.ResponseRecorder) (status int, path, msg, errText string) {
	t.Helper()
	loc := rec.Header().Get("Location")
	u, err := url.Parse(loc)
	if err != nil {
		t.Fatalf("bad Location %q", loc)
	}
	q := u.Query()
	return rec.Code, u.Path, q.Get("msg"), q.Get("err")
}

// actRows runs a query and returns its rows as normalised JSON.
func actRows(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) string {
	t.Helper()
	rows, err := queryMaps(context.Background(), pool, sql, args...)
	if err != nil {
		t.Fatal(err)
	}
	return normValue(t, rows)
}

func actWant(t *testing.T, what, got, want string) {
	t.Helper()
	if w := norm(t, []byte(want)); got != w {
		t.Errorf("%s\n got: %s\nwant: %s", what, got, w)
	}
}

// actAudit is the audit rows written since top (login rows left out).
func actAudit(t *testing.T, pool *pgxpool.Pool, top int64) string {
	t.Helper()
	return normValue(t, auditSince(t, pool, top))
}

func countRows(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// accountMux routes the three account actions the way register_web_customers.go does.
func testClock() time.Time { return testNow }

func accountMux(pool *pgxpool.Pool, getenv func(string) string) *http.ServeMux {
	now := testClock
	mux := http.NewServeMux()
	mux.Handle("POST /admin/customers/{user_id}/stav", StatusHandler(pool, getenv, now))
	mux.Handle("POST /admin/customers/{user_id}/prodlouzit", ExtendTrialHandler(pool, getenv, now))
	mux.Handle("POST /admin/customers/{user_id}/overit-znovu", ResendVerificationHandler(pool, getenv, now))
	return mux
}

var idSegment = regexp.MustCompile(`/customers/[0-9]+/`)

// guardCases are the routes of one brief with a body that would change an
// account if the guards let it through.
type guardCase struct{ name, path, form string }

// checkGuards proves, for every route, what Python's guards do (CSRF dependency,
// path check, _require_admin) and that a refused request writes nothing.
func checkGuards(t *testing.T, mux *http.ServeMux, pool *pgxpool.Pool, cases []guardCase, watch string) {
	t.Helper()
	before := actRows(t, pool, watch)
	top := maxAuditID(t, pool)
	for _, c := range cases {
		// Signed out: login redirect with the path.
		rec := actServe(t, mux, actCall{path: c.path, form: c.form, lang: "en"})
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next="+c.path {
			t.Errorf("%s signed out: %d %q", c.name, rec.Code, rec.Header().Get("Location"))
		}
		// A normal host gets Python's 403 with the translated refusal.
		rec = actServe(t, mux, actCall{path: c.path, form: c.form, lang: "en", uid: 7, sv: 1})
		if rec.Code != http.StatusForbidden || rec.Body.String() != "Administrators only." {
			t.Errorf("%s host: %d %q", c.name, rec.Code, rec.Body.String())
		}
		// CSRF: cross-site is 403 JSON, a same-site request without a token goes back to the login.
		rec = actServe(t, mux, actCall{path: c.path, form: c.form, uid: 1, sv: 1, noToken: true, origin: "https://evil.example"})
		if rec.Code != http.StatusForbidden || rec.Body.String() != `{"detail":"Cross-site request rejected."}` {
			t.Errorf("%s cross-site: %d %q", c.name, rec.Code, rec.Body.String())
		}
		rec = actServe(t, mux, actCall{path: c.path, form: c.form, uid: 1, sv: 1, noToken: true})
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?notice=form_expired" {
			t.Errorf("%s no token: %d %q", c.name, rec.Code, rec.Header().Get("Location"))
		}
		// A user_id that is not an integer is FastAPI's 422, before the admin check (so for a host too).
		bad := idSegment.ReplaceAllString(c.path, "/customers/abc/")
		for _, uid := range []int64{0, 7, 1} {
			rec = actServe(t, mux, actCall{path: bad, form: c.form, uid: uid, sv: 1})
			if rec.Code != http.StatusUnprocessableEntity {
				t.Errorf("%s bad id uid %d: %d", c.name, uid, rec.Code)
			}
		}
	}
	actWant(t, "rows after refused requests", actRows(t, pool, watch), before)
	if got := maxAuditID(t, pool); got != top {
		t.Errorf("refused requests wrote %d audit rows", got-top)
	}
}

func accountWorld(t *testing.T) (*http.ServeMux, *pgxpool.Pool) {
	t.Helper()
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	return accountMux(pool, actEnv(g.Versions)), pool
}

// TestAccountActionGuards: every account route refuses as Python does.
func TestAccountActionGuards(t *testing.T) {
	mux, pool := accountWorld(t)
	checkGuards(t, mux, pool, []guardCase{
		{"stav", "/admin/customers/2/stav", "status=canceling"},
		{"prodlouzit", "/admin/customers/7/prodlouzit", "days=5"},
		{"overit-znovu", "/admin/customers/4/overit-znovu", ""},
	}, "SELECT owner_user_id, status, cancel_at_period_end, trial_ends_at FROM billing_account ORDER BY owner_user_id")
}

// TestStatusAction mirrors customer_status (admin_customers.py 241-262).
func TestStatusAction(t *testing.T) {
	mux, pool := accountWorld(t)
	post := func(id, form string, c actCall) (int, string, string, string, int64) {
		top := maxAuditID(t, pool)
		c.path, c.form, c.uid, c.sv = "/admin/customers/"+id+"/stav", form, 1, 1
		if c.lang == "" {
			c.lang = "en"
		}
		s, p, m, e := flashOf(t, actServe(t, mux, c))
		return s, p, m, e, top
	}
	// active -> canceling goes through cancel(): flag set, audit actor is the username (Python's "host").
	s, p, m, e, top := post("2", "status=canceling", actCall{})
	if s != 303 || p != "/admin/customers/2" || m != "Status changed." || e != "" {
		t.Errorf("cancel: %d %s %q %q", s, p, m, e)
	}
	actWant(t, "acct 2", actRows(t, pool, "SELECT status, cancel_at_period_end FROM billing_account WHERE owner_user_id = 2"),
		`[{"status":"canceling","cancel_at_period_end":1}]`)
	actWant(t, "cancel audit", actAudit(t, pool, top), `[{"action":"billing_status","actor":"admin","actor_user_id":1,
		"detail":"active->canceling","impersonator_user_id":null,"owner_user_id":2}]`)
	if n := countRows(t, pool, "SELECT COUNT(*) FROM billing_month_snapshot WHERE month = '2026-11'"); n == 0 {
		t.Error("month snapshot not written")
	}
	if got := actRows(t, pool, "SELECT status FROM billing_month_snapshot WHERE month = '2026-11' AND owner_user_id = 2"); got != `[{"status":"canceling"}]` {
		t.Errorf("snapshot of acct 2: %s", got)
	}
	// canceling -> active goes through resume().
	_, _, m, _, top = post("9", "status=active", actCall{})
	if m != "Status changed." {
		t.Errorf("resume msg %q", m)
	}
	actWant(t, "acct 9", actRows(t, pool, "SELECT status, cancel_at_period_end FROM billing_account WHERE owner_user_id = 9"),
		`[{"status":"active","cancel_at_period_end":0}]`)
	actWant(t, "resume audit", actAudit(t, pool, top), `[{"action":"billing_status","actor":"admin","actor_user_id":1,
		"detail":"canceling->active","impersonator_user_id":null,"owner_user_id":9}]`)
	// paused -> active is a plain set_status with actor operator:<username>.
	_, _, m, _, top = post("10", "status=active", actCall{})
	actWant(t, "set_status audit", actAudit(t, pool, top), `[{"action":"billing_status","actor":"operator:admin","actor_user_id":1,
		"detail":"paused->active","impersonator_user_id":null,"owner_user_id":10}]`)
	if m != "Status changed." {
		t.Errorf("set_status msg %q", m)
	}
	// A move the machine does not allow is refused and writes nothing (acct 2 is canceling now).
	_, _, m, e, top = post("2", "status=overdue", actCall{})
	if m != "" || e != "That status change is not allowed." {
		t.Errorf("refused: %q %q", m, e)
	}
	if got := actAudit(t, pool, top); got != "[]" {
		t.Errorf("refused move wrote %s", got)
	}
	// Unknown status, and the last value wins after strip.
	_, _, m, e, _ = post("2", "status=bogus", actCall{})
	if m != "" || e != "Unknown status." {
		t.Errorf("bad status: %q %q", m, e)
	}
	_, _, m, _, top = post("2", "status=bogus&status=%20paused%20", actCall{})
	if m != "Status changed." {
		t.Errorf("last value: %q", m)
	}
	actWant(t, "paused audit", actAudit(t, pool, top), `[{"action":"billing_status","actor":"operator:admin","actor_user_id":1,
		"detail":"canceling->paused","impersonator_user_id":null,"owner_user_id":2}]`)
	// Unknown user: Python has no 404 here, set_status just returns False.
	_, p, _, e, _ = post("99999", "status=paused", actCall{})
	if p != "/admin/customers/99999" || e != "That status change is not allowed." {
		t.Errorf("unknown user: %s %q", p, e)
	}
	// Czech text.
	_, _, _, e, _ = post("2", "status=bogus", actCall{lang: "cs"})
	if e != "Neznámý stav." {
		t.Errorf("Czech: %q", e)
	}
	// An impersonating admin passes the guard; the audit row names the impersonator.
	_, _, m, _, top = post("8", "status=paused", actCall{impersonating: true})
	if m != "Status changed." {
		t.Errorf("impersonating: %q", m)
	}
	actWant(t, "impersonating audit", actAudit(t, pool, top), `[{"action":"billing_status","actor":"operator:admin","actor_user_id":1,
		"detail":"overdue->paused","impersonator_user_id":1,"owner_user_id":8}]`)
}

// TestExtendTrialAction mirrors customer_extend_trial (admin_customers.py 184-202)
// and billing_order.extend_trial (billing_order.py 193-217).
func TestExtendTrialAction(t *testing.T) {
	mux, pool := accountWorld(t)
	post := func(id, form string) (string, string, int64) {
		top := maxAuditID(t, pool)
		_, _, m, e := flashOf(t, actServe(t, mux, actCall{path: "/admin/customers/" + id + "/prodlouzit", form: form, uid: 1, sv: 1, lang: "en"}))
		return m, e, top
	}
	ends := func(id string) string {
		return actRows(t, pool, "SELECT trial_ends_at FROM billing_account WHERE owner_user_id = "+id)
	}
	// A trial that runs on: its end plus the days.
	m, e, top := post("7", "days=7")
	if m != "Trial extended by 7 days." || e != "" {
		t.Errorf("extend: %q %q", m, e)
	}
	actWant(t, "acct 7 end", ends("7"), `[{"trial_ends_at":"2026-12-20"}]`)
	actWant(t, "extend audit", actAudit(t, pool, top), `[{"action":"billing_trial_extended","actor":"operator:admin","actor_user_id":1,
		"detail":"+7d -> 2026-12-20","impersonator_user_id":null,"owner_user_id":7}]`)
	// A trial that ended before today counts from today.
	m, _, _ = post("16", "days=10")
	actWant(t, "acct 16 end", ends("16"), `[{"trial_ends_at":"2026-11-23"}]`)
	// int() reads a sign and underscores; the last value wins.
	post("15", "days=%2B3")
	actWant(t, "acct 15 end", ends("15"), `[{"trial_ends_at":"2026-11-23"}]`)
	post("6", "days=1&days=1_0")
	actWant(t, "acct 6 end", ends("6"), `[{"trial_ends_at":"2026-11-26"}]`)
	// Out of range or not a number: bad_days, nothing written.
	for _, form := range []string{"days=0", "days=366", "days=-5", "days=abc", "days=", "", "days=1.5", "days=%20", "days=99999999999999999999999"} {
		m, e, top = post("4", form)
		if m != "" || e != "Days must be 1 to 365." {
			t.Errorf("form %q: %q %q", form, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("form %q wrote %s", form, got)
		}
	}
	// 365 is the edge that works.
	m, _, _ = post("6", "days=365")
	if m != "Trial extended by 365 days." {
		t.Errorf("365: %q", m)
	}
	actWant(t, "acct 6 end 365", ends("6"), `[{"trial_ends_at":"2027-11-26"}]`)
	// Not on a trial (active), no account row (user 3), no user at all: not_trialing.
	for _, id := range []string{"2", "3", "99999"} {
		m, e, top = post(id, "days=5")
		if m != "" || e != "This customer is not on a trial." {
			t.Errorf("user %s: %q %q", id, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("user %s wrote %s", id, got)
		}
	}
}

// TestResendVerificationAction mirrors customer_resend_verification
// (admin_customers.py 228-238) over signup.ResendOperator.
func TestResendVerificationAction(t *testing.T) {
	mux, pool := accountWorld(t)
	post := func(id, lang string) (string, string, int64) {
		top := maxAuditID(t, pool)
		_, _, m, e := flashOf(t, actServe(t, mux, actCall{path: "/admin/customers/" + id + "/overit-znovu", uid: 1, sv: 1, lang: lang}))
		return m, e, top
	}
	// Carol (4) is a pending sign-up: inactive, signed up, not verified.
	m, e, top := post("4", "en")
	if m != "Verification e-mail sent." || e != "" {
		t.Errorf("resend: %q %q", m, e)
	}
	actWant(t, "resend audit", actAudit(t, pool, top), `[{"action":"signup_resend_operator","actor":"operator:admin","actor_user_id":1,
		"detail":"","impersonator_user_id":null,"owner_user_id":4}]`)
	if got := countRows(t, pool, "SELECT COUNT(*) FROM user_account WHERE id = 4 AND signup_verify_nonce IS NOT NULL"); got != 1 {
		t.Error("nonce not stored")
	}
	if got := actRows(t, pool, "SELECT kind, owner_user_id FROM email_outbox WHERE idempotency_key LIKE 'signup_verify:4:%'"); got != `[{"kind":"signup_verify","owner_user_id":4}]` {
		t.Errorf("mail row: %s", got)
	}
	// A second resend retires the first link: one more mail, the nonce changes.
	post("4", "en")
	if got := countRows(t, pool, "SELECT COUNT(*) FROM email_outbox WHERE idempotency_key LIKE 'signup_verify:4:%'"); got != 2 {
		t.Errorf("mails after two resends: %d", got)
	}
	// Everyone else is refused: active host (2), verified sign-up (14), admin (1), missing user.
	for _, id := range []string{"2", "14", "1", "99999"} {
		m, e, top = post(id, "cs")
		if m != "" || e != "Tenhle účet nemá čekající ověření." {
			t.Errorf("user %s: %q %q", id, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("user %s wrote %s", id, got)
		}
	}
	if got := countRows(t, pool, "SELECT COUNT(*) FROM email_outbox WHERE idempotency_key LIKE 'signup_verify:%'"); got != 2 {
		t.Errorf("refused resends queued mail: %d", got)
	}
}

// TestPyIntAndClamp pins the helpers to Python's int().
func TestPyIntAndClamp(t *testing.T) {
	for in, want := range map[string]int{"7": 7, " 7 ": 7, "+7": 7, "-7": -7, "1_0": 10, "007": 7} {
		n, ok := pyInt(in)
		if !ok || clampInt(n) != want {
			t.Errorf("pyInt(%q) = %v %v", in, n, ok)
		}
	}
	for _, in := range []string{"", " ", "_1", "1_", "1__0", "1.5", "abc", "1e3", "٣", "+", "--1"} {
		if n, ok := pyInt(in); ok {
			t.Errorf("pyInt(%q) = %v, Python raises", in, n)
		}
	}
	big, _ := pyInt("99999999999999999999999")
	if clampInt(big) != 1<<40 {
		t.Error("clamp")
	}
	if b, err := json.Marshal(statuses); err != nil || string(b) != `["trial_pending","trialing","active","overdue","canceling","paused"]` {
		t.Errorf("statuses %s", b)
	}
}
