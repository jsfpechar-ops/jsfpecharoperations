# 1363: Go customer admin part 3 of 3: admin guard, funnel redirect, account toggle

Status: review
Depends on: 1362 | Base commit: a83df5412638cc7ae1c64810e5b0b59fc68997cc | Branch: go-customer-admin (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Add `requireAdmin` (port of `_require_admin`, `App/app/routes/admin_accounts.py` line 716), `GET /admin/funnel` (303 to `/admin/fakturace#reports`) and `POST /admin/customers/{user_id}/aktivovat` (port of `customer_toggle_active`), and register only those two routes. The tests replay the golden toggle and funnel steps of brief 1360 against the Go handlers and check signed-out, CSRF and impersonation cases.

## 2. Context

- Split: this task is three briefs run in order on one branch, one executor session each: 1360 (Python golden fixture), 1362 (Go queries), 1363 (Go guard, funnel, toggle, routes). Brief 1361 (HTML pages) comes later. The orchestrator opens one draft PR after 1363.
- Plan: `docs/plans/go-full-move.md` §2 (parity first: a Python golden script writes fixtures, the Go code reproduces them) and §7 row "Port customer admin pages" (Tier B, own package `go/internal/web/customers/`). You do not need to open it.
- Every file in this brief is NEW and given in full. Create it byte for byte from its block in §4 (everything between the `~~~~` fence lines, ending with one newline) and check its sha256. If the sha256 differs: compare with the block once, fix, check again; still different: STOP (§8). Never edit an existing file.
- The port stays switched off: no Caddy, env, `UBYHOST_GO_PATHS` or `docs/ENVIRONMENT.md` change. No new dependency (rule 4). SQL Postgres-portable (rule 5). Never push to `main` (rule 8).
- Needs `go/internal/web/customers/query.go` from brief 1362: `test -f go/internal/web/customers/query.go && echo ok`. Missing: STOP.
- Guard order, as in Python: CSRF (`hostweb.CSRF`), then `hostweb.Login`, then the REAL account's role must be `admin` (an impersonating admin passes), else 403 with the translated `auth.error.admins_only`. `requireAdmin` is replaced later by `admingate.Require` from `go/internal/session/admingate` (another thread, not on main): do not import it.
- `go/cmd/ubyhost-web/registry.go` (read-only): a thread adds its own `register_web_<area>.go` whose `init()` calls `registerRoutes`; the route function must not use the pool while it builds.
- The four host strings live in the package's own `i18n.json`; `App/scripts/go_host_i18n.py` only scans `go/internal/*/i18n_keys.txt` one level deep, so `TestCatalogMatchesPython` checks them through the golden file instead.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/handlers.go` | create | `requireAdmin`, `FunnelHandler`, `ToggleActiveHandler` |
| `go/internal/web/customers/i18n.json` | create | the 4 host strings the handlers read |
| `go/internal/web/customers/handlers_test.go` | create | catalog, signed-out, CSRF, golden replay and impersonation tests |
| `go/cmd/ubyhost-web/register_web_customers.go` | create | registers the 2 routes |
| `docs/tasks/1363-go-customer-admin-toggle.md` | edit | `Status:` line only |
| `docs/tasks/1363-report.md` | create | your report |

No other file may change.

## 4. Steps

Commit after each step with the message `1363 step k`.

### Step 1: start Postgres (no commit)

```bash
PGBIN=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1360 && chown postgres /var/tmp/pg1360
[ -f /var/tmp/pg1360/data/PG_VERSION ] || su postgres -c "$PGBIN/initdb -D /var/tmp/pg1360/data -A trust -U postgres" | tail -3
$PGBIN/pg_isready -h 127.0.0.1 -p 55436 || { rm -f /var/tmp/pg1360/data/postmaster.pid /var/tmp/pg1360/.s.PGSQL.55436 /var/tmp/pg1360/.s.PGSQL.55436.lock; su postgres -c "$PGBIN/pg_ctl -D /var/tmp/pg1360/data -l /var/tmp/pg1360/log -o '-p 55436 -k /var/tmp/pg1360 -c listen_addresses=127.0.0.1' -w start" 2>&1 | tail -3; }
$PGBIN/pg_isready -h 127.0.0.1 -p 55436
```

Expected last line: `127.0.0.1:55436 - accepting connections`.

### Step 2: handlers and strings

Create `go/internal/web/customers/i18n.json`:

~~~~json
{
 "cs": {
  "auth.error.admins_only": "Pouze pro administrátory.",
  "auth.error.own_disable": "Nemůžete vypnout vlastní administrátorský účet.",
  "customers.ops.disabled": "Účet %(username)s deaktivován.",
  "customers.ops.enabled": "Účet %(username)s aktivován."
 },
 "en": {
  "auth.error.admins_only": "Administrators only.",
  "auth.error.own_disable": "You cannot disable your own administrator account.",
  "customers.ops.disabled": "Account %(username)s deactivated.",
  "customers.ops.enabled": "Account %(username)s activated."
 },
 "vi": {
  "auth.error.admins_only": "Chỉ dành cho quản trị viên.",
  "auth.error.own_disable": "Bạn không thể tắt tài khoản quản trị của chính mình."
 }
}
~~~~

Check: `sha256sum go/internal/web/customers/i18n.json 2>&1 | tail -30` must print `190bb75a6b63df3f73fb37dca67d7b9a04c9998260e1551072e348123623306e`.

Create `go/internal/web/customers/handlers.go`:

~~~~go
package customers

import (
	_ "embed"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the host strings this package reads. The golden test checks it
// against host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

// page is routes/admin_customers.PAGE.
const page = "/admin/customers"

// requireAdmin is _require_admin (routes/admin_accounts.py): the signed-in
// real account must be an admin, so an impersonating admin passes. It returns
// ok=false after writing the response (a login redirect, the 403 text or a
// 500). It is replaced by admingate.Require in a later brief.
func requireAdmin(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(w, r, pool, getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	if h.Account.Role != "admin" {
		// Starlette's Response(text, 403) sends no Content-Type; a nil value
		// stops net/http from adding one.
		w.Header()["Content-Type"] = nil
		w.WriteHeader(http.StatusForbidden)
		_, _ = io.WriteString(w, catalog.T(hostweb.Lang(r), "auth.error.admins_only", nil))
		return nil, false
	}
	return h, true
}

// FunnelHandler serves GET /admin/funnel (admin_accounts.funnel_admin): the
// funnel moved into Reports on the billing page.
func FunnelHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if _, ok := requireAdmin(w, r, pool, getenv, now()); !ok {
			return
		}
		w.Header().Set("Location", "/admin/fakturace#reports")
		w.WriteHeader(http.StatusSeeOther)
	}
}

// ToggleActiveHandler serves POST /admin/customers/{user_id}/aktivovat
// (admin_customers.customer_toggle_active). The CSRF check runs first, as the
// Python app-wide dependency does.
func ToggleActiveHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		admin, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		userID, err := strconv.ParseInt(r.PathValue("user_id"), 10, 64)
		if err != nil {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return
		}
		ctx := r.Context()
		var username string
		var wasActive int64
		err = pool.QueryRow(ctx, "SELECT username, active FROM user_account WHERE id = $1", userID).Scan(&username, &wasActive)
		if errors.Is(err, pgx.ErrNoRows) {
			// HTTPException(404) answers FastAPI's JSON body.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
			return
		}
		if err != nil {
			serverError(w, err)
			return
		}
		back := fmt.Sprintf("%s/%d", page, userID)
		lang := hostweb.Lang(r)
		if userID == admin.Account.ID {
			key := "auth.error.own_disable"
			hostweb.Back(w, r, back, hostweb.Flash{}, hostweb.Flash{Text: catalog.T(lang, key, nil), Key: key})
			return
		}
		active, action, key := int64(1), "user_enabled", "customers.ops.enabled"
		if wasActive != 0 {
			active, action, key = 0, "user_disabled", "customers.ops.disabled"
		}
		if err := setActive(r, pool, admin, userID, active, action, at); err != nil {
			serverError(w, err)
			return
		}
		msg := catalog.T(lang, key, map[string]any{"username": username})
		hostweb.Back(w, r, back, hostweb.Flash{Text: msg, Key: key}, hostweb.Flash{})
	}
}

// setActive flips the account and writes the audit row in one transaction:
// db.execute UPDATE and db.audit (actor operator:<admin>, the admin's id, and
// impersonator_user_id only while the admin is inside another workspace).
func setActive(r *http.Request, pool *pgxpool.Pool, admin *session.Host, userID, active int64, action string, at time.Time) error {
	ctx := r.Context()
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx,
		"UPDATE user_account SET active = $1, session_version = session_version + 1 WHERE id = $2",
		active, userID); err != nil {
		return err
	}
	var impersonator any
	if admin.Impersonating {
		impersonator = admin.Account.ID
	}
	if _, err := tx.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		stamp(at), "operator:"+admin.Account.Username, action, "", userID, admin.Account.ID, impersonator); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// stamp is db.utcnow: UTC, whole seconds, "+00:00".
func stamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("customers: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}
~~~~

Check: `sha256sum go/internal/web/customers/handlers.go 2>&1 | tail -30` must print `9e90463d27a0ae1f60eb96b9e71359ab7cda8cd674df62e3c0132f0fdb87127f`.

Run from `go/`: `/usr/local/go/bin/go build ./internal/web/... 2>&1 | tail -30` (no output). Commit `1363 step 2`.

### Step 3: routes

Create `go/cmd/ubyhost-web/register_web_customers.go`:

~~~~go
package main

// Web thread "customer admin" owns this file. Only the routes that need no
// host layout are registered; the customer list and detail pages come later.
// The port stays off until a path is routed to Go.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("GET /admin/funnel", m.wrap("/admin/funnel", customers.FunnelHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/aktivovat", m.wrap("/admin/customers/{user_id}/aktivovat", customers.ToggleActiveHandler(pool, os.Getenv, time.Now)))
	})
}
~~~~

Check: `sha256sum go/cmd/ubyhost-web/register_web_customers.go 2>&1 | tail -30` must print `5913abc6d71de5b05e984e0fa7e25d13b2f50c516856afc8e498664604c032be`.

Run from `go/`: `/usr/local/go/bin/go vet ./cmd/... 2>&1 | tail -30` (no output). Commit `1363 step 3`.

### Step 4: handler tests

Create `go/internal/web/customers/handlers_test.go`:

~~~~go
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
~~~~

Check: `sha256sum go/internal/web/customers/handlers_test.go 2>&1 | tail -30` must print `063139f3a8c82db38d50d10c3cfebed9f78fb4c9d8eea7d6fd273b79e2e083b3`.

Run §6. Commit `1363 step 4`.

### Step 5: report

Write the report (§9), set `Status: review`, commit `1363 step 5`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `App/tests/conftest.py`, every existing file under `App/app/` and `App/scripts/`.
- `docs/context/*`, `docs/ENVIRONMENT.md`, Caddy, compose and `.env` files: no change.
- `go/internal/web/customers/testdata/admin_customers_golden.json` is written only by the golden script, never by hand.
- Never print the session secret or cookies. No push, merge or deploy.

## 6. Commands

1. Postgres: step 1 block.
2. Go, from the repo root:

```bash
cd go && export PATH=$PATH:/usr/local/go/bin
test -z "$(gofmt -l ./internal/web ./cmd)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ -count=1 -v 2>&1 | grep -E -c 'SKIP'
```

Expected: `ok` for both packages; the last command prints `0` (the DB tests run; none skip).

3. From `App/`: `.venv/bin/python -m pytest tests/test_admin_customers_golden.py -q --tb=short 2>&1 | tail -30` (`1 passed`).
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` ends `context lint: OK`.

## 7. Acceptance

- [ ] The 4 files exist with the sha256 values in §4.
- [ ] All `customers` tests and `go/cmd/ubyhost-web` tests pass (incl. `TestRoutesRegisterOnce`); `grep -c SKIP` prints `0`.
- [ ] `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_customers.go` prints `2`.
- [ ] Context lint OK.
- [ ] `git diff --stat <start commit>` lists only the §3 paths.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 differs twice for the same file;
- a test fails twice;
- Postgres does not start, or a DB test skips;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1363-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat <start commit>`; `<start commit>` is the commit you started from: `git rev-parse HEAD` before step 1, write it down).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/customers/handlers.go`: guard order; own-account refusal; UPDATE and audit row in one transaction (actor `operator:<admin>`, `actor_user_id` the admin, `impersonator_user_id` only while impersonating, as `db.audit`); 403 without Content-Type and 404 `{"detail":"Not Found"}`, as FastAPI sends them. A non-numeric `user_id` answers 422 without FastAPI's JSON body.
- `go/cmd/ubyhost-web/register_web_customers.go`: only the two patterns, no pool use while building.

## Owner steps

None for this brief. When CI is green on the draft PR, merge it. The routes stay on Python until a later brief adds their paths to `UBYHOST_GO_PATHS`.
