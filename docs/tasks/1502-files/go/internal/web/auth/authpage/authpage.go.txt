// Package authpage renders the signed-out account pages (login, login link,
// 2FA code and the later sign-up and account pages) inside the port of
// App/app/templates/auth_base.html. hostweb/layout.Render only knows the host
// shell (base.html), which these pages do not use (brief 1502).
//
// A page is templates/<name>.html. It defines {{define "<name>"}} (the
// auth_body block) and the slots "<name>.title" (the <title> text, required),
// "<name>.meta" (meta_description) and "<name>.lang_next" (the language
// switch's next, default the request path and query). The slots run with the
// same Page value as the body; their output is text.
//
// CSRF: a form takes its token from .CSRF; Render binds it to the
// ubyhost_csrf nonce cookie exactly as hostweb/layout does.
package authpage

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	stdhtml "html"
	"html/template"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
)

//go:embed i18n.json
var catalogJSON []byte

//go:embed templates/*.html
var templateFS embed.FS

// Strings is the pages' catalog, written from host_i18n.STRINGS by
// App/scripts/go_host_i18n.py from i18n_keys.txt.
var Strings = hostweb.Load(catalogJSON)

var master = template.Must(template.New("authpage").Funcs(funcs("en")).ParseFS(templateFS, "templates/*.html"))

// Env is what Render reads besides the request.
type Env struct {
	Getenv func(string) string
	Now    time.Time
}

// Page is the value every page template and slot runs with.
type Page struct {
	Lang          string // the page language (en, cs, vi)
	CSRF          string // the form token
	SiteKey       string // turnstile_site_key: set when Turnstile is configured
	Passkeys      bool   // passkeys_enabled()
	OperatorEmail string // operator().email
	SignedIn      bool   // current_user is set
	Data          any    // the page's own values
}

type alternate struct{ Code, Href string }

type view struct {
	Lang, CSRF, Title, MetaDescription string
	Canonical                          string
	Alternates                         []alternate
	LangNext, Notice, OperatorEmail    string
	UbyportMock, ProductionMock        bool
	SignedIn                           bool
	Body                               template.HTML
}

// noticeKeys is auth_base.html's auth_notice_keys (?notice=).
var noticeKeys = map[string]string{
	"2fa_expired":   "auth.notice.2fa_expired",
	"form_expired":  "auth.notice.form_expired",
	"logged_out":    "auth.notice.logged_out",
	"email_changed": "auth.notice.email_changed",
}

// indexablePaths is seo.INDEXABLE_PATHS (the same list as hostweb/layout).
var indexablePaths = map[string]bool{
	"/": true, "/login": true, "/legal": true, "/terms": true, "/privacy": true, "/dpa": true,
	"/subprocessors": true, "/jak-to-funguje": true, "/cenik": true,
	"/pruvodce/hlaseni-cizincu-ubyport": true, "/pruvodce/online-ubytovaci-kniha": true,
}

// Render is templating.render for a page that extends auth_base.html, plus
// what the middleware adds to it: it writes the ubyhost_lang cookie when
// ?lang= names a new language (remember_language), the ubyhost_csrf nonce
// cookie when the request has none (attach_csrf_cookie) and, for a signed-in
// host, the sliding refresh of a remember-me session (refresh_session_cookie),
// in that order, then the page with status (0 is 200). host is current_user:
// nil for a visitor. Nothing is written when it returns an error.
func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, name string, data any, status int) error {
	if master.Lookup(name) == nil || master.Lookup(name+".title") == nil {
		return fmt.Errorf("authpage: no page %q", name)
	}
	secret, err := secure.LoadSecret(env.Getenv)
	if err != nil {
		return err
	}
	token, csrfCookie, err := csrfToken(r, secret, env.Getenv, env.Now)
	if err != nil {
		return err
	}
	var refresh *http.Cookie
	if host != nil {
		if refresh, err = session.RefreshSession(secret, host.Payload, w.Header(), hostweb.SecureCookies(env.Getenv), env.Now); err != nil {
			return err
		}
	}
	lang := Language(r, host != nil)
	page := Page{
		Lang: lang, CSRF: token, SiteKey: turnstile.PageSiteKey(env.Getenv),
		Passkeys: PasskeysAvailable(env.Getenv), OperatorEmail: OperatorEmail(env.Getenv),
		SignedIn: host != nil, Data: data,
	}
	out, err := execute(r, env.Getenv, lang, name, page)
	if err != nil {
		return err
	}
	if asked := supportedLanguage(lastQuery(r, "lang")); asked != "" && hostweb.Cookie(r, LangCookie) != asked {
		http.SetCookie(w, LanguageCookie(asked, env.Getenv))
	}
	if csrfCookie != nil {
		http.SetCookie(w, csrfCookie)
	}
	if refresh != nil {
		http.SetCookie(w, refresh)
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	_, err = w.Write(out)
	return err
}

// execute runs the page and its slots, then the base, on a clone that speaks lang.
func execute(r *http.Request, getenv func(string) string, lang, name string, page Page) ([]byte, error) {
	clone, err := master.Clone()
	if err != nil {
		return nil, err
	}
	clone.Funcs(funcs(lang))
	slot := func(suffix string) (string, bool, error) {
		t := clone.Lookup(name + suffix)
		if t == nil {
			return "", false, nil
		}
		var b bytes.Buffer
		if err := t.Execute(&b, page); err != nil {
			return "", true, err
		}
		return b.String(), true, nil
	}
	body, _, err := slot("")
	if err != nil {
		return nil, err
	}
	v := view{
		Lang: lang, CSRF: page.CSRF, OperatorEmail: page.OperatorEmail, SignedIn: page.SignedIn,
		Body: template.HTML(body),
	}
	for _, s := range []struct {
		suffix string
		dst    *string
	}{{".title", &v.Title}, {".meta", &v.MetaDescription}, {".lang_next", &v.LangNext}} {
		text, _, err := slot(s.suffix)
		if err != nil {
			return nil, err
		}
		*s.dst = strings.TrimSpace(stdhtml.UnescapeString(text))
	}
	if _, defined, _ := slot(".lang_next"); !defined {
		v.LangNext = r.URL.Path
		if r.URL.RawQuery != "" {
			v.LangNext += "?" + r.URL.RawQuery
		}
	}
	v.Notice = noticeKeys[lastQuery(r, "notice")]
	env := strings.ToLower(getenvOr(getenv, "UBYHOST_UBYPORT_ENV", "mock"))
	v.UbyportMock = env == "mock"
	v.ProductionMock = strings.ToLower(getenvOr(getenv, "UBYHOST_DEPLOYMENT", "local")) == "production"
	if indexablePaths[r.URL.Path] {
		base := hostweb.PublicBase(getenv) + r.URL.Path
		v.Canonical = base
		if asked := supportedLanguage(lastQuery(r, "lang")); asked == "en" || asked == "cs" {
			v.Canonical = base + "?lang=" + asked
		}
		v.Alternates = []alternate{{"en", base + "?lang=en"}, {"cs", base + "?lang=cs"}, {"x-default", base}}
	}
	var out bytes.Buffer
	if err := clone.ExecuteTemplate(&out, "authpage.base", v); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

// funcs are the template funcs: t is the template global t (host_i18n.translate
// in the page language) with its keyword arguments as name, value pairs.
func funcs(lang string) template.FuncMap {
	return template.FuncMap{
		"t": func(key string, kv ...any) (string, error) {
			if len(kv)%2 != 0 {
				return "", fmt.Errorf("authpage: t %q: odd arguments", key)
			}
			var params map[string]any
			if len(kv) > 0 {
				params = map[string]any{}
				for i := 0; i < len(kv); i += 2 {
					k, ok := kv[i].(string)
					if !ok {
						return "", fmt.Errorf("authpage: t %q: argument name", key)
					}
					params[k] = kv[i+1]
				}
			}
			return Strings.T(lang, key, params), nil
		},
	}
}

// LangCookie is host_i18n.LANG_COOKIE; langCookieMaxAge is LANG_COOKIE_MAX_AGE (180 days).
const (
	LangCookie       = "ubyhost_lang"
	langCookieMaxAge = 60 * 60 * 24 * 180
)

// LanguageCookie is host_i18n.remember_language: not HttpOnly, Lax, Secure on
// an https public base URL only.
func LanguageCookie(lang string, getenv func(string) string) *http.Cookie {
	return &http.Cookie{
		Name:     LangCookie,
		Value:    lang,
		Path:     "/",
		MaxAge:   langCookieMaxAge,
		SameSite: http.SameSiteLaxMode,
		Secure:   strings.HasPrefix(strings.ToLower(hostweb.PublicBase(getenv)), "https://"),
	}
}

// Language is the page language templating.render resolves: the last ?lang=,
// then the ubyhost_lang cookie, each through supported_language, else English
// for a signed-in host and Czech for a visitor. None of these paths is a
// public page, so Vietnamese stays.
func Language(r *http.Request, signedIn bool) string {
	for _, v := range []string{lastQuery(r, "lang"), hostweb.Cookie(r, LangCookie)} {
		if lang := supportedLanguage(v); lang != "" {
			return lang
		}
	}
	if signedIn {
		return "en"
	}
	return "cs"
}

// supportedLanguage is host_i18n.supported_language.
func supportedLanguage(v string) string {
	s := []rune(strings.ToLower(strings.TrimSpace(v)))
	if len(s) > 2 {
		s = s[:2]
	}
	switch string(s) {
	case "en", "cs", "vi":
		return string(s)
	}
	return ""
}

// lastQuery is Starlette's request.query_params.get: the last value of key.
func lastQuery(r *http.Request, key string) string {
	vals := r.URL.Query()[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}

func getenvOr(getenv func(string) string, key, def string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return def
}

// OperatorEmail is config.OPERATOR_EMAIL (operator().email).
func OperatorEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL")); v != "" {
		return v
	}
	return "support@ubyhost.com"
}

// PasskeysAvailable is passkeys.available(): a host name (not an IP) and
// HTTPS, or localhost (as hostweb/layout passkeysAvailable).
func PasskeysAvailable(getenv func(string) string) bool {
	u, err := url.Parse(hostweb.PublicBase(getenv))
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Hostname())
	if host == "" || isDigits(strings.ReplaceAll(host, ".", "")) || strings.Contains(host, ":") {
		return false
	}
	return strings.ToLower(u.Scheme) == "https" || host == "localhost"
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

// security.CSRF_COOKIE, CSRF_MAX_AGE and the serializer salt.
const (
	csrfCookieName = "ubyhost_csrf"
	csrfMaxAge     = 30 * 24 * 60 * 60
	csrfSalt       = "ubyhost-csrf"
)

// csrfToken is security.csrf_token plus attach_csrf_cookie (a copy of
// hostweb/layout csrfToken, which is not exported): the token is bound to the
// ubyhost_csrf nonce cookie; a request without one gets a new nonce and the
// cookie to set.
func csrfToken(r *http.Request, secret string, getenv func(string) string, now time.Time) (string, *http.Cookie, error) {
	nonce := hostweb.Cookie(r, csrfCookieName)
	var cookie *http.Cookie
	if nonce == "" {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return "", nil, err
		}
		nonce = base64.RawURLEncoding.EncodeToString(buf)
		cookie = &http.Cookie{
			Name:     csrfCookieName,
			Value:    nonce,
			Path:     "/",
			MaxAge:   csrfMaxAge,
			HttpOnly: true,
			SameSite: http.SameSiteStrictMode,
			Secure:   hostweb.SecureCookies(getenv),
		}
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(secret, csrfSalt).Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	if err != nil {
		return "", nil, err
	}
	return token, cookie, nil
}
