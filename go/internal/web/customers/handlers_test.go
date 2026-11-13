package customers

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const testSecret = "customers-test-secret-key-0123456789abcdef"

var testNow = time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)

const csrfValue = "customers-csrf-cookie"

// testGetenv is the environment of every handler test. versions are the
// legal document versions the golden seed accepted (nil when no DB is used).
func testGetenv(versions map[string]string) func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_TERMS_VERSION":   versions["terms"],
		"UBYHOST_PRIVACY_VERSION": versions["privacy"],
		"UBYHOST_DPA_VERSION":     versions["dpa"],
	}
	return func(k string) string { return env[k] }
}

// csrfToken is a token bound to csrfValue, as security.csrf_token makes it.
func csrfToken(t *testing.T) string {
	t.Helper()
	sum := sha256.Sum256([]byte(csrfValue))
	token, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return token
}

// testMux routes the two handlers the way register_web_customers.go does.
func testMux(pool *pgxpool.Pool, getenv func(string) string) *http.ServeMux {
	now := func() time.Time { return testNow }
	mux := http.NewServeMux()
	mux.Handle("GET /admin/funnel", FunnelHandler(pool, getenv, now))
	mux.Handle("POST /admin/customers/{user_id}/aktivovat", ToggleActiveHandler(pool, getenv, now))
	return mux
}

// call is one request. payload nil means signed out; token "" means no CSRF header.
type call struct {
	method, path, lang, token, origin string
	payload                           map[string]any
}

func serve(t *testing.T, mux *http.ServeMux, c call) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(c.method, c.path, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfValue})
	if c.lang != "" {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: c.lang})
	}
	if c.payload != nil {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, c.payload, testNow)})
	}
	if c.token != "" {
		req.Header.Set("X-CSRF-Token", c.token)
	}
	if c.origin != "" {
		req.Header.Set("Origin", c.origin)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// TestCatalogMatchesPython checks i18n.json against host_i18n.py (the golden
// file's "i18n" section).
func TestCatalogMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if got, want := normValue(t, map[string]map[string]string(catalog)), normValue(t, g.I18N); got != want {
		t.Errorf("i18n.json differs from host_i18n.py\n got: %s\nwant: %s", got, want)
	}
}

func TestSignedOutGoesToLogin(t *testing.T) {
	mux := testMux(nil, testGetenv(nil))
	rec := serve(t, mux, call{method: "GET", path: "/admin/funnel"})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/admin/funnel" {
		t.Fatalf("funnel signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = serve(t, mux, call{method: "POST", path: "/admin/customers/5/aktivovat", token: csrfToken(t)})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/admin/customers/5/aktivovat" {
		t.Fatalf("toggle signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

// The CSRF check runs before the session is read, so a nil pool is never touched.
func TestToggleRejectsMissingCSRF(t *testing.T) {
	mux := testMux(nil, testGetenv(nil))
	signedIn := map[string]any{"uid": 1, "sv": 1}
	rec := serve(t, mux, call{method: "POST", path: "/admin/customers/5/aktivovat", payload: signedIn,
		origin: "https://evil.example"})
	if rec.Code != http.StatusForbidden || rec.Body.String() != `{"detail":"Cross-site request rejected."}` {
		t.Fatalf("cross-site: %d %q", rec.Code, rec.Body.String())
	}
	rec = serve(t, mux, call{method: "POST", path: "/admin/customers/5/aktivovat", payload: signedIn})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?notice=form_expired" {
		t.Fatalf("same-site without token: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = serve(t, mux, call{method: "POST", path: "/admin/customers/5/aktivovat", payload: signedIn,
		token: "not-a-token"})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?notice=form_expired" {
		t.Fatalf("bad token: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

type userState struct {
	ID             int64  `json:"id"`
	Username       string `json:"username"`
	Active         int64  `json:"active"`
	SessionVersion int64  `json:"session_version"`
}

func readUser(t *testing.T, pool *pgxpool.Pool, id int64) *userState {
	t.Helper()
	var u userState
	err := pool.QueryRow(context.Background(),
		"SELECT id, username, active, session_version FROM user_account WHERE id = $1", id).
		Scan(&u.ID, &u.Username, &u.Active, &u.SessionVersion)
	if err != nil {
		return nil
	}
	return &u
}

func maxAuditID(t *testing.T, pool *pgxpool.Pool) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), "SELECT COALESCE(MAX(id), 0) FROM audit").Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func auditSince(t *testing.T, pool *pgxpool.Pool, top int64) []map[string]any {
	t.Helper()
	rows, err := queryMaps(context.Background(), pool,
		"SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id "+
			"FROM audit WHERE id > $1 AND action <> 'login' ORDER BY id", top)
	if err != nil {
		t.Fatal(err)
	}
	return rows
}

// TestHandlersMatchPython replays the toggle and funnel steps that
// admin_customers_golden.py drove through the real FastAPI app: admin toggles
// (en and cs), own-account refusal, unknown user 404, non-admin 403, funnel.
func TestHandlersMatchPython(t *testing.T) {
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	mux := testMux(pool, testGetenv(g.Versions))
	uids := map[string]int64{"admin": 1, "host": 7}
	for _, s := range g.Toggle.Steps {
		uid := uids[s.Role]
		me := readUser(t, pool, uid)
		if me == nil {
			t.Fatalf("%s: no account %d", s.Name, uid)
		}
		var before *userState
		if s.Target != 0 {
			before = readUser(t, pool, s.Target)
		}
		same(t, s.Name+": user before", before, s.UserBefore)
		top := maxAuditID(t, pool)
		rec := serve(t, mux, call{method: s.Method, path: s.Path, lang: s.Lang, token: csrfToken(t),
			payload: map[string]any{"uid": uid, "sv": me.SessionVersion}})
		if rec.Code != s.Status {
			t.Errorf("%s: status %d, Python %d (%s)", s.Name, rec.Code, s.Status, rec.Body.String())
		}
		loc := rec.Header().Get("Location")
		if s.Location == nil && loc != "" || s.Location != nil && loc != *s.Location {
			t.Errorf("%s: location %q, Python %v", s.Name, loc, s.Location)
		}
		if s.Body != nil && rec.Body.String() != *s.Body {
			t.Errorf("%s: body %q, Python %q", s.Name, rec.Body.String(), *s.Body)
		}
		if ct := rec.Header().Get("Content-Type"); s.CType == nil && ct != "" || s.CType != nil && ct != *s.CType {
			t.Errorf("%s: content type %q, Python %v", s.Name, ct, s.CType)
		}
		var after *userState
		if s.Target != 0 {
			after = readUser(t, pool, s.Target)
		}
		same(t, s.Name+": user after", after, s.UserAfter)
		added := auditSince(t, pool, top)
		raw, _ := json.Marshal(s.AuditAdded)
		same(t, s.Name+": audit rows", added, raw)
	}
}

// An impersonating admin passes the guard (the real account is the admin), and
// the audit row names the admin as impersonator, as db.audit does.
func TestImpersonatingAdminToggles(t *testing.T) {
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	mux := testMux(pool, testGetenv(g.Versions))
	top := maxAuditID(t, pool)
	rec := serve(t, mux, call{method: "POST", path: "/admin/customers/5/aktivovat", lang: "en", token: csrfToken(t),
		payload: map[string]any{"uid": 1, "sv": 1, "as": 2, "ast": testNow.Unix()}})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/admin/customers/5?msg=Account%20dan%20activated." {
		t.Fatalf("impersonating toggle: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	want := `[{"action":"user_enabled","actor":"operator:admin","actor_user_id":1,"detail":"",` +
		`"impersonator_user_id":1,"owner_user_id":5}]`
	same(t, "impersonating audit", auditSince(t, pool, top), json.RawMessage(want))
	if u := readUser(t, pool, 5); u == nil || u.Active != 1 || u.SessionVersion != 2 {
		t.Fatalf("dan after: %+v", u)
	}
	// A path id that is not a number never reaches the database.
	rec = serve(t, mux, call{method: "POST", path: "/admin/customers/abc/aktivovat",
		lang: "en", token: csrfToken(t), payload: map[string]any{"uid": 1, "sv": 1}})
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("bad id: %d", rec.Code)
	}
}
