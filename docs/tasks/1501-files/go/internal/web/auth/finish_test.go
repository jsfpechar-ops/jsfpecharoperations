package auth

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

type finishGolden struct {
	Secret string `json:"secret"`
	Now    int64  `json:"now"`
	Paths  []struct {
		In       string `json:"in"`
		Safe     string `json:"safe"`
		Location string `json:"location"`
	} `json:"paths"`
	Langs []struct {
		Base      string  `json:"base"`
		Query     string  `json:"query"`
		Cookie    *string `json:"cookie"`
		SetCookie *string `json:"set_cookie"`
	} `json:"langs"`
	Cookies []struct {
		Deployment   string   `json:"deployment"`
		Base         string   `json:"base"`
		Remember     bool     `json:"remember"`
		SessionToken string   `json:"session_token"`
		SetCookie    []string `json:"set_cookie"`
		DeviceKeys   []string `json:"device_keys"`
		DeviceDidLen int      `json:"device_did_len"`
	} `json:"cookies"`
}

func loadFinishGolden(t *testing.T) finishGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/finish_login.json")
	if err != nil {
		t.Fatal(err)
	}
	var g finishGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Paths) == 0 || len(g.Langs) == 0 || len(g.Cookies) == 0 {
		t.Fatal("empty golden")
	}
	return g
}

// cookieShape is one Set-Cookie line without its value: the name and the
// attributes, lower-cased, in a stable order (Starlette and Go order them
// differently).
func cookieShape(line string) string {
	parts := strings.Split(line, ";")
	name := strings.SplitN(strings.TrimSpace(parts[0]), "=", 2)[0]
	var attrs []string
	for _, p := range parts[1:] {
		attrs = append(attrs, strings.ToLower(strings.TrimSpace(p)))
	}
	sort.Strings(attrs)
	return name + "|" + strings.Join(attrs, ";")
}

func cookieValue(line string) string {
	first := strings.TrimSpace(strings.Split(line, ";")[0])
	return strings.SplitN(first, "=", 2)[1]
}

// TestNextPathMatchesPython: the Location _finish_login sends is
// RedirectResponse(safe_local_path(next, "/")).headers["location"].
func TestNextPathMatchesPython(t *testing.T) {
	for _, c := range loadFinishGolden(t).Paths {
		if got := safeLocalPath(c.In, "/"); got != c.Safe {
			t.Errorf("safeLocalPath(%q) = %q, want %q", c.In, got, c.Safe)
		}
		if got := locationQuote(safeLocalPath(c.In, "/")); got != c.Location {
			t.Errorf("location(%q) = %q, want %q", c.In, got, c.Location)
		}
	}
}

// TestKeepLoginLanguageMatchesPython: the ubyhost_lang cookie
// _keep_login_language sets (or not) for each ?lang= and cookie.
func TestKeepLoginLanguageMatchesPython(t *testing.T) {
	for _, c := range loadFinishGolden(t).Langs {
		r := httptest.NewRequest("POST", "/login/link", nil)
		r.URL.RawQuery = c.Query
		if c.Cookie != nil {
			r.Header.Set("Cookie", "ubyhost_lang="+*c.Cookie)
		}
		w := httptest.NewRecorder()
		keepLoginLanguage(w, r, func(k string) string {
			if k == "UBYHOST_PUBLIC_BASE_URL" {
				return c.Base
			}
			return ""
		})
		got := w.Header().Values("Set-Cookie")
		if c.SetCookie == nil {
			if len(got) != 0 {
				t.Errorf("%s %q %v: set %v, Python sets nothing", c.Base, c.Query, c.Cookie, got)
			}
			continue
		}
		if len(got) != 1 || cookieShape(got[0]) != cookieShape(*c.SetCookie) || cookieValue(got[0]) != cookieValue(*c.SetCookie) {
			t.Errorf("%s %q %v: got %v, want %q", c.Base, c.Query, c.Cookie, got, *c.SetCookie)
		}
	}
}

func finishEnv(g finishGolden, deployment, base string) func(string) string {
	return func(k string) string {
		switch k {
		case "UBYHOST_SECRET_KEY":
			return g.Secret
		case "UBYHOST_DEPLOYMENT":
			return deployment
		case "UBYHOST_PUBLIC_BASE_URL":
			return base
		}
		return ""
	}
}

// sessionPayload is the JSON a session token signs, after checking the
// signature and timestamp at at.
func sessionPayload(t *testing.T, secret, token string, at time.Time) string {
	t.Helper()
	var raw json.RawMessage
	if err := secure.NewTimedSerializer(secret, "ubyhost-session").Loads(token, time.Second, at, &raw); err != nil {
		t.Fatalf("session token does not load: %v", err)
	}
	return string(raw)
}

// TestLoginCookiesMatchPython: the session token issue_session signs at the
// same second, and the attributes of attach_session and attach_device, in
// each cookie-security setting.
func TestLoginCookiesMatchPython(t *testing.T) {
	g := loadFinishGolden(t)
	at := time.Unix(g.Now, 0)
	for _, c := range g.Cookies {
		env := finishEnv(g, c.Deployment, c.Base)
		token, err := session.IssueSession(g.Secret, 7, 3, session.IssueOptions{Remember: c.Remember}, at)
		// Go's zlib output differs from Python's, so compare what each token
		// carries: the same payload bytes signed at the same second.
		if err != nil || sessionPayload(t, g.Secret, token, at) != sessionPayload(t, g.Secret, c.SessionToken, at) {
			t.Fatalf("%s %s remember=%v: session payload differs", c.Deployment, c.Base, c.Remember)
		}
		w := httptest.NewRecorder()
		secureCookie := hostweb.SecureCookies(env)
		http.SetCookie(w, session.SessionCookie(token, c.Remember, secureCookie))
		http.SetCookie(w, session.DeviceCookie("DEVICE", secureCookie))
		got := w.Header().Values("Set-Cookie")
		if len(got) != 2 {
			t.Fatalf("cookies %v", got)
		}
		for i := range got {
			if cookieShape(got[i]) != cookieShape(c.SetCookie[i]) {
				t.Errorf("%s %s remember=%v: %q, want %q", c.Deployment, c.Base, c.Remember, got[i], c.SetCookie[i])
			}
		}
	}
}

// TestStartSession runs startSession and finishLogin against PostgreSQL:
// last_login_at, the audit row, the three cookies in Python's order, and the
// Location; a failing write leaves no cookie.
func TestStartSession(t *testing.T) {
	g := loadFinishGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	at := time.Unix(g.Now, 0)
	env := finishEnv(g, "production", "https://ubyhost.example")
	d := deps{pool: pool, getenv: env, now: func() time.Time { return at }}
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, session_version, email)
		VALUES (7, 'host7', 'x', '2026-01-01T00:00:00+00:00', 3, 'host@example.cz')`); err != nil {
		t.Fatal(err)
	}
	account, err := session.AccountByID(ctx, pool, 7)
	if err != nil || account == nil {
		t.Fatalf("account: %v", err)
	}
	r := httptest.NewRequest("POST", "/login/link", nil)
	w := httptest.NewRecorder()
	if err := d.finishLogin(w, r, account, true, "/x?q=a b", MethodLinkTOTP, ActionTwoFactorLogin, at); err != nil {
		t.Fatal(err)
	}
	if w.Code != http.StatusSeeOther || w.Header().Get("Location") != "/x?q=a%20b" {
		t.Fatalf("redirect %d %q", w.Code, w.Header().Get("Location"))
	}
	got := w.Header().Values("Set-Cookie")
	names := []string{}
	for _, line := range got {
		names = append(names, strings.SplitN(line, "=", 2)[0])
	}
	if !reflect.DeepEqual(names, []string{session.CookieName, session.DeviceCookieName, langCookieName}) {
		t.Fatalf("cookies %v", names)
	}
	if sessionPayload(t, g.Secret, cookieValue(got[0]), at) != sessionPayload(t, g.Secret, g.Cookies[0].SessionToken, at) ||
		cookieValue(got[2]) != "cs" {
		t.Fatalf("session or language cookie differs")
	}
	var dev map[string]any
	if err := secure.NewTimedSerializer(g.Secret, "ubyhost-device").Loads(cookieValue(got[1]), time.Hour, at, &dev); err != nil {
		t.Fatalf("device cookie: %v", err)
	}
	if dev["uid"] != float64(7) || dev["sv"] != float64(3) || len(dev["did"].(string)) != g.Cookies[0].DeviceDidLen {
		t.Fatalf("device payload %v", dev)
	}
	var last, action, detail, actor string
	var owner int64
	var actorID, impersonator *int64
	if err := pool.QueryRow(ctx, `SELECT last_login_at FROM user_account WHERE id = 7`).Scan(&last); err != nil || last != session.UTCNow(at) {
		t.Fatalf("last_login_at %q %v", last, err)
	}
	if err := pool.QueryRow(ctx, `SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id FROM audit`).
		Scan(&action, &detail, &actor, &owner, &actorID, &impersonator); err != nil {
		t.Fatal(err)
	}
	if action != "two_factor_login" || detail != "method=link+totp" || actor != "host7" || owner != 7 || actorID != nil || impersonator != nil {
		t.Fatalf("audit %q %q %q %d %v %v", action, detail, actor, owner, actorID, impersonator)
	}

	// Passkey shape: startSession returns the Location and writes no status.
	r = httptest.NewRequest("POST", "/login/passkey/finish", nil)
	r.Header.Set("Cookie", "ubyhost_lang=cs")
	w = httptest.NewRecorder()
	loc, err := d.startSession(w, r, account, true, "//evil.example", MethodPasskey(5), ActionLogin, at)
	if err != nil || loc != "/" || len(w.Header().Values("Set-Cookie")) != 2 || w.Header().Get("Location") != "" {
		t.Fatalf("startSession: %q %v %v", loc, err, w.Header())
	}

	// A write that fails (the audit table is gone) sets no cookie.
	if _, err := pool.Exec(ctx, `ALTER TABLE audit RENAME TO audit_gone`); err != nil {
		t.Fatal(err)
	}
	w = httptest.NewRecorder()
	if err := d.finishLogin(w, r, account, false, "/", MethodLink, ActionLogin, at); err == nil {
		t.Fatal("no error without the audit table")
	}
	if len(w.Header().Values("Set-Cookie")) != 0 || w.Header().Get("Location") != "" {
		t.Fatalf("headers after a failed write: %v", w.Header())
	}
}
