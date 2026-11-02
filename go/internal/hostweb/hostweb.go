// Package hostweb is the host web gate shared by the Go routes: login, CSRF,
// language, flash redirects and the host string catalog. It ports
// App/app/auth.py (require_login), App/app/security.py (_require_csrf),
// App/app/routes/admin_helpers.py (back, _flash_message) and
// App/app/host_i18n.py (resolve_language, lookup). The Python files are the
// reference; each function names its source.
package hostweb

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// DefaultLanguage is host_i18n.DEFAULT_LANGUAGE.
const DefaultLanguage = "en"

// langCookie is host_i18n.LANG_COOKIE.
const langCookie = "ubyhost_lang"

// defaultBase is config.PUBLIC_BASE_URL's default.
const defaultBase = "http://127.0.0.1:8080"

// sessionMaxAge is the session cookie lifetime in seconds (SESSION_MAX_AGE, no "rm").
const sessionMaxAge = 12 * 60 * 60

// Flash is a translated message for a redirect, with the key it was raised
// under. Count is the number of accepted guests; only
// flash.reservations.accepted reads it.
type Flash struct {
	Text  string
	Key   string
	Count int
}

// successFlashKeys is _SUCCESS_FLASH_KEYS in admin_helpers.py.
var successFlashKeys = keySet(
	"flash.entities.added_first",
	"flash.entities.added",
	"flash.entities.saved",
	"flash.entities.restored",
	"flash.apartments.created",
	"flash.apartments.saved_ready",
	"flash.apartments.settings_saved",
	"flash.apartments.connection_ok",
	"flash.apartments.restored",
	"flash.reservations.created",
	"flash.reservations.saved",
	"flash.reservations.restored",
	"flash.guests.added",
	"flash.guests.saved",
	"flash.guests.saved_plain",
	"flash.housebook.restored",
	"flash.setup.complete",
)

// stickyWarningFlashKeys is _STICKY_WARNING_FLASH_KEYS in admin_helpers.py.
var stickyWarningFlashKeys = keySet(
	"flash.apartments.saved",
	"flash.apartments.pin_rotated",
	"flash.apartments.guest_link",
)

func keySet(keys ...string) map[string]bool {
	set := make(map[string]bool, len(keys))
	for _, k := range keys {
		set[k] = true
	}
	return set
}

// toastFor is the toast kind and stickiness _flash_message gives a key.
// Keys that are neither success, sticky warning nor partial stay neutral.
func toastFor(f Flash) (string, bool) {
	switch {
	case successFlashKeys[f.Key]:
		return "success", false
	case stickyWarningFlashKeys[f.Key]:
		return "warning", true
	case f.Key == "flash.reservations.accepted" && f.Count > 0:
		return "partial", true
	}
	return "", false
}

// Back is admin_helpers.back: a 303 to path with msg=, toast_kind=,
// toast_sticky= and err= in the query, and a #fragment kept at the end.
func Back(w http.ResponseWriter, r *http.Request, path string, msg, err Flash) {
	var query []string
	if msg.Text != "" {
		query = append(query, "msg="+pyQuote(msg.Text))
		if kind, sticky := toastFor(msg); kind != "" {
			query = append(query, "toast_kind="+kind)
			if sticky {
				query = append(query, "toast_sticky=1")
			}
		}
	}
	if err.Text != "" {
		query = append(query, "err="+pyQuote(err.Text))
	}
	if len(query) == 0 {
		http.Redirect(w, r, path, http.StatusSeeOther)
		return
	}
	base, fragment, hasFragment := strings.Cut(path, "#")
	sep := "?"
	if strings.Contains(base, "?") {
		sep = "&"
	}
	location := base + sep + strings.Join(query, "&")
	if hasFragment {
		location += "#" + fragment
	}
	// Location is set directly: http.Redirect would clean the query string.
	w.Header().Set("Location", location)
	w.WriteHeader(http.StatusSeeOther)
}

// pyQuote is Python's quote(s) with the default safe="/": ASCII letters,
// digits and "_.-~/" stay, every other UTF-8 byte becomes %XX.
func pyQuote(s string) string {
	const hexDigits = "0123456789ABCDEF"
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9':
			b.WriteByte(c)
		case strings.IndexByte("_.-~/", c) >= 0:
			b.WriteByte(c)
		default:
			b.WriteByte('%')
			b.WriteByte(hexDigits[c>>4])
			b.WriteByte(hexDigits[c&15])
		}
	}
	return b.String()
}

// Lang is host_i18n.resolve_language(request): ?lang=, then the ubyhost_lang
// cookie, each through supported_language, else DefaultLanguage.
func Lang(r *http.Request) string {
	for _, v := range []string{r.URL.Query().Get("lang"), Cookie(r, langCookie)} {
		if lang := supportedLanguage(v); lang != "" {
			return lang
		}
	}
	return DefaultLanguage
}

// supportedLanguage is host_i18n.supported_language: the first two letters
// of the value when we speak them, else "".
func supportedLanguage(v string) string {
	lang := firstTwo(strings.ToLower(strings.TrimSpace(v)))
	if knownLanguage(lang) {
		return lang
	}
	return ""
}

// normalise is host_i18n.normalise_language: a known code, else the default.
func normalise(v string) string {
	if lang := firstTwo(strings.ToLower(v)); knownLanguage(lang) {
		return lang
	}
	return DefaultLanguage
}

func knownLanguage(code string) bool {
	return code == "en" || code == "cs" || code == "vi"
}

// firstTwo is Python's [:2] on a string: the first two characters.
func firstTwo(s string) string {
	if r := []rune(s); len(r) > 2 {
		return string(r[:2])
	}
	return s
}

// Cookie returns the value of a cookie, or "" when it is missing.
func Cookie(r *http.Request, name string) string {
	if c, err := r.Cookie(name); err == nil {
		return c.Value
	}
	return ""
}

// QuotePath is Python quote(path): slashes kept, segments escaped.
func QuotePath(p string) string {
	parts := strings.Split(p, "/")
	for i, part := range parts {
		parts[i] = url.PathEscape(part)
	}
	return strings.Join(parts, "/")
}

// PublicBase is config.PUBLIC_BASE_URL with its default and trailing slash removed.
func PublicBase(getenv func(string) string) string {
	base := strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL"))
	if base == "" {
		base = defaultBase
	}
	return strings.TrimRight(base, "/")
}

// AppBase is config.app_base_url(): UBYHOST_APP_BASE_URL, else the public URL.
func AppBase(getenv func(string) string) string {
	if base := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/"); base != "" {
		return base
	}
	return PublicBase(getenv)
}

// SecureCookies is secure_cookies() (auth.py 880-893).
func SecureCookies(getenv func(string) string) bool {
	if strings.ToLower(strings.TrimSpace(getenv("UBYHOST_DEPLOYMENT"))) == "production" {
		return true
	}
	return strings.HasPrefix(strings.ToLower(PublicBase(getenv)), "https://")
}

// billingOn is config.BILLING_ENABLED.
func billingOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// publicHost is the canonical host of PUBLIC_BASE_URL.
func publicHost(getenv func(string) string) string {
	u, err := url.Parse(PublicBase(getenv))
	if err != nil {
		return ""
	}
	return canonical(u.Hostname())
}

// publicScheme is the lower-case scheme of PUBLIC_BASE_URL.
func publicScheme(getenv func(string) string) string {
	u, err := url.Parse(PublicBase(getenv))
	if err != nil {
		return ""
	}
	return strings.ToLower(u.Scheme)
}

// canonical is _canonical_host: lower case, no port, no leading "www.".
func canonical(host string) string {
	host = strings.ToLower(strings.SplitN(host, ":", 2)[0])
	return strings.TrimPrefix(host, "www.")
}

func hostsEqual(a, b string) bool {
	ca := canonical(a)
	return ca != "" && ca == canonical(b)
}

// claimInt reads a JSON-decoded integer claim; anything else is 0.
func claimInt(v any) int64 {
	switch n := v.(type) {
	case int64:
		return n
	case int:
		return int64(n)
	case float64:
		return int64(n)
	case json.Number:
		i, _ := n.Int64()
		return i
	}
	return 0
}

func stampAt(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// fail logs an error and writes the plain 500 the Connect routes always wrote.
func fail(w http.ResponseWriter, err error) {
	log.Printf("connect route failed: %v", err)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	_, _ = io.WriteString(w, "Internal Server Error")
}
