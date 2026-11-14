package exports

// Brief 1605: shared test set-up for the routes of briefs 1605 to 1609. It
// seeds the rows of testdata/exports_golden.json (the fixtures of briefs 1320
// and 1321, all made up) and signs sessions and CSRF pairs with the golden's
// test-only secret.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// world is one seeded test database with the export routes on a mux.
type world struct {
	t       *testing.T
	g       golden
	pool    *pgxpool.Pool
	mux     *http.ServeMux
	at      time.Time
	env     map[string]string
	dataDir string
}

// newWorld seeds the golden rows (and the golden's photo files) and mounts
// Routes with the golden's keys and clock.
func newWorld(t *testing.T) *world {
	t.Helper()
	g := loadGolden(t)
	pool := testPool(t)
	seedGolden(t, pool, g)
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	dataDir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dataDir, "passport_photos"), 0o700); err != nil {
		t.Fatal(err)
	}
	for _, name := range g.Photos {
		if err := os.WriteFile(filepath.Join(dataDir, "passport_photos", name), []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	w := &world{t: t, g: g, pool: pool, at: at, dataDir: dataDir, env: map[string]string{
		"UBYHOST_SECRET_KEY": g.Secret,
		"UBYHOST_DATA_KEYS":  g.DataKeys,
		"UBYHOST_DATA_DIR":   dataDir,
	}}
	w.mux = http.NewServeMux()
	for _, route := range Routes(pool, w.getenv, func() time.Time { return w.at }) {
		w.mux.Handle(route.Pattern, route.Handler)
	}
	return w
}

func (w *world) getenv(k string) string { return w.env[k] }

// who is a signed-in session: uid, and as (the workspace an admin supports)
// when not 0; stale makes the login an hour old.
type who struct {
	uid, as int64
	stale   bool
}

// do sends one request. A nil who is signed out. A POST carries form as an
// url-encoded body and a valid CSRF pair unless noCSRF is set.
func (w *world) do(method, path string, s *who, form url.Values, noCSRF bool) *httptest.ResponseRecorder {
	w.t.Helper()
	return w.send(method, path, s, form, noCSRF, "")
}

// doLang is do with the ubyhost_lang cookie set ("" or nil: none).
func (w *world) doLang(method, path string, s *who, lang *string, noCSRF bool) *httptest.ResponseRecorder {
	w.t.Helper()
	l := ""
	if lang != nil {
		l = *lang
	}
	return w.send(method, path, s, nil, noCSRF, l)
}

func (w *world) send(method, path string, s *who, form url.Values, noCSRF bool, lang string) *httptest.ResponseRecorder {
	w.t.Helper()
	var req *http.Request
	if method == http.MethodPost {
		req = httptest.NewRequest(method, path, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if !noCSRF {
			cookie := "exports-csrf-cookie"
			sum := sha256.Sum256([]byte(cookie))
			token, err := secure.NewTimedSerializer(w.g.Secret, "ubyhost-csrf").Dumps(
				map[string]any{"nonce": hex.EncodeToString(sum[:])}, w.at)
			if err != nil {
				w.t.Fatal(err)
			}
			req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
			req.Header.Set("X-CSRF-Token", token)
		}
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	if s != nil {
		iat := w.at.Unix()
		if s.stale {
			iat -= 3600
		}
		payload := map[string]any{"uid": s.uid, "sv": int64(0), "iat": iat}
		if s.as != 0 {
			payload["as"] = s.as
			payload["ast"] = w.at.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(w.g.Secret, payload, w.at)})
	}
	if lang != "" {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	}
	rec := httptest.NewRecorder()
	w.mux.ServeHTTP(rec, req)
	return rec
}

// exec runs one statement on the test database.
func (w *world) exec(sql string, args ...any) {
	w.t.Helper()
	if _, err := w.pool.Exec(context.Background(), sql, args...); err != nil {
		w.t.Fatalf("%s: %v", sql, err)
	}
}

// count is SELECT COUNT(*) ... on the test database.
func (w *world) count(sql string, args ...any) int {
	w.t.Helper()
	var n int
	if err := w.pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		w.t.Fatalf("%s: %v", sql, err)
	}
	return n
}

// lastAudit is the newest audit row: action, detail, actor, owner, actor id, impersonator.
func (w *world) lastAudit() []any {
	w.t.Helper()
	var action string
	var detail, actor *string
	var owner, actorID, imp *int64
	err := w.pool.QueryRow(context.Background(), `SELECT action, detail, actor, owner_user_id, actor_user_id,
		impersonator_user_id FROM audit ORDER BY id DESC LIMIT 1`).Scan(&action, &detail, &actor, &owner, &actorID, &imp)
	if err != nil {
		w.t.Fatal(err)
	}
	return []any{action, deref(detail), deref(actor), num(owner), num(actorID), num(imp)}
}

// auditMax is the highest audit id so far.
func (w *world) auditMax() int64 {
	w.t.Helper()
	var n int64
	if err := w.pool.QueryRow(context.Background(), `SELECT COALESCE(MAX(id), 0) FROM audit`).Scan(&n); err != nil {
		w.t.Fatal(err)
	}
	return n
}

// redirectsTo checks a 303 whose Location starts with prefix.
func redirectsTo(t *testing.T, name string, rec *httptest.ResponseRecorder, prefix string) {
	t.Helper()
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), prefix) {
		t.Errorf("%s: %d %q, want 303 to %s...", name, rec.Code, rec.Header().Get("Location"), prefix)
	}
}

var (
	asOwner   = &who{uid: 1}
	asOther   = &who{uid: 2}
	asAdmin   = &who{uid: 3}
	asSupport = &who{uid: 3, as: 1}
	asBroken  = &who{uid: 4}
	asStale   = &who{uid: 1, stale: true}
)
