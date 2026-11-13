package onboarding

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const testSecret = "onboarding-test-secret-key-0123456789abcdef"

var testNow = time.Unix(1790000000, 0)

// TestSafeLocalPathPythonCases are the cases of
// test_safe_local_path_rejects_ambiguous_redirect_targets (App/tests/test_security.py)
// with the results Python gives.
func TestSafeLocalPathPythonCases(t *testing.T) {
	cases := []struct{ in, want string }{
		{"https://other.example/path", "/fallback"},
		{"//other.example/path", "/fallback"},
		{"/%2f%2fother.example/path", "/fallback"},
		{"/\\other.example/path", "/fallback"},
		{"/%5cother.example/path", "/fallback"},
		{"/safe\r\nLocation: https://other.example", "/fallback"},
		{"/a/../../other", "/other"},
		{"", "/fallback"},
		{"/x?a=1#frag", "/x?a=1"},
		{"///x", "/x"},
		{"////x", "/fallback"},
		{"//[x", "/fallback"},
	}
	for _, c := range cases {
		got := safeLocalPath(c.in, "/fallback")
		if got != c.want {
			t.Errorf("safeLocalPath(%q) = %q, want %q", c.in, got, c.want)
		}
		if !strings.HasPrefix(got, "/") || strings.HasPrefix(got, "//") || strings.ContainsAny(got, "\\\r\n") {
			t.Errorf("safeLocalPath(%q) = %q is not a safe local path", c.in, got)
		}
	}
}

func TestPyInt(t *testing.T) {
	cases := []struct {
		in   string
		want string
		ok   bool
	}{
		{"0", "0", true}, {"5", "5", true}, {"+5", "5", true}, {"-007", "-7", true},
		{"1_000", "1000", true}, {" 12 ", "12", true}, {"99999999999999999999", "99999999999999999999", true},
		{"", "", false}, {"abc", "", false}, {"1.5", "", false}, {"_1", "", false}, {"1_", "", false},
		{"1__0", "", false}, {"+_1", "", false}, {"+", "", false}, {"0x10", "", false}, {"1 2", "", false},
		{strings.Repeat("1", 4300), strings.Repeat("1", 4300), true}, {strings.Repeat("1", 4301), "", false},
	}
	for _, c := range cases {
		n, ok := pyInt(c.in)
		if ok != c.ok || (ok && n.String() != c.want) {
			t.Errorf("pyInt(%.20q) = %v, %v; want %q, %v", c.in, n, ok, c.want, c.ok)
		}
	}
}

func TestStarletteQuote(t *testing.T) {
	in := "/a b/é?x=1&y=<\">#f~;:@[]!$'()*+,%20"
	want := "/a%20b/%C3%A9?x=1&y=%3C%22%3E#f~;:@[]!$'()*+,%20"
	if got := starletteQuote(in); got != want {
		t.Errorf("starletteQuote = %q, want %q", got, want)
	}
}

func TestPyStrip(t *testing.T) {
	if got := pyStrip("\x1c 　 x \t \x1f"); got != "x" {
		t.Errorf("pyStrip = %q", got)
	}
	if got := pyStrip("​x"); got != "​x" {
		t.Errorf("pyStrip must keep U+200B: %q", got)
	}
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and
// applies the Postgres migrations, as pushweb_test.go does.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_onboarding_%d", time.Now().UnixNano())
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
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
	return pool
}

// seedAccounts adds admin 1 and hosts 2 and 3, each with the current legal
// acceptances so require_login does not send them to /account/accept.
func seedAccounts(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	for _, a := range []struct {
		id         int64
		name, role string
	}{{1, "admin_one", "admin"}, {2, "host_two", "host"}, {3, "host_three", "host"}} {
		if _, err := pool.Exec(ctx,
			`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES ($1, $2, 'x', '2026-01-01T00:00:00+00:00', $3, 1, 1)`,
			a.id, a.name, a.role); err != nil {
			t.Fatal(err)
		}
		for doc, ver := range map[string]string{"terms": "1.7", "privacy": "1.8", "dpa": "1.8"} {
			if _, err := pool.Exec(ctx,
				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01T00:00:00+00:00', 'clickwrap')`,
				a.id, doc, ver); err != nil {
				t.Fatal(err)
			}
		}
	}
}

type request struct {
	form    url.Values
	uid     int64
	extra   map[string]any
	noCSRF  bool
	signOut bool
}

func post(t *testing.T, h http.Handler, path string, rq request) *httptest.ResponseRecorder {
	t.Helper()
	cookie := "onboarding-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
	if err != nil {
		t.Fatal(err)
	}
	form := url.Values{}
	for k, v := range rq.form {
		form[k] = v
	}
	if !rq.noCSRF {
		form.Set("_csrf", token)
	}
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
	if !rq.signOut {
		payload := map[string]any{"uid": rq.uid, "sv": 1}
		for k, v := range rq.extra {
			payload[k] = v
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func wantRedirect(t *testing.T, rec *httptest.ResponseRecorder, location string) {
	t.Helper()
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != location {
		t.Fatalf("got %d %q, want 303 %q: %s", rec.Code, rec.Header().Get("Location"), location, rec.Body.String())
	}
}

func setting(t *testing.T, pool *pgxpool.Pool, key string) (string, bool) {
	t.Helper()
	var value *string
	err := pool.QueryRow(context.Background(), `SELECT value FROM settings WHERE key = $1`, key).Scan(&value)
	if err == pgx.ErrNoRows {
		return "", false
	}
	if err != nil {
		t.Fatal(err)
	}
	if value == nil {
		return "<NULL>", true
	}
	return *value, true
}

type auditRow struct {
	at, actor, action, detail string
	owner, actorID            int64
	impersonator              *int64
}

func audits(t *testing.T, pool *pgxpool.Pool) []auditRow {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []auditRow
	for rows.Next() {
		var a auditRow
		if err := rows.Scan(&a.at, &a.actor, &a.action, &a.detail, &a.owner, &a.actorID, &a.impersonator); err != nil {
			t.Fatal(err)
		}
		out = append(out, a)
	}
	return out
}

func TestOnboardingRoutes(t *testing.T) {
	pool := testPool(t)
	seedAccounts(t, pool)
	env := map[string]string{"UBYHOST_SECRET_KEY": testSecret}
	getenv := func(k string) string { return env[k] }
	now := func() time.Time { return testNow }
	dismiss := DismissHandler(pool, getenv, now)
	resume := ResumeHandler(pool, getenv, now)
	welcome := WelcomeBackDismissHandler(pool, getenv, now)
	celebrate := CelebrationDismissHandler(pool, getenv, now)
	stamp := "2026-09-21T14:13:20+00:00"
	preview := map[string]any{"as": 2, "ast": testNow.Unix()}

	t.Run("signed out goes to login", func(t *testing.T) {
		wantRedirect(t, post(t, dismiss, "/onboarding/dismiss", request{signOut: true}), "/login?next=/onboarding/dismiss")
		if _, ok := setting(t, pool, "onboarding_dismissed_2"); ok {
			t.Fatal("signed-out dismiss wrote a setting")
		}
	})

	t.Run("missing CSRF token is refused", func(t *testing.T) {
		wantRedirect(t, post(t, dismiss, "/onboarding/dismiss", request{uid: 2, noCSRF: true}), "/login?notice=form_expired")
		if len(audits(t, pool)) != 0 {
			t.Fatal("CSRF-less dismiss wrote an audit row")
		}
	})

	t.Run("dismiss then resume", func(t *testing.T) {
		rec := post(t, dismiss, "/onboarding/dismiss", request{uid: 2, form: url.Values{"return_to": {"/x", " /a b/../c?q=é#frag "}}})
		wantRedirect(t, rec, "/c?q=%C3%A9")
		if rec.Body.Len() != 0 {
			t.Fatalf("redirect body %q, want empty", rec.Body.String())
		}
		if v, _ := setting(t, pool, "onboarding_dismissed_2"); v != "1" {
			t.Fatalf("onboarding_dismissed_2 = %q, want 1", v)
		}
		wantRedirect(t, post(t, resume, "/onboarding/resume", request{uid: 2, form: url.Values{"return_to": {"https://evil.example/"}}}), "/onboarding")
		if v, _ := setting(t, pool, "onboarding_dismissed_2"); v != "0" {
			t.Fatalf("onboarding_dismissed_2 = %q, want 0", v)
		}
		wantRedirect(t, post(t, dismiss, "/onboarding/dismiss", request{uid: 2}), "/")
		got := audits(t, pool)
		want := []auditRow{
			{stamp, "host_two", "onboarding.dismissed", "", 2, 2, nil},
			{stamp, "host_two", "onboarding.resumed", "", 2, 2, nil},
			{stamp, "host_two", "onboarding.dismissed", "", 2, 2, nil},
		}
		if fmt.Sprint(got) != fmt.Sprint(want) {
			t.Fatalf("audit rows %v, want %v", got, want)
		}
	})

	t.Run("an admin previewing a workspace acts for it", func(t *testing.T) {
		before := len(audits(t, pool))
		wantRedirect(t, post(t, resume, "/onboarding/resume", request{uid: 1, extra: preview}), "/onboarding")
		if v, _ := setting(t, pool, "onboarding_dismissed_2"); v != "0" {
			t.Fatalf("onboarding_dismissed_2 = %q, want 0", v)
		}
		if _, ok := setting(t, pool, "onboarding_dismissed_1"); ok {
			t.Fatal("preview wrote the admin's own key")
		}
		rows := audits(t, pool)
		if len(rows) != before+1 {
			t.Fatalf("%d audit rows, want %d", len(rows), before+1)
		}
		last := rows[len(rows)-1]
		if last.actor != "admin_one" || last.owner != 2 || last.actorID != 1 || last.impersonator == nil || *last.impersonator != 1 {
			t.Fatalf("preview audit row %+v", last)
		}
	})

	t.Run("welcome back uses the signed-in account", func(t *testing.T) {
		if _, err := pool.Exec(context.Background(), `INSERT INTO settings (key, value) VALUES ('welcome_back_1', '2026-01-01|2026-02-01')`); err != nil {
			t.Fatal(err)
		}
		wantRedirect(t, post(t, welcome, "/welcome-back/dismiss", request{uid: 1, extra: preview, form: url.Values{"return_to": {"/elsewhere"}}}), "/")
		if v, _ := setting(t, pool, "welcome_back_1"); v != "" {
			t.Fatalf("welcome_back_1 = %q, want empty", v)
		}
		if _, ok := setting(t, pool, "welcome_back_2"); ok {
			t.Fatal("welcome-back dismiss wrote the workspace's key")
		}
	})

	t.Run("celebrations", func(t *testing.T) {
		wantRedirect(t, post(t, celebrate, "/celebrations/dismiss", request{uid: 3, form: url.Values{"milestone": {" 1_0 "}, "return_to": {"/dashboard"}}}), "/dashboard")
		if v, _ := setting(t, pool, "celebration_3"); v != "10" {
			t.Fatalf("celebration_3 = %q, want 10", v)
		}
		wantRedirect(t, post(t, celebrate, "/celebrations/dismiss", request{uid: 3, form: url.Values{"milestone": {"0"}}}), "/")
		wantRedirect(t, post(t, celebrate, "/celebrations/dismiss", request{uid: 3}), "/")
		if v, _ := setting(t, pool, "celebration_3"); v != "10" {
			t.Fatalf("milestone 0 changed celebration_3 to %q", v)
		}
		rec := post(t, celebrate, "/celebrations/dismiss", request{uid: 3, form: url.Values{"milestone": {"abc"}}})
		if rec.Code != http.StatusInternalServerError || rec.Header().Get("Cache-Control") != "no-store, private" {
			t.Fatalf("bad milestone: %d %q", rec.Code, rec.Header().Get("Cache-Control"))
		}
		if v, _ := setting(t, pool, "celebration_3"); v != "10" {
			t.Fatalf("bad milestone changed celebration_3 to %q", v)
		}
	})

	t.Run("pool settings", func(t *testing.T) {
		ctx := context.Background()
		s := PoolSettings(pool)
		if _, err := pool.Exec(ctx, `INSERT INTO settings (key, value) VALUES ('property_setup:5', NULL)`); err != nil {
			t.Fatal(err)
		}
		for _, k := range []string{"property_setup:5", "property_setup:6"} {
			if v, err := s.Get(ctx, k); err != nil || v != "" {
				t.Fatalf("Get(%s) = %q, %v", k, v, err)
			}
		}
		if err := Mark(ctx, s, 5, "pin", "done"); err != nil {
			t.Fatal(err)
		}
		if err := Mark(ctx, s, 5, "police", "waiting"); err != nil {
			t.Fatal(err)
		}
		want := `{"celebrated": false, "finished": false, "hidden": false, "legacy": true, "steps": {"guest_link": "done", "police": "waiting"}, "tested": false}`
		if v, _ := setting(t, pool, "property_setup:5"); v != want {
			t.Fatalf("property_setup:5 = %s", v)
		}
	})
}
