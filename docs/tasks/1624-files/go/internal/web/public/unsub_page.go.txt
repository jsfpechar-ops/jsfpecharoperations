package public

// GET and POST /mail/unsubscribe/{token} (brief 1624), ported from
// App/app/routes/mail_unsubscribe.py, templates/mail_unsubscribe.html and the
// auth_base.html shell. Public and without a login: the signed token in the
// path is the only credential. GET only shows the page with one button, so a
// link scanner cannot unsubscribe anyone; POST unsubscribes. The page loads no
// analytics and no outside script (it is not on analytics.PUBLIC_ANALYTICS_TEMPLATES).

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"text/template"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

//go:embed catalog_unsub.json
var unsubJSON []byte

//go:embed templates/unsub/*.tmpl
var unsubFS embed.FS

type unsubCatalog struct {
	Strings   hostweb.Catalog `json:"strings"`
	CheckIcon string          `json:"check_icon"`
}

var ucat = func() unsubCatalog {
	var c unsubCatalog
	if err := json.Unmarshal(unsubJSON, &c); err != nil {
		panic("public: bad catalog_unsub.json: " + err.Error())
	}
	return c
}()

var unsubTmpl = template.Must(template.New("unsubscribe.tmpl").ParseFS(unsubFS, "templates/unsub/*.tmpl"))

// UnsubDeps are the outside inputs of the two handlers. Now nil means time.Now.
type UnsubDeps struct {
	Pool     *pgxpool.Pool
	Getenv   func(string) string
	SignedIn func(*http.Request) bool
	Now      func() time.Time
}

const (
	csrfCookieName = "ubyhost_csrf" // security.CSRF_COOKIE
	csrfMaxAge     = 30 * 24 * 60 * 60
	csrfSalt       = "ubyhost-csrf"
)

// noticeKeys is auth_base.html's auth_notice_keys.
var noticeKeys = map[string]string{
	"2fa_expired":   "auth.notice.2fa_expired",
	"form_expired":  "auth.notice.form_expired",
	"logged_out":    "auth.notice.logged_out",
	"email_changed": "auth.notice.email_changed",
}

// up is the data of one unsubscribe render.
type up struct {
	Lang, Token, Message, CSRF, Next, Notice string
	Done, SignedIn, Mock, MockProduction     bool
	OperatorEmail                            string
}

func (p *up) tr(key string) string { return ucat.Strings.T(p.Lang, key, nil) }

// T is {{ t(key) }}: the translated text, escaped.
func (p *up) T(key string) string { return esc(p.tr(key)) }

// E is {{ value }}: a plain value, escaped.
func (p *up) E(v string) string { return esc(v) }

// Check is {{ icon('check', 14) }}.
func (p *up) Check() string { return ucat.CheckIcon }

// LangOn is {{ 'is-active' if lang == code }}.
func (p *up) LangOn(code string) string {
	if p.Lang == code {
		return "is-active"
	}
	return ""
}

// unsubLang is templating.render's language for a page outside the public
// list: ?lang=, then the ubyhost_lang cookie, each through supported_language
// (en, cs or vi), else English for a signed-in host and Czech for a visitor.
func unsubLang(r *http.Request, signedIn bool) string {
	for _, v := range []string{r.URL.Query().Get("lang"), hostweb.Cookie(r, langCookieName)} {
		if l := supportedLanguage(v); l != "" {
			return l
		}
	}
	if signedIn {
		return appDefault
	}
	return publicDefault
}

// csrfToken is security.csrf_token plus attach_csrf_cookie: a token bound to
// the ubyhost_csrf nonce cookie; a request without the cookie gets a new nonce
// and the cookie to set.
func csrfToken(r *http.Request, secret string, getenv func(string) string, now time.Time) (string, *http.Cookie, error) {
	nonce := hostweb.Cookie(r, csrfCookieName)
	var cookie *http.Cookie
	if nonce == "" {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return "", nil, err
		}
		nonce = base64.RawURLEncoding.EncodeToString(buf)
		cookie = &http.Cookie{Name: csrfCookieName, Value: nonce, Path: "/", MaxAge: csrfMaxAge,
			HttpOnly: true, SameSite: http.SameSiteStrictMode, Secure: hostweb.SecureCookies(getenv)}
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(secret, csrfSalt).Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	return token, cookie, err
}

func (d UnsubDeps) now() time.Time {
	if d.Now != nil {
		return d.Now()
	}
	return time.Now()
}

// page is mail_unsubscribe._page: the status picks the message key (404 and
// 429 only), as render() would, with the language cookie for a ?lang= link.
func (d UnsubDeps) page(w http.ResponseWriter, r *http.Request, token string, done bool, status int) {
	cfg := loadConfig(d.Getenv)
	secret, err := secure.LoadSecret(d.Getenv)
	if err != nil {
		log.Printf("unsubscribe: no secret key")
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	signedIn := d.SignedIn != nil && d.SignedIn(r)
	csrf, cookie, err := csrfToken(r, secret, d.Getenv, d.now())
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	p := &up{
		Lang: unsubLang(r, signedIn), Token: token, CSRF: csrf, Done: done, SignedIn: signedIn,
		Message:        map[int]string{404: "unsubscribe.invalid", 429: "unsubscribe.too_many"}[status],
		Next:           r.URL.Path,
		Notice:         noticeKeys[r.URL.Query().Get("notice")],
		OperatorEmail:  cfg.OpEmail,
		Mock:           strings.ToLower(orDefault(d.Getenv("UBYHOST_UBYPORT_ENV"), "mock")) == "mock",
		MockProduction: cfg.Deployment == "production",
	}
	if r.URL.RawQuery != "" {
		p.Next += "?" + r.URL.RawQuery
	}
	var buf bytes.Buffer
	if err := unsubTmpl.ExecuteTemplate(&buf, "unsubscribe.tmpl", p); err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	if asked := supportedLanguage(r.URL.Query().Get("lang")); asked != "" && hostweb.Cookie(r, langCookieName) != asked {
		http.SetCookie(w, &http.Cookie{Name: langCookieName, Value: asked, MaxAge: langCookieMaxAge, Path: "/",
			SameSite: http.SameSiteLaxMode, Secure: strings.HasPrefix(strings.ToLower(cfg.PublicBase), "https://")})
	}
	if cookie != nil {
		http.SetCookie(w, cookie)
	}
	w.WriteHeader(status)
	if r.Method != http.MethodHead {
		_, _ = w.Write(buf.Bytes())
	}
}

func orDefault(v, def string) string {
	if v == "" {
		return def
	}
	return v
}

func (d UnsubDeps) fail(w http.ResponseWriter, what string, err error) {
	log.Printf("unsubscribe %s: %v", what, err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// UnsubscribeForm is mail_unsubscribe_form (GET): rate limit first (a blocked
// address gets 429 and is not counted again), then count the view, then the
// page: 404 for a forged token or a missing account, else the button or, for
// an account that is already opted out, the confirmation.
func UnsubscribeForm(d UnsubDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, token, key, now := r.Context(), r.PathValue("token"), unsubKey(r), d.now()
		blocked, err := rateBlocked(ctx, d.Pool, key, now)
		if err != nil {
			d.fail(w, "rate limit", err)
			return
		}
		if blocked {
			d.page(w, r, token, false, http.StatusTooManyRequests)
			return
		}
		if err := rateRecord(ctx, d.Pool, key, now); err != nil {
			d.fail(w, "rate record", err)
			return
		}
		secret, err := secure.LoadSecret(d.Getenv)
		if err != nil {
			d.fail(w, "secret", err)
			return
		}
		id, _, ok := readUnsubscribeToken(secret, token)
		if ok {
			if ok, err = userExists(ctx, d.Pool, id); err != nil {
				d.fail(w, "user", err)
				return
			}
		}
		if !ok {
			d.page(w, r, token, false, http.StatusNotFound)
			return
		}
		done, err := optedOut(ctx, d.Pool, id)
		if err != nil {
			d.fail(w, "opt-out", err)
			return
		}
		d.page(w, r, token, done, http.StatusOK)
	}
}

// UnsubscribeSubmit is mail_unsubscribe_submit (POST). A valid token always
// works, with no rate check and no CSRF check (one-click posts come from the
// mailbox provider's servers, with no cookie); only a failed attempt is
// counted and, past the limit, answered 429.
func UnsubscribeSubmit(d UnsubDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, token, now := r.Context(), r.PathValue("token"), d.now()
		secret, err := secure.LoadSecret(d.Getenv)
		if err != nil {
			d.fail(w, "secret", err)
			return
		}
		if id, digest, ok := readUnsubscribeToken(secret, token); ok {
			done, err := unsubscribe(ctx, d.Pool, id, digest, now)
			if err != nil {
				d.fail(w, "unsubscribe", err)
				return
			}
			if done {
				d.page(w, r, token, true, http.StatusOK)
				return
			}
		}
		key := unsubKey(r)
		blocked, err := rateBlocked(ctx, d.Pool, key, now)
		if err != nil {
			d.fail(w, "rate limit", err)
			return
		}
		if blocked {
			d.page(w, r, token, false, http.StatusTooManyRequests)
			return
		}
		if err := rateRecord(ctx, d.Pool, key, now); err != nil {
			d.fail(w, "rate record", err)
			return
		}
		d.page(w, r, token, false, http.StatusNotFound)
	}
}
