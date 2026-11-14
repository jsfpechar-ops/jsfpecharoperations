package ai

// Shared helpers of the guide tests (brief 1440). Nothing here calls a real
// external service; the database tests skip without UBYHOST_TEST_DATABASE_URL.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const guideTestSecret = "guide-test-secret-key-0123456789abcdef"

var guideTestNow = time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)

// guideTestEnvs is the environment of a test; a test may add to it.
func guideTestEnv(extra map[string]string) func(string) string {
	base := map[string]string{
		"UBYHOST_SECRET_KEY":      guideTestSecret,
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_TERMS_VERSION":   "t1",
		"UBYHOST_PRIVACY_VERSION": "p1",
		"UBYHOST_DPA_VERSION":     "d1",
	}
	for k, v := range extra {
		base[k] = v
	}
	return func(k string) string { return base[k] }
}

func guideTestLookup(getenv func(string) string) func(string) (string, bool) {
	return func(k string) (string, bool) { v := getenv(k); return v, v != "" }
}

func guideTestClock() time.Time { return guideTestNow }

// guideTestPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL,
// applies the goose Up sections of App/migrations_pg and drops it at the end.
// It skips when the variable is unset.
func guideTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_guide_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

// guideSeedUser inserts an active host account and returns its id.
func guideSeedUser(t *testing.T, pool *pgxpool.Pool, username, role string) int64 {
	t.Helper()
	var id int64
	err := pool.QueryRow(context.Background(), `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
VALUES ($1, 'x', $2, 1, 1, '2026-01-01T00:00:00+00:00', $3) RETURNING id`, username, role, username+"@example.test").Scan(&id)
	if err != nil {
		t.Fatal(err)
	}
	for _, doc := range []string{"terms", "privacy", "dpa"} { // the versions of guideTestEnv
		guideTestExec(t, pool, `INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01T00:00:00+00:00', 'backfill')`,
			id, doc, map[string]string{"terms": "t1", "privacy": "p1", "dpa": "d1"}[doc])
	}
	return id
}

// guideSeedApartment inserts a property of owner and returns its id.
func guideSeedApartment(t *testing.T, pool *pgxpool.Pool, owner int64, name string) int64 {
	t.Helper()
	var id int64
	err := pool.QueryRow(context.Background(), `INSERT INTO apartment (owner_user_id, internal_name, created_at)
VALUES ($1, $2, '2026-01-01T00:00:00+00:00') RETURNING id`, owner, name).Scan(&id)
	if err != nil {
		t.Fatal(err)
	}
	return id
}

func guideTestExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatal(err)
	}
}

func guideTestCount(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func guideTestServer(pool *pgxpool.Pool, extra map[string]string) *guideServer {
	getenv := guideTestEnv(extra)
	return &guideServer{pool: pool, getenv: getenv, lookupEnv: guideTestLookup(getenv), now: guideTestClock}
}

// guideTestMux serves the guide routes the way cmd/ubyhost-web does.
func guideTestMux(pool *pgxpool.Pool, extra map[string]string) http.Handler {
	getenv := guideTestEnv(extra)
	mux := http.NewServeMux()
	for _, route := range GuideRoutes(pool, getenv, guideTestLookup(getenv), guideTestClock) {
		mux.Handle(route.Pattern, route.Handler)
	}
	return mux
}

const guideTestCSRFCookie = "guide-test-csrf-cookie"

func guideTestCSRF(t *testing.T) string {
	t.Helper()
	sum := sha256.Sum256([]byte(guideTestCSRFCookie))
	tok, err := secure.NewTimedSerializer(guideTestSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, guideTestNow)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

// guideTestDo sends a request as host uid (0 means signed out). A POST gets a
// valid CSRF token in the _csrf field and url-encoded form values.
func guideTestDo(t *testing.T, h http.Handler, method, target string, uid int64, form url.Values) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if method == http.MethodPost {
		if form == nil {
			form = url.Values{}
		}
		form.Set("_csrf", guideTestCSRF(t))
		req = httptest.NewRequest(method, target, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	} else {
		req = httptest.NewRequest(method, target, nil)
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: guideTestCSRFCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	if uid != 0 {
		token := session.Sign(guideTestSecret, map[string]any{"uid": uid, "sv": int64(1), "iat": guideTestNow.Unix()}, guideTestNow)
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: token})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func jsonUnmarshal(data []byte, v any) error { return json.Unmarshal(data, v) }

func guideTestRequest(t *testing.T, uid int64, target string) *http.Request {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, target, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: guideTestCSRFCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	return req
}

func guideTestRecorder() *httptest.ResponseRecorder { return httptest.NewRecorder() }

func guideTestHost(uid int64) *session.Host {
	acc := session.Account{ID: uid, Username: "host1", Role: "host", SessionVersion: 1}
	return &session.Host{Account: acc, Workspace: acc}
}

func layoutPage(title string) layout.Page {
	return layout.Page{Title: title, BodyKind: "settings", V2: true}
}

// guideCardWorld is a host with one property whose default cards exist, and a stranger.
type guideCardWorld struct {
	pool           *pgxpool.Pool
	mux            http.Handler
	s              *guideServer
	host, stranger int64
	apt, otherApt  int64
	checkin, wifi  int64
	dataDir        string
}

func newGuideCardWorld(t *testing.T) *guideCardWorld {
	t.Helper()
	pool := guideTestPool(t)
	dir := t.TempDir()
	extra := map[string]string{"UBYHOST_DATA_DIR": dir}
	w := &guideCardWorld{pool: pool, mux: guideTestMux(pool, extra), s: guideTestServer(pool, extra), dataDir: dir}
	w.host = guideSeedUser(t, pool, "host1", "host")
	w.stranger = guideSeedUser(t, pool, "stranger", "host")
	w.apt = guideSeedApartment(t, pool, w.host, "Flat 1")
	w.otherApt = guideSeedApartment(t, pool, w.stranger, "Flat X")
	now := guideStamp(guideTestNow)
	ctx := context.Background()
	for _, id := range []int64{w.apt, w.otherApt} {
		if err := w.s.ensureDefaults(ctx, &guideApartment{ID: id}, now); err != nil {
			t.Fatal(err)
		}
	}
	rows, _ := w.s.items(ctx, w.apt)
	for _, r := range rows {
		switch r.Kind {
		case "checkin":
			w.checkin = r.ID
		case "wifi":
			w.wifi = r.ID
		}
	}
	return w
}

func (w *guideCardWorld) path(parts ...string) string {
	return "/apartments/" + itoa64(w.apt) + "/guide" + strings.Join(parts, "")
}

func itoa64(n int64) string { return strconv.FormatInt(n, 10) }

func intString(n int64) string { return strconv.FormatInt(n, 10) }

func location(rec *httptest.ResponseRecorder) string { return rec.Header().Get("Location") }
