package payments

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const connectTestSecret = "connect-test-secret-key-0123456789abcdef"

type fakeOnboarder struct {
	url     string
	err     error
	retErr  error
	links   int
	base    string
	returns int
}

func (f *fakeOnboarder) OnboardingLink(_ context.Context, _ int64, base string) (string, error) {
	f.links++
	f.base = base
	return f.url, f.err
}

func (f *fakeOnboarder) HandleReturn(_ context.Context, _ int64) error {
	f.returns++
	return f.retErr
}

func connectNow() time.Time { return testNow }

func connectEnv(mode string, extra map[string]string) func(string) string {
	env := map[string]string{
		"UBYHOST_STRIPE_MODE":     mode,
		"UBYHOST_SECRET_KEY":      connectTestSecret,
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_TERMS_VERSION":   "t1",
		"UBYHOST_PRIVACY_VERSION": "p1",
		"UBYHOST_DPA_VERSION":     "d1",
	}
	for k, v := range extra {
		env[k] = v
	}
	return func(k string) string { return env[k] }
}

func connectDo(h http.HandlerFunc, method, path string, cookies, headers map[string]string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(""))
	for k, v := range cookies {
		req.AddCookie(&http.Cookie{Name: k, Value: v})
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	h(rec, req)
	return rec
}

func connectSession(uid int64, extra map[string]any) string {
	payload := map[string]any{"uid": uid, "sv": int64(0), "iat": testNow.Unix()}
	for k, v := range extra {
		payload[k] = v
	}
	return session.Sign(connectTestSecret, payload, testNow)
}

// connectCSRF mints a token bound to the CSRF cookie value, as csrf_token does.
func connectCSRF(t *testing.T, cookie string) string {
	t.Helper()
	sum := sha256.Sum256([]byte(cookie))
	tok, err := secure.NewTimedSerializer(connectTestSecret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func TestConnectExpiredTextsMatchPython(t *testing.T) {
	en, err := os.ReadFile("../../../App/app/host_i18n.py")
	if err != nil {
		t.Fatal(err)
	}
	vi, err := os.ReadFile("../../../App/app/host_vi_i18n.py")
	if err != nil {
		t.Fatal(err)
	}
	checks := map[string]struct {
		src  []byte
		want string
	}{
		"en": {en, hostweb.ExpiredTexts["en"]},
		"cs": {en, hostweb.ExpiredTexts["cs"]},
		"vi": {vi, hostweb.ExpiredTexts["vi"]},
	}
	for lang, c := range checks {
		if !strings.Contains(string(c.src), `"impersonation.expired": "`+c.want+`"`) {
			t.Errorf("%s: impersonation.expired differs from the Python file", lang)
		}
	}
}

func TestConnectNoCookieRedirectsToLogin(t *testing.T) {
	fake := &fakeOnboarder{url: "https://connect.stripe.example/setup"}
	h := ConnectStartHandler(nil, connectEnv("test", nil), connectNow, fake)
	rec := connectDo(h, http.MethodGet, "/payments/connect/start", nil, nil)
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/payments/connect/start" {
		t.Errorf("no cookie: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if fake.links != 0 {
		t.Errorf("Stripe called without a session")
	}
}

func TestConnectDatabase(t *testing.T) {
	pool := testPool(t)
	connectSeed(t, pool)

	const startPath = "/payments/connect/start"
	hostCookies := map[string]string{session.CookieName: connectSession(1, nil)}
	noConsentCookies := map[string]string{session.CookieName: connectSession(4, nil)}
	pendingCookies := map[string]string{session.CookieName: connectSession(3, nil)}
	adminCookies := map[string]string{session.CookieName: connectSession(2, map[string]any{
		"as":  int64(1),
		"ast": testNow.Unix() - 90000,
	})}
	fake := &fakeOnboarder{url: "https://connect.stripe.example/setup/abc"}
	start := func(mode string, extra map[string]string) http.HandlerFunc {
		return ConnectStartHandler(pool, connectEnv(mode, extra), connectNow, fake)
	}

	t.Run("mode off is 404", func(t *testing.T) {
		rec := connectDo(start("", nil), http.MethodGet, startPath, hostCookies, nil)
		if rec.Code != http.StatusNotFound || fake.links != 0 {
			t.Errorf("mode off: %d, links %d", rec.Code, fake.links)
		}
	})

	t.Run("consent missing goes to consent page", func(t *testing.T) {
		rec := connectDo(start("test", nil), http.MethodGet, startPath, noConsentCookies, nil)
		if rec.Header().Get("Location") != "/payments/consent" || fake.links != 0 {
			t.Errorf("consent missing: %q, links %d", rec.Header().Get("Location"), fake.links)
		}
	})

	t.Run("consent present redirects to Stripe with the public base", func(t *testing.T) {
		rec := connectDo(start("test", nil), http.MethodGet, startPath, hostCookies, nil)
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != fake.url {
			t.Errorf("start: %d %q", rec.Code, rec.Header().Get("Location"))
		}
		if fake.base != "https://ubyhost.example" {
			t.Errorf("base %q", fake.base)
		}
	})

	t.Run("no entity goes home", func(t *testing.T) {
		fake.err = ErrNoEntity
		defer func() { fake.err = nil }()
		rec := connectDo(start("test", nil), http.MethodGet, startPath, hostCookies, nil)
		if rec.Header().Get("Location") != "/" {
			t.Errorf("no entity: %q", rec.Header().Get("Location"))
		}
	})

	t.Run("other onboarding error is 500", func(t *testing.T) {
		fake.err = errors.New("boom")
		defer func() { fake.err = nil }()
		rec := connectDo(start("test", nil), http.MethodGet, startPath, hostCookies, nil)
		if rec.Code != http.StatusInternalServerError {
			t.Errorf("other error: %d", rec.Code)
		}
	})

	t.Run("return calls HandleReturn and goes home", func(t *testing.T) {
		h := ConnectReturnHandler(pool, connectEnv("test", nil), connectNow, fake)
		before := fake.returns
		rec := connectDo(h, http.MethodGet, "/payments/connect/return", hostCookies, nil)
		if rec.Header().Get("Location") != "/" || fake.returns != before+1 {
			t.Errorf("return: %q, calls %d", rec.Header().Get("Location"), fake.returns-before)
		}
		fake.retErr = ErrNoAccount
		rec = connectDo(h, http.MethodGet, "/payments/connect/return", hostCookies, nil)
		fake.retErr = nil
		if rec.Header().Get("Location") != "/" {
			t.Errorf("return with no account: %q", rec.Header().Get("Location"))
		}
	})

	t.Run("cross-site POST without token is 403", func(t *testing.T) {
		before := fake.links
		rec := connectDo(start("test", nil), http.MethodPost, startPath, hostCookies,
			map[string]string{"Origin": "https://evil.example"})
		if rec.Code != http.StatusForbidden || !strings.Contains(rec.Body.String(), "Cross-site request rejected.") || fake.links != before {
			t.Errorf("cross-site: %d %q", rec.Code, rec.Body.String())
		}
	})

	t.Run("same-site POST without token goes to recovery", func(t *testing.T) {
		rec := connectDo(start("test", nil), http.MethodPost, startPath, hostCookies,
			map[string]string{"Origin": "http://example.com"})
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?notice=form_expired" {
			t.Errorf("same-site: %d %q", rec.Code, rec.Header().Get("Location"))
		}
	})

	t.Run("POST with a valid token proceeds", func(t *testing.T) {
		cookies := map[string]string{
			session.CookieName: connectSession(1, nil),
			"ubyhost_csrf":     "csrf-cookie-1",
		}
		rec := connectDo(start("test", nil), http.MethodPost, startPath, cookies,
			map[string]string{"x-csrf-token": connectCSRF(t, "csrf-cookie-1")})
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != fake.url {
			t.Errorf("valid token: %d %q", rec.Code, rec.Header().Get("Location"))
		}
	})

	t.Run("acceptance pending redirects", func(t *testing.T) {
		rec := connectDo(start("test", nil), http.MethodGet, startPath, pendingCookies, nil)
		if rec.Header().Get("Location") != "/account/accept?next="+startPath {
			t.Errorf("acceptance: %q", rec.Header().Get("Location"))
		}
	})

	t.Run("expired impersonation writes two rows and a plain cookie", func(t *testing.T) {
		h := ConnectReturnHandler(pool, connectEnv("test", nil), connectNow, fake)
		rec := connectDo(h, http.MethodGet, "/payments/connect/return", adminCookies, nil)
		want := "/admin/customers?msg=" + url.PathEscape(hostweb.ExpiredTexts["en"])
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != want {
			t.Errorf("expired: %d %q", rec.Code, rec.Header().Get("Location"))
		}
		if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'impersonation_stopped' AND detail = 'expired'`); n != 2 {
			t.Errorf("impersonation_stopped rows: %d", n)
		}
		var token string
		for _, c := range rec.Result().Cookies() {
			if c.Name == session.CookieName {
				token = c.Value
			}
		}
		payload, ok := session.Verify(connectTestSecret, token, testNow)
		if !ok {
			t.Fatal("new cookie does not verify")
		}
		if _, has := payload["as"]; has {
			t.Errorf("new cookie still carries an impersonation claim")
		}
	})

	t.Run("paused billing blocks POST only", func(t *testing.T) {
		if _, err := pool.Exec(context.Background(),
			`INSERT INTO billing_account (owner_user_id, status, updated_at) VALUES (1, 'paused', NOW())`); err != nil {
			t.Fatal(err)
		}
		env := map[string]string{"UBYHOST_BILLING_ENABLED": "1"}
		cookies := map[string]string{
			session.CookieName: connectSession(1, nil),
			"ubyhost_csrf":     "csrf-cookie-2",
		}
		rec := connectDo(start("test", env), http.MethodPost, startPath, cookies,
			map[string]string{"x-csrf-token": connectCSRF(t, "csrf-cookie-2")})
		if rec.Header().Get("Location") != "/predplatne?paused=1" {
			t.Errorf("paused POST: %q", rec.Header().Get("Location"))
		}
		rec = connectDo(start("test", env), http.MethodGet, startPath, hostCookies, nil)
		if rec.Header().Get("Location") != fake.url {
			t.Errorf("paused GET: %q", rec.Header().Get("Location"))
		}
	})
}

// connectSeed makes host 1 (consented, legal accepted), admin 2, host 3 (acceptance
// pending) and host 4 (legal accepted, no consent).
func connectSeed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES
			(1, 'host', 'x', NOW(), 'host', 1, 0),
			(2, 'admin', 'x', NOW(), 'admin', 1, 0),
			(3, 'newhost', 'x', NOW(), 'host', 1, 0),
			(4, 'noconsent', 'x', NOW(), 'host', 1, 0)`,
		`INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES
			(1, 1, 'terms', 't1', NOW(), 'clickwrap'), (2, 1, 'privacy', 'p1', NOW(), 'clickwrap'), (3, 1, 'dpa', 'd1', NOW(), 'clickwrap'),
			(4, 2, 'terms', 't1', NOW(), 'clickwrap'), (5, 2, 'privacy', 'p1', NOW(), 'clickwrap'), (6, 2, 'dpa', 'd1', NOW(), 'clickwrap'),
			(7, 4, 'terms', 't1', NOW(), 'clickwrap'), (8, 4, 'privacy', 'p1', NOW(), 'clickwrap'), (9, 4, 'dpa', 'd1', NOW(), 'clickwrap')`,
	}
	for _, q := range stmts {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	if err := audit(ctx, pool, stampAt(testNow), connectConsentAction, connectConsentDetail, 1); err != nil {
		t.Fatal(err)
	}
}
