package auth

// The sign-up pages' renderer (brief 1507): App/app/templates/signup.html,
// signup_sent.html and signup_verify.html on the auth_base.html shell, with
// the context templating.render gives a signed-out page. text/template with
// markupsafe's escaping (every value through E or T), so the bytes match
// Jinja's; App/scripts/signup_pages_golden.py records the Python pages.

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
	"text/template"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
)

//go:embed signup_catalog.json
var signupCatalogJSON []byte

//go:embed templates/signup/*.tmpl
var signupFS embed.FS

// signupCatalog holds the host strings of the four templates (every signup.*
// key and the shell's) and the check icon, written by signup_pages_golden.py.
var signupCatalog = func() struct {
	Strings   hostweb.Catalog `json:"strings"`
	CheckIcon string          `json:"check_icon"`
} {
	var c struct {
		Strings   hostweb.Catalog `json:"strings"`
		CheckIcon string          `json:"check_icon"`
	}
	if err := json.Unmarshal(signupCatalogJSON, &c); err != nil {
		panic("web/auth: bad signup_catalog.json: " + err.Error())
	}
	return c
}()

// signupTemplates is one set per page: the shell plus the page's blocks.
var signupTemplates = map[string]*template.Template{
	"signup.html":        signupParse("signup.tmpl"),
	"signup_sent.html":   signupParse("signup_sent.tmpl"),
	"signup_verify.html": signupParse("signup_verify.tmpl"),
}

func signupParse(page string) *template.Template {
	return template.Must(template.New("auth_base.tmpl").ParseFS(signupFS,
		"templates/signup/auth_base.tmpl", "templates/signup/"+page))
}

// signupEsc is markupsafe.escape: & < > " ' only.
var signupEsc = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&#34;", "'", "&#39;").Replace

// signupNoticeKeys is auth_base.html's auth_notice_keys.
var signupNoticeKeys = map[string]string{
	"2fa_expired":   "auth.notice.2fa_expired",
	"form_expired":  "auth.notice.form_expired",
	"logged_out":    "auth.notice.logged_out",
	"email_changed": "auth.notice.email_changed",
}

// signupConsentBox is one entry of _form_context's consent_boxes.
type signupConsentBox struct {
	Platform  string `json:"platform"`
	Field     string `json:"field"`
	Checked   bool   `json:"checked"`
	Text      string `json:"text"`
	LinkLabel string `json:"link_label"`
	LinkURL   string `json:"link_url"`
}

// signupView is the route's part of the context: what signup.py hands to
// render() for one of the three templates.
type signupView struct {
	Template string
	Status   int

	// signup.html (_form_context and again()).
	Attr           map[string]string
	Selection      [][2]string // signup_selection.clean order: plan, interval, ttlock, apartments
	Boxes          []signupConsentBox
	LangNext       string
	Error          string
	ErrorField     string
	Email          string // signup.html: the raw address; signup_sent.html: the normalised one
	Workspace      string
	MarketingOptIn bool

	// signup_verify.html.
	Token   string
	Expired bool
}

// signupPage is the whole template context.
type signupPage struct {
	V              signupView
	Lang           string
	CSRF           string
	Next           string // lang_next, or the path and query
	Notice         string
	SignedIn       bool
	Mock           bool
	MockProduction bool
	OperatorEmail  string
	SiteKey        string
}

// T is {{ t(key) }}, escaped.
func (p *signupPage) T(key string) string {
	return signupEsc(signupCatalog.Strings.T(p.Lang, key, nil))
}

// TP is {{ t(key, name=value) }}, escaped.
func (p *signupPage) TP(key, name, value string) string {
	return signupEsc(signupCatalog.Strings.T(p.Lang, key, map[string]any{name: value}))
}

// E is {{ value }}: escaped.
func (p *signupPage) E(v string) string { return signupEsc(v) }

// LangOn is {{ 'is-active' if lang == code }}.
func (p *signupPage) LangOn(code string) string {
	if p.Lang == code {
		return "is-active"
	}
	return ""
}

// Check is {{ icon('check', 14) }}.
func (p *signupPage) Check() string { return signupCatalog.CheckIcon }

// AttrHidden is the click and utm_* hidden fields, in the template's order.
func (p *signupPage) AttrHidden() [][2]string {
	var out [][2]string
	for _, k := range []string{"click", "utm_source", "utm_medium", "utm_campaign"} {
		if v := p.V.Attr[k]; v != "" {
			out = append(out, [2]string{k, v})
		}
	}
	return out
}

// signupPageLang is templating.render's language for these pages: the last
// ?lang=, then the ubyhost_lang cookie, each through supported_language, else
// English for a signed-in visitor and Czech for anyone else. None of the
// three paths is in seo.INDEXABLE_PATHS, so vi stays vi.
func signupPageLang(r *http.Request, signupSignedIn bool) string {
	if !signupSignedIn {
		return loginLanguage(r)
	}
	query := ""
	if vals := r.URL.Query()["lang"]; len(vals) > 0 {
		query = vals[len(vals)-1]
	}
	for _, v := range []string{query, hostweb.Cookie(r, langCookieName)} {
		if lang := supportedLanguage(v); lang != "" {
			return lang
		}
	}
	return hostweb.DefaultLanguage
}

// signupCSRFToken is security.csrf_token plus attach_csrf_cookie (the same as
// go/internal/hostweb/layout's unexported csrfToken): the token is bound to
// the ubyhost_csrf nonce cookie; a request without one gets a new nonce and
// the cookie to set.
func signupCSRFToken(r *http.Request, secret string, getenv func(string) string, now time.Time) (string, *http.Cookie, error) {
	nonce := hostweb.Cookie(r, "ubyhost_csrf")
	var cookie *http.Cookie
	if nonce == "" {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return "", nil, err
		}
		nonce = base64.RawURLEncoding.EncodeToString(buf)
		cookie = &http.Cookie{Name: "ubyhost_csrf", Value: nonce, Path: "/", MaxAge: 30 * 24 * 60 * 60,
			HttpOnly: true, SameSite: http.SameSiteStrictMode, Secure: hostweb.SecureCookies(getenv)}
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	return token, cookie, err
}

// renderSignup is templating.render(request, v.Template, context, v.Status)
// for a page on auth_base.html. Set-Cookie order is Python's: the language
// cookie (render) before the CSRF cookie (the middleware).
func renderSignup(w http.ResponseWriter, r *http.Request, getenv func(string) string, now time.Time, signupSignedIn bool, v signupView) error {
	tpl := signupTemplates[v.Template]
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return err
	}
	csrf, csrfCookie, err := signupCSRFToken(r, secret, getenv, now)
	if err != nil {
		return err
	}
	ubyport := strings.ToLower(getenv("UBYHOST_UBYPORT_ENV"))
	if ubyport == "" {
		ubyport = "mock"
	}
	operator := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL"))
	if operator == "" {
		operator = "support@ubyhost.com"
	}
	p := &signupPage{
		V:              v,
		Lang:           signupPageLang(r, signupSignedIn),
		CSRF:           csrf,
		Next:           v.LangNext,
		Notice:         signupNoticeKeys[signupQuery(r, "notice")],
		SignedIn:       signupSignedIn,
		Mock:           ubyport == "mock",
		MockProduction: turnstile.FromEnv(getenv).Deployment == "production",
		OperatorEmail:  operator,
		SiteKey:        turnstile.PageSiteKey(getenv),
	}
	if p.Next == "" {
		p.Next = r.URL.Path
		if r.URL.RawQuery != "" {
			p.Next += "?" + r.URL.RawQuery
		}
	}
	var buf bytes.Buffer
	if err := tpl.ExecuteTemplate(&buf, "auth_base.tmpl", p); err != nil {
		return err
	}
	if asked := supportedLanguage(signupQuery(r, "lang")); asked != "" && hostweb.Cookie(r, langCookieName) != asked {
		http.SetCookie(w, &http.Cookie{Name: langCookieName, Value: asked, Path: "/", MaxAge: langCookieMaxAge,
			SameSite: http.SameSiteLaxMode, Secure: strings.HasPrefix(strings.ToLower(hostweb.PublicBase(getenv)), "https://")})
	}
	if csrfCookie != nil {
		http.SetCookie(w, csrfCookie)
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	status := v.Status
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	_, err = w.Write(buf.Bytes())
	return err
}

// signupQuery is request.query_params.get(key): the last value, or "".
func signupQuery(r *http.Request, key string) string {
	vals := r.URL.Query()[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}
