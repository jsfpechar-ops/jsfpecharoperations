package auth

// The signed-out style page shell of App/app/templates/auth_base.html for the
// account pages of briefs 1505 and 1506 (account_accept, two_factor_setup,
// two_factor_recovery, account_email_confirm). layout.Render draws the host
// shell (host_page.html) only, so these pages carry their own copy of
// auth_base.html: language form, env banner, ?notice= line, the "not you"
// form for a signed-in visitor, footer links and the hero panel. The context
// is templating.render()'s for a page that is not in seo.INDEXABLE_PATHS:
// no canonical or hreflang links and no analytics tag.
//
// The templates run under text/template with explicit escaping (acctView.E
// and T escape as markupsafe does), so the output matches Jinja's byte for
// byte and an otpauth: link is kept as Jinja keeps it (html/template would
// replace it with #ZgotmplZ). Every value that reaches a template goes
// through E or T; Check and Raw are trusted markup only.

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"net/http"
	"strings"
	"text/template"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

//go:embed acct_i18n.json
var acctCatalogJSON []byte

// acctCatalog holds every host string the account pages and their
// redirects raise, written from host_i18n.STRINGS by
// App/scripts/auth_account_golden.py from acct_i18n_keys.txt.
var acctCatalog = hostweb.Load(acctCatalogJSON)

//go:embed acct_templates/*.tmpl
var acctFS embed.FS

var acctTemplates = template.Must(template.New("acct").ParseFS(acctFS, "acct_templates/*.tmpl"))

// acctSendNow is mail.SendNow; the golden test records the ids instead.
var acctSendNow = mail.SendNow

// acctBackground runs f once the answer is on its way, as Starlette runs a
// BackgroundTask; the golden test runs it inline.
var acctBackground = func(f func()) { go f() }

const (
	acctCSRFCookie = "ubyhost_csrf" // security.CSRF_COOKIE
	acctCSRFMaxAge = 30 * 24 * 60 * 60
	acctCSRFSalt   = "ubyhost-csrf"
	// acctCheckIcon is icon('check', 14) from _icons.html.
	acctCheckIcon = `<svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-icon="check"><path d="M20 6 9 17l-5-5"/></svg>`
)

// acctNoticeKeys is auth_base.html's auth_notice_keys.
var acctNoticeKeys = map[string]string{
	"2fa_expired":   "auth.notice.2fa_expired",
	"form_expired":  "auth.notice.form_expired",
	"logged_out":    "auth.notice.logged_out",
	"email_changed": "auth.notice.email_changed",
}

// acctPage is what a handler gives acctRender.
type acctPage struct {
	Name         string // the template, e.g. "account_accept"
	TitleKey     string // the {% block title %} key
	Status       int    // 0 is 200
	LangNext     string // {% set lang_next %}; "" is the request path and query
	NoLangSwitch bool   // {% block lang_switch %}{% endblock %}
	SignedIn     bool   // current_user is set
	Data         any    // the page's own context, read as .Page in the template
}

// acctView is the template data: the auth_base.html context plus the page's.
type acctView struct {
	Lang, CSRF, Title, Next, Notice, OperatorEmail string
	SignedIn, LangSwitch, Mock, MockProduction     bool
	Page                                           any
}

// acctEscape is markupsafe.escape for a plain string.
var acctEscape = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&#34;", "'", "&#39;")

// T is {{ t(key, name=value, ...) }}: the text in the page language, escaped.
// kv are name, value pairs; a value is a string or an int.
func (v *acctView) T(key string, kv ...any) string {
	var params map[string]any
	if len(kv) > 1 {
		params = map[string]any{}
		for i := 0; i+1 < len(kv); i += 2 {
			if name, ok := kv[i].(string); ok {
				params[name] = kv[i+1]
			}
		}
	}
	return acctEscape.Replace(acctCatalog.T(v.Lang, key, params))
}

// E is {{ value }}: a plain value, escaped.
func (v *acctView) E(s string) string { return acctEscape.Replace(s) }

// Check is {{ icon('check', 14) }}.
func (v *acctView) Check() string { return acctCheckIcon }

// On is {{ 'is-active' if lang == code }}.
func (v *acctView) On(code string) string {
	if v.Lang == code {
		return "is-active"
	}
	return ""
}

// acctSupported is host_i18n.supported_language.
func acctSupported(v string) string {
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

// acctLang is templating.render's language for a page outside the public
// list: ?lang=, then the ubyhost_lang cookie, else English for a signed-in
// host and Czech for a visitor.
func acctLang(r *http.Request, signedIn bool) string {
	for _, v := range []string{acctLastQuery(r, "lang"), hostweb.Cookie(r, langCookieName)} {
		if l := acctSupported(v); l != "" {
			return l
		}
	}
	if signedIn {
		return hostweb.DefaultLanguage
	}
	return publicDefaultLanguage
}

// acctCSRFToken is security.csrf_token plus attach_csrf_cookie, as
// layout.csrfToken: a token bound to the ubyhost_csrf nonce cookie; a request
// without the cookie gets a new nonce and the cookie to set.
func acctCSRFToken(r *http.Request, secret string, getenv func(string) string, now time.Time) (string, *http.Cookie, error) {
	nonce := hostweb.Cookie(r, acctCSRFCookie)
	var cookie *http.Cookie
	if nonce == "" {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return "", nil, err
		}
		nonce = base64.RawURLEncoding.EncodeToString(buf)
		cookie = &http.Cookie{Name: acctCSRFCookie, Value: nonce, Path: "/", MaxAge: acctCSRFMaxAge,
			HttpOnly: true, SameSite: http.SameSiteStrictMode, Secure: hostweb.SecureCookies(getenv)}
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(secret, acctCSRFSalt).Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	return token, cookie, err
}

// acctEnvOr is os.environ.get(key, def) for a value read as given.
func acctEnvOr(getenv func(string) string, key, def string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return def
}

// acctRender is render(request, "<name>.html", context, status_code) for an
// auth_base.html page: the page, the ubyhost_lang cookie when ?lang= names a
// language the cookie does not hold, and the CSRF nonce cookie when the
// request had none. Nothing is written when it returns an error.
func (d deps) acctRender(w http.ResponseWriter, r *http.Request, p acctPage, at time.Time) error {
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		return err
	}
	token, csrfCookie, err := acctCSRFToken(r, secret, d.getenv, at)
	if err != nil {
		return err
	}
	v := &acctView{
		Lang:           acctLang(r, p.SignedIn),
		CSRF:           token,
		Next:           p.LangNext,
		Notice:         acctNoticeKeys[acctLastQuery(r, "notice")],
		OperatorEmail:  acctOperatorEmail(d.getenv),
		SignedIn:       p.SignedIn,
		LangSwitch:     !p.NoLangSwitch,
		Mock:           strings.ToLower(acctEnvOr(d.getenv, "UBYHOST_UBYPORT_ENV", "mock")) == "mock",
		MockProduction: strings.ToLower(acctEnvOr(d.getenv, "UBYHOST_DEPLOYMENT", "local")) == "production",
		Page:           p.Data,
	}
	v.Title = v.T(p.TitleKey)
	if v.Next == "" {
		v.Next = r.URL.Path
		if r.URL.RawQuery != "" {
			v.Next += "?" + r.URL.RawQuery
		}
	}
	var buf bytes.Buffer
	if err := acctTemplates.ExecuteTemplate(&buf, p.Name, v); err != nil {
		return err
	}
	if asked := acctSupported(acctLastQuery(r, "lang")); asked != "" && hostweb.Cookie(r, langCookieName) != asked {
		http.SetCookie(w, &http.Cookie{Name: langCookieName, Value: asked, Path: "/", MaxAge: langCookieMaxAge,
			SameSite: http.SameSiteLaxMode, Secure: strings.HasPrefix(strings.ToLower(hostweb.PublicBase(d.getenv)), "https://")})
	}
	if csrfCookie != nil {
		http.SetCookie(w, csrfCookie)
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	status := p.Status
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	_, _ = w.Write(buf.Bytes()) // the status is sent: a failed write is the client's
	return nil
}

// acctOperatorEmail is config.OPERATOR_EMAIL (operator().email).
func acctOperatorEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL")); v != "" {
		return v
	}
	return "support@ubyhost.com"
}

// acctLastQuery is request.query_params.get(key): the last value, or "".
func acctLastQuery(r *http.Request, key string) string {
	vals := r.URL.Query()[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}
