package auth

// The end of every successful login, ported from App/app/routes/admin_accounts.py
// _finish_login and _keep_login_language (brief 1501). No route uses it yet:
// the login, 2FA, passkey and sign-up briefs (1502-1513) call it.

import (
	"net/http"
	"path"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	// langCookieName and langCookieMaxAge are host_i18n.LANG_COOKIE and
	// LANG_COOKIE_MAX_AGE (180 days).
	langCookieName   = "ubyhost_lang"
	langCookieMaxAge = 60 * 60 * 24 * 180
	// publicDefaultLanguage is host_i18n.PUBLIC_DEFAULT_LANGUAGE: the language
	// of a signed-out page that no ?lang= or cookie names.
	publicDefaultLanguage = "cs"
)

// Login methods and audit actions the callers of startSession pass, as
// Python writes them into audit.detail ("method=<m>") and audit.action.
const (
	MethodLink            = "link"
	MethodLinkTOTP        = "link+totp"
	MethodStagingPassword = "staging_password"
	ActionLogin           = "login"
	ActionTwoFactorLogin  = "two_factor_login"
)

// MethodPasskey is the method of a passkey login: "passkey:<passkey id>".
func MethodPasskey(passkeyID int64) string { return "passkey:" + itoa(passkeyID) }

// startSession is _finish_login without the redirect: it records the login
// (user_account.last_login_at, then the audit row action with detail
// "method=<method>", actor the username, owner the account, no actor id),
// then sets, in Python's order, a fresh ubyhost_session cookie
// (issue_session(id, session_version, remember) and attach_session), a new
// ubyhost_device cookie (attach_device) and, when it differs, the
// ubyhost_lang cookie (_keep_login_language). It returns the Location
// _finish_login redirects to: safe_local_path(nextPath, "/") as Starlette's
// RedirectResponse quotes it. On an error nothing has been written to w.
//
// The database writes come first so that a failure leaves no cookie behind;
// Python builds the response first but discards it when a write raises, so
// the browser sees the same 500 either way.
func (d deps) startSession(w http.ResponseWriter, r *http.Request, account *session.LoginAccount,
	remember bool, nextPath, method, action string, at time.Time) (string, error) {
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		return "", err
	}
	token, err := session.IssueSession(secret, account.ID, account.SessionVersion, session.IssueOptions{Remember: remember}, at)
	if err != nil {
		return "", err
	}
	device, err := session.DeviceToken(secret, account.ID, account.SessionVersion, session.NewDeviceID(), at)
	if err != nil {
		return "", err
	}
	ctx := r.Context()
	if _, err := d.pool.Exec(ctx, `UPDATE user_account SET last_login_at = $1 WHERE id = $2`,
		session.UTCNow(at), account.ID); err != nil {
		return "", err
	}
	if err := d.audit(ctx, nil, at, action, "method="+method, account.Username, ptr(account.ID)); err != nil {
		return "", err
	}
	secureCookie := hostweb.SecureCookies(d.getenv)
	http.SetCookie(w, session.SessionCookie(token, remember, secureCookie))
	http.SetCookie(w, session.DeviceCookie(device, secureCookie))
	keepLoginLanguage(w, r, d.getenv)
	return locationQuote(safeLocalPath(nextPath, "/")), nil
}

// finishLogin is _finish_login: startSession, then a 303 to its Location.
func (d deps) finishLogin(w http.ResponseWriter, r *http.Request, account *session.LoginAccount,
	remember bool, nextPath, method, action string, at time.Time) error {
	location, err := d.startSession(w, r, account, remember, nextPath, method, action, at)
	if err != nil {
		return err
	}
	redirect(w, location)
	return nil
}

// loginLanguage is the language _keep_login_language resolves on a POST that
// rendered nothing yet (request.state.lang is unset on every caller):
// resolve_language(request, default=PUBLIC_DEFAULT_LANGUAGE), that is the
// last ?lang=, then the ubyhost_lang cookie, each through supported_language,
// else Czech.
func loginLanguage(r *http.Request) string {
	query := ""
	if vals := r.URL.Query()["lang"]; len(vals) > 0 {
		query = vals[len(vals)-1]
	}
	for _, v := range []string{query, hostweb.Cookie(r, langCookieName)} {
		if lang := supportedLanguage(v); lang != "" {
			return lang
		}
	}
	return publicDefaultLanguage
}

// supportedLanguage is host_i18n.supported_language: the first two
// characters of the stripped, lower-cased value when the app speaks them.
func supportedLanguage(v string) string {
	code := []rune(strings.ToLower(pyStrip(v)))
	if len(code) > 2 {
		code = code[:2]
	}
	switch s := string(code); s {
	case "en", "cs", "vi":
		return s
	}
	return ""
}

// keepLoginLanguage is _keep_login_language: carry the login page's language
// into the signed-in pages, which would otherwise fall back to English. The
// cookie is set only when the request's ubyhost_lang differs (a missing
// cookie always differs). remember_language marks it Secure on an https
// public base URL only (not on "production" alone, unlike the session).
func keepLoginLanguage(w http.ResponseWriter, r *http.Request, getenv func(string) string) {
	lang := loginLanguage(r)
	if c, err := r.Cookie(langCookieName); err == nil && c.Value == lang {
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     langCookieName,
		Value:    lang,
		Path:     "/",
		MaxAge:   langCookieMaxAge,
		SameSite: http.SameSiteLaxMode,
		Secure:   strings.HasPrefix(strings.ToLower(hostweb.PublicBase(getenv)), "https://"),
	})
}

// safeLocalPath is security.safe_local_path: a normalised same-site path with
// its query (the fragment dropped), or def for unsafe input. Copied from
// go/internal/web/properties/localpath.go, which this package cannot import.
// (Python raises ValueError for a few malformed "//[" hosts; Go answers def.)
func safeLocalPath(value, def string) string {
	raw := pyStrip(value)
	if raw == "" || hasControl(raw) || strings.Contains(raw, "\\") {
		return def
	}
	if !strings.HasPrefix(raw, "/") {
		return def
	}
	// urlsplit reads "//" as the start of a host: "///x" has an empty host and
	// the path "/x", while "//host/x", "//" and "//?q" are refused.
	if strings.HasPrefix(raw, "//") {
		raw = raw[2:]
		if !strings.HasPrefix(raw, "/") {
			return def
		}
	}
	p, query := raw, ""
	if i := strings.IndexByte(p, '#'); i >= 0 {
		p = p[:i]
	}
	if i := strings.IndexByte(p, '?'); i >= 0 {
		p, query = p[:i], p[i+1:]
	}
	decoded := pyUnquote(p)
	if strings.HasPrefix(decoded, "//") || strings.Contains(decoded, "\\") || hasControl(decoded) {
		return def
	}
	clean := path.Clean(p)
	if !strings.HasPrefix(clean, "/") || strings.HasPrefix(clean, "//") {
		return def
	}
	if query != "" {
		return clean + "?" + query
	}
	return clean
}

func hasControl(s string) bool {
	for _, r := range s {
		if r < 0x20 {
			return true
		}
	}
	return false
}

// pyUnquote is urllib.parse.unquote: %XX sequences become bytes, read as
// UTF-8 with U+FFFD for bad bytes; a bad sequence such as "%zz" stays.
func pyUnquote(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	var b []byte
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && isHex(s[i+1]) && isHex(s[i+2]) {
			b = append(b, hexVal(s[i+1])<<4|hexVal(s[i+2]))
			i += 2
			continue
		}
		b = append(b, s[i])
	}
	return strings.ToValidUTF8(string(b), "\uFFFD")
}

func isHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

func hexVal(c byte) byte {
	switch {
	case c >= 'a':
		return c - 'a' + 10
	case c >= 'A':
		return c - 'A' + 10
	}
	return c - '0'
}

// locationQuote is Starlette RedirectResponse's
// quote(url, safe=":/%#?=@[]!$&'()*+,;"): ASCII letters, digits, "_.-~" and
// the safe set stay, every other UTF-8 byte becomes %XX.
func locationQuote(s string) string {
	const hexDigits = "0123456789ABCDEF"
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9':
			b.WriteByte(c)
		case strings.IndexByte("_.-~:/%#?=@[]!$&'()*+,;", c) >= 0:
			b.WriteByte(c)
		default:
			b.WriteByte('%')
			b.WriteByte(hexDigits[c>>4])
			b.WriteByte(hexDigits[c&15])
		}
	}
	return b.String()
}
