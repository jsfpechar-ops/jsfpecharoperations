package authpage

import (
	"io/fs"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"
)

var keyRE = regexp.MustCompile(`\{\{t "([^"]+)"`)

// TestTemplateKeysInCatalog: every literal key a page prints has an English
// and a Czech text in i18n.json, so a key missing from i18n_keys.txt fails here
// and not as a raw key on the page.
func TestTemplateKeysInCatalog(t *testing.T) {
	files, err := fs.Glob(templateFS, "templates/*.html")
	if err != nil || len(files) == 0 {
		t.Fatal("no templates")
	}
	n := 0
	for _, f := range files {
		raw, err := fs.ReadFile(templateFS, f)
		if err != nil {
			t.Fatal(err)
		}
		for _, m := range keyRE.FindAllStringSubmatch(string(raw), -1) {
			n++
			for _, lang := range []string{"en", "cs"} {
				if Strings[lang][m[1]] == "" {
					t.Errorf("%s: %s has no %s text", f, m[1], lang)
				}
			}
		}
	}
	if n < 50 {
		t.Errorf("only %d keys found", n)
	}
}

// TestEveryPageHasTitle: Render refuses a page without its title slot.
func TestEveryPageHasTitle(t *testing.T) {
	for _, name := range []string{"login", "login_sent", "login_link", "two_factor_login"} {
		if master.Lookup(name) == nil || master.Lookup(name+".title") == nil {
			t.Errorf("page %s or its title is missing", name)
		}
	}
	env := Env{Getenv: testEnv(nil), Now: time.Now()}
	rec := httptest.NewRecorder()
	if err := Render(rec, httptest.NewRequest("GET", "/login", nil), env, nil, "nope", nil, 0); err == nil {
		t.Error("unknown page rendered")
	}
	if rec.Code != http.StatusOK || rec.Body.Len() != 0 || len(rec.Result().Cookies()) != 0 {
		t.Error("a refused page wrote to the response")
	}
}

func testEnv(extra map[string]string) func(string) string {
	env := map[string]string{"UBYHOST_SECRET_KEY": "authpage-test-secret-0123456789-abcdef"}
	for k, v := range extra {
		env[k] = v
	}
	return func(k string) string { return env[k] }
}

func TestLanguage(t *testing.T) {
	for _, c := range []struct {
		query, cookie string
		signedIn      bool
		want          string
	}{
		{"", "", false, "cs"},
		{"", "", true, "en"},
		{"lang=vi", "", false, "vi"},
		{"lang=en&lang=VI-x", "cs", false, "vi"},
		{"lang=xx", "en", false, "en"},
		{"", "vi", true, "vi"},
	} {
		r := httptest.NewRequest("GET", "/login?"+c.query, nil)
		if c.cookie != "" {
			r.AddCookie(&http.Cookie{Name: LangCookie, Value: c.cookie})
		}
		if got := Language(r, c.signedIn); got != c.want {
			t.Errorf("%q %q %v: %s, want %s", c.query, c.cookie, c.signedIn, got, c.want)
		}
	}
}

// TestRenderCookiesAndHead: a visitor without a nonce gets the CSRF cookie
// after the language cookie; the language switch keeps the query; /login is
// indexable, /login/link is not.
func TestRenderCookiesAndHead(t *testing.T) {
	env := Env{Getenv: testEnv(map[string]string{"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.test/"}), Now: time.Now()}
	rec := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/login?lang=en&a=1", nil)
	if err := Render(rec, r, env, nil, "login", LoginData{Next: "/x"}, http.StatusTeapot); err != nil {
		t.Fatal(err)
	}
	res := rec.Result()
	cookies := res.Cookies()
	if res.StatusCode != http.StatusTeapot || len(cookies) != 2 || cookies[0].Name != LangCookie || cookies[0].Value != "en" ||
		!cookies[0].Secure || cookies[1].Name != csrfCookieName || !cookies[1].HttpOnly || !cookies[1].Secure {
		t.Fatalf("status %d cookies %+v", res.StatusCode, cookies)
	}
	body := rec.Body.String()
	for _, want := range []string{
		`<html lang="en">`, `<link rel="canonical" href="https://ubyhost.test/login?lang=en">`,
		`name="next" value="/login?lang=en&amp;a=1"`, `name="next" value="/x"`, `data-passkey-login`,
		`autocomplete="email webauthn"`, `/static/passkeys.js`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("page lacks %s", want)
		}
	}
	rec = httptest.NewRecorder()
	r = httptest.NewRequest("GET", "/login/link?t=x", nil)
	r.AddCookie(&http.Cookie{Name: csrfCookieName, Value: "nonce"})
	if err := Render(rec, r, env, nil, "login_link", LoginLinkData{Expired: true}, 0); err != nil {
		t.Fatal(err)
	}
	body = rec.Body.String()
	if len(rec.Result().Cookies()) != 0 || strings.Contains(body, "canonical") || !strings.Contains(body, `name="next" value="/login"`) ||
		!strings.Contains(body, `href="/login?lang=cs"`) || strings.Contains(body, "t=x") {
		t.Errorf("link page: cookies %v", rec.Result().Cookies())
	}
}
