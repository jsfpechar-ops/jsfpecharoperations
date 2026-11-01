package pushweb

import (
	"context"
	"crypto/ecdh"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
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

const testSecret = "pushweb-test-secret-key-0123456789abcdef"

var testNow = time.Unix(1790000000, 0)

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and applies
// the Postgres migrations to it, as session_test.go does.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_pushweb_%d", time.Now().UnixNano())
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
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
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

type fixture struct {
	pool   *pgxpool.Pool
	env    map[string]string
	pubKey string
	auth   string
}

// call is one request: its path, body, user agent, cookies and CSRF header.
type call struct {
	path    string
	body    string
	ua      string
	cookies []*http.Cookie
	token   string
}

type routes struct {
	subscribe, refresh, unsubscribe, remove http.Handler
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	pool := testPool(t)
	ctx := context.Background()
	accounts := []struct {
		id         int64
		name, role string
	}{{1, "admin_one", "admin"}, {2, "host_two", "host"}, {3, "host_three", "host"}}
	for _, a := range accounts {
		if _, err := pool.Exec(ctx,
			`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES ($1, $2, 'x', '2026-01-01T00:00:00+00:00', $3, 1, 1)`,
			a.id, a.name, a.role); err != nil {
			t.Fatal(err)
		}
	}
	priv, err := ecdh.P256().GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	auth := make([]byte, 16)
	if _, err := rand.Read(auth); err != nil {
		t.Fatal(err)
	}
	return &fixture{
		pool:   pool,
		env:    map[string]string{"UBYHOST_SECRET_KEY": testSecret},
		pubKey: base64.RawURLEncoding.EncodeToString(priv.PublicKey().Bytes()),
		auth:   base64.RawURLEncoding.EncodeToString(auth),
	}
}

func (f *fixture) getenv(k string) string { return f.env[k] }

func (f *fixture) offEnv(k string) string {
	if k == "UBYHOST_WEB_PUSH" {
		return "0"
	}
	return f.env[k]
}

func (f *fixture) routes(getenv func(string) string) routes {
	now := func() time.Time { return testNow }
	return routes{
		subscribe:   SubscribeHandler(f.pool, getenv, now),
		refresh:     RefreshHandler(f.pool, getenv, now),
		unsubscribe: UnsubscribeHandler(f.pool, getenv, now),
		remove:      DeviceDeleteHandler(f.pool, getenv, now),
	}
}

func csrfCookieAndToken(t *testing.T) (*http.Cookie, string) {
	t.Helper()
	cookie := "pushweb-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "ubyhost_csrf", Value: cookie}, token
}

// as is a call signed in as uid (with extra session payload) and carrying a valid CSRF token.
func as(t *testing.T, uid int64, extra map[string]any) call {
	t.Helper()
	payload := map[string]any{"uid": uid, "sv": 1}
	for k, v := range extra {
		payload[k] = v
	}
	ck, token := csrfCookieAndToken(t)
	return call{
		cookies: []*http.Cookie{{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)}, ck},
		token:   token,
	}
}

func serve(h http.Handler, c call) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, c.path, strings.NewReader(c.body))
	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		req.Header.Set("X-CSRF-Token", c.token)
	}
	if c.ua != "" {
		req.Header.Set("User-Agent", c.ua)
	}
	for _, ck := range c.cookies {
		req.AddCookie(ck)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func (f *fixture) subBody(endpoint, lang string) string {
	return fmt.Sprintf(`{"subscription":{"endpoint":%q,"keys":{"p256dh":%q,"auth":%q}},"lang":%q}`,
		endpoint, f.pubKey, f.auth, lang)
}

func endpointFor(i int) string {
	return fmt.Sprintf("https://web.push.apple.com/device-%d", i)
}

func count(t *testing.T, f *fixture, query string, args ...any) int {
	t.Helper()
	var n int
	if err := f.pool.QueryRow(context.Background(), query, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func wantStatus(t *testing.T, rec *httptest.ResponseRecorder, want int) {
	t.Helper()
	if rec.Code != want {
		t.Fatalf("status %d, want %d: %s", rec.Code, want, rec.Body.String())
	}
}

func wantBody(t *testing.T, rec *httptest.ResponseRecorder, want string) {
	t.Helper()
	if got := strings.TrimSpace(rec.Body.String()); got != want {
		t.Fatalf("body %q, want %q", got, want)
	}
}

func TestPushDeviceRoutes(t *testing.T) {
	f := newFixture(t)
	rt := f.routes(f.getenv)
	mux := http.NewServeMux()
	mux.Handle("POST /account/push/devices/{id}/delete", rt.remove)
	ck, token := csrfCookieAndToken(t)
	csrfOnly := []*http.Cookie{ck}

	t.Run("signed out", func(t *testing.T) {
		c := call{path: "/account/push/subscribe", body: f.subBody(endpointFor(0), ""), cookies: csrfOnly, token: token}
		rec := serve(rt.subscribe, c)
		wantStatus(t, rec, http.StatusUnauthorized)
		if !strings.Contains(rec.Body.String(), "Log in again") || rec.Header().Get("Cache-Control") != "no-store" {
			t.Fatalf("bad signed-out answer: %s", rec.Body.String())
		}
	})

	t.Run("admin previewing another workspace", func(t *testing.T) {
		c := as(t, 1, map[string]any{"as": 2, "ast": testNow.Unix()})
		c.path = "/account/push/subscribe"
		c.body = f.subBody(endpointFor(0), "")
		wantStatus(t, serve(rt.subscribe, c), http.StatusUnauthorized)
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription`); n != 0 {
			t.Fatalf("preview stored %d devices", n)
		}
	})

	t.Run("bad CSRF is refused", func(t *testing.T) {
		c := call{path: "/account/push/subscribe", body: f.subBody(endpointFor(0), ""), cookies: []*http.Cookie{{Name: session.CookieName, Value: session.Sign(testSecret, map[string]any{"uid": 2, "sv": 1}, testNow)}}}
		rec := serve(rt.subscribe, c)
		if rec.Code == http.StatusOK {
			t.Fatalf("CSRF-less subscribe was accepted")
		}
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription`); n != 0 {
			t.Fatalf("refused call stored %d devices", n)
		}
	})

	t.Run("push off gives 409", func(t *testing.T) {
		c := as(t, 2, nil)
		c.path = "/account/push/subscribe"
		c.body = f.subBody(endpointFor(0), "")
		rec := serve(f.routes(f.offEnv).subscribe, c)
		wantStatus(t, rec, http.StatusConflict)
	})

	t.Run("subscribe valid and idempotent", func(t *testing.T) {
		c := as(t, 2, nil)
		c.path = "/account/push/subscribe"
		c.body = f.subBody(endpointFor(0), "cs")
		c.ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
		rec := serve(rt.subscribe, c)
		wantStatus(t, rec, http.StatusOK)
		wantBody(t, rec, `{"ok":true}`)
		digest := hashEndpoint(endpointFor(0))
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE endpoint_hash = $1 AND user_account_id = 2 AND device = 'iPhone' AND lang = 'cs'`, digest); n != 1 {
			t.Fatalf("stored row not found (n=%d)", n)
		}
		if n := count(t, f, `SELECT COUNT(*) FROM audit WHERE action = 'push_device_added' AND detail = 'devices=1' AND owner_user_id = 2 AND actor = 'host_two' AND actor_user_id = 2 AND impersonator_user_id IS NULL`); n != 1 {
			t.Fatalf("audit row not written (n=%d)", n)
		}
		wantStatus(t, serve(rt.subscribe, c), http.StatusOK)
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE user_account_id = 2`); n != 1 {
			t.Fatalf("same endpoint twice made %d rows", n)
		}
	})

	t.Run("invalid subscriptions give 400", func(t *testing.T) {
		bad := []string{
			`{"subscription":{"endpoint":"https://web.push.apple.com/x"}}`,
			`{"subscription":"not an object"}`,
			fmt.Sprintf(`{"subscription":{"endpoint":"http://web.push.apple.com/x","keys":{"p256dh":%q,"auth":%q}}}`, f.pubKey, f.auth),
			fmt.Sprintf(`{"subscription":{"endpoint":"https://evil.example/x","keys":{"p256dh":%q,"auth":%q}}}`, f.pubKey, f.auth),
			fmt.Sprintf(`{"subscription":{"endpoint":"https://fcm.googleapis.com/%s","keys":{"p256dh":%q,"auth":%q}}}`, strings.Repeat("a", 1100), f.pubKey, f.auth),
			fmt.Sprintf(`{"subscription":{"endpoint":"https://fcm.googleapis.com/x","keys":{"p256dh":"AAAA","auth":%q}}}`, f.auth),
		}
		for _, body := range bad {
			c := as(t, 2, nil)
			c.path = "/account/push/subscribe"
			c.body = body
			rec := serve(rt.subscribe, c)
			wantStatus(t, rec, http.StatusBadRequest)
			if !strings.Contains(rec.Body.String(), "Could not turn on alerts") {
				t.Fatalf("bad answer for %s: %s", body, rec.Body.String())
			}
		}
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE user_account_id = 2`); n != 1 {
			t.Fatalf("invalid bodies changed the device count to %d", n)
		}
	})

	t.Run("device cap", func(t *testing.T) {
		for i := 1; i < maxDevices; i++ {
			c := as(t, 2, nil)
			c.path = "/account/push/subscribe"
			c.body = f.subBody(endpointFor(i), "")
			wantStatus(t, serve(rt.subscribe, c), http.StatusOK)
		}
		c := as(t, 2, nil)
		c.path = "/account/push/subscribe"
		c.body = f.subBody(endpointFor(maxDevices), "")
		rec := serve(rt.subscribe, c)
		wantStatus(t, rec, http.StatusBadRequest)
		if !strings.Contains(rec.Body.String(), "Alerts are on for 10 devices") {
			t.Fatalf("cap answer: %s", rec.Body.String())
		}
	})

	t.Run("refresh", func(t *testing.T) {
		c := as(t, 2, nil)
		c.path = "/account/push/refresh"
		c.body = fmt.Sprintf(`{"endpoint":%q,"lang":"vi"}`, endpointFor(0))
		wantBody(t, serve(rt.refresh, c), `{"known":true}`)
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE endpoint_hash = $1 AND lang = 'vi'`, hashEndpoint(endpointFor(0))); n != 1 {
			t.Fatalf("refresh did not update the language")
		}
		c.body = fmt.Sprintf(`{"endpoint":%q}`, endpointFor(999))
		wantBody(t, serve(rt.refresh, c), `{"known":false}`)
		other := as(t, 3, nil)
		other.path = "/account/push/refresh"
		other.body = fmt.Sprintf(`{"endpoint":%q}`, endpointFor(0))
		wantBody(t, serve(rt.refresh, other), `{"known":false}`)
	})

	t.Run("unsubscribe", func(t *testing.T) {
		other := as(t, 3, nil)
		other.path = "/account/push/unsubscribe"
		other.body = fmt.Sprintf(`{"endpoint":%q}`, endpointFor(0))
		wantBody(t, serve(rt.unsubscribe, other), `{"ok":true}`)
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE user_account_id = 2`); n != maxDevices {
			t.Fatalf("another account's unsubscribe removed a device (n=%d)", n)
		}
		c := as(t, 2, nil)
		c.path = "/account/push/unsubscribe"
		c.body = fmt.Sprintf(`{"endpoint":%q}`, endpointFor(0))
		wantBody(t, serve(rt.unsubscribe, c), `{"ok":true}`)
		if n := count(t, f, `SELECT COUNT(*) FROM audit WHERE action = 'push_device_removed' AND detail = 'source=device' AND owner_user_id = 2`); n != 1 {
			t.Fatalf("removal audit rows: %d", n)
		}
		c.body = fmt.Sprintf(`{"endpoint":%q}`, endpointFor(999))
		wantBody(t, serve(rt.unsubscribe, c), `{"ok":true}`)
		if n := count(t, f, `SELECT COUNT(*) FROM audit WHERE action = 'push_device_removed' AND owner_user_id = 2`); n != 1 {
			t.Fatalf("unknown endpoint wrote an audit row")
		}
	})

	t.Run("device delete from settings", func(t *testing.T) {
		var own int64
		if err := f.pool.QueryRow(context.Background(), `SELECT id FROM push_subscription WHERE user_account_id = 2 ORDER BY id LIMIT 1`).Scan(&own); err != nil {
			t.Fatal(err)
		}
		c := as(t, 2, nil)
		c.path = fmt.Sprintf("/account/push/devices/%d/delete", own)
		rec := serve(mux, c)
		wantStatus(t, rec, http.StatusSeeOther)
		if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/settings?msg=") || !strings.HasSuffix(loc, "#settings-group-phone") {
			t.Fatalf("redirect %q", loc)
		}
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE id = $1`, own); n != 0 {
			t.Fatalf("own device still there")
		}

		// Account 3 has a device; account 2 cannot remove it.
		third := as(t, 3, nil)
		third.path = "/account/push/subscribe"
		third.body = f.subBody(endpointFor(50), "")
		wantStatus(t, serve(rt.subscribe, third), http.StatusOK)
		var theirs int64
		if err := f.pool.QueryRow(context.Background(), `SELECT id FROM push_subscription WHERE user_account_id = 3`).Scan(&theirs); err != nil {
			t.Fatal(err)
		}
		other := as(t, 2, nil)
		other.path = fmt.Sprintf("/account/push/devices/%d/delete", theirs)
		rec = serve(mux, other)
		wantStatus(t, rec, http.StatusSeeOther)
		if loc := rec.Header().Get("Location"); loc != "/settings#settings-group-phone" {
			t.Fatalf("plain redirect expected, got %q", loc)
		}
		if n := count(t, f, `SELECT COUNT(*) FROM push_subscription WHERE id = $1`, theirs); n != 1 {
			t.Fatalf("another account's device was removed")
		}
	})

	t.Run("device id not an integer is 404", func(t *testing.T) {
		c := as(t, 2, nil)
		c.path = "/account/push/devices/abc/delete"
		wantStatus(t, serve(mux, c), http.StatusNotFound)
	})

	t.Run("device delete signed out uses a flash", func(t *testing.T) {
		c := call{path: "/account/push/devices/1/delete", cookies: csrfOnly, token: token}
		rec := serve(mux, c)
		wantStatus(t, rec, http.StatusSeeOther)
		if !strings.Contains(rec.Header().Get("Location"), "err=") {
			t.Fatalf("no flash on redirect: %q", rec.Header().Get("Location"))
		}
	})

	t.Run("body over 8 KiB counts as empty", func(t *testing.T) {
		pad := strings.Repeat("a", 9000)
		c := as(t, 2, nil)
		c.path = "/account/push/refresh"
		c.body = fmt.Sprintf(`{"endpoint":%q,"pad":%q}`, endpointFor(0), pad)
		wantBody(t, serve(rt.refresh, c), `{"known":false}`)
		c.path = "/account/push/subscribe"
		c.body = fmt.Sprintf(`{"subscription":{"endpoint":%q},"pad":%q}`, endpointFor(0), pad)
		wantStatus(t, serve(rt.subscribe, c), http.StatusBadRequest)
	})
}
