package onboarding

import (
	"context"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"path"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// formMaxMemory is the multipart memory limit for the small onboarding forms.
const formMaxMemory = 1 << 20

// maxIntDigits is CPython's default int() string limit (sys.int_info.default_max_str_digits).
const maxIntDigits = 4300

const auditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`

// DismissHandler serves POST /onboarding/dismiss (routes/onboarding.py onboarding_dismiss).
func DismissHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return dismissedRoute(pool, getenv, now, true, "onboarding.dismissed", "/")
}

// ResumeHandler serves POST /onboarding/resume (routes/onboarding.py onboarding_resume).
func ResumeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return dismissedRoute(pool, getenv, now, false, "onboarding.resumed", "/onboarding")
}

// dismissedRoute is the shared body of onboarding_dismiss and onboarding_resume:
// onboarding.set_dismissed, db.audit, then a 303 to the safe return_to.
func dismissedRoute(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, dismissed bool, action, fallback string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, ok := guard(w, r, pool, getenv, now)
		if !ok {
			return
		}
		ctx := r.Context()
		owner := h.Workspace.ID
		value := "0"
		if dismissed {
			value = "1"
		}
		if err := PoolSettings(pool).Set(ctx, fmt.Sprintf("onboarding_dismissed_%d", owner), value); err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, now(), action, owner); err != nil {
			serverError(w, err)
			return
		}
		redirect(w, safeLocalPath(formStr(r, "return_to"), fallback))
	}
}

// WelcomeBackDismissHandler serves POST /welcome-back/dismiss
// (routes/onboarding.py welcome_back_dismiss, welcome_back.dismiss). The key
// is the signed-in account's, not the previewed workspace's.
func WelcomeBackDismissHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, ok := guard(w, r, pool, getenv, now)
		if !ok {
			return
		}
		if h.Account.ID != 0 {
			if err := PoolSettings(pool).Set(r.Context(), fmt.Sprintf("welcome_back_%d", h.Account.ID), ""); err != nil {
				serverError(w, err)
				return
			}
		}
		redirect(w, "/")
	}
}

// CelebrationDismissHandler serves POST /celebrations/dismiss
// (routes/onboarding.py dismiss_celebration, celebrations.acknowledge). A
// milestone Python's int() refuses is the plain 500 Python answers with.
func CelebrationDismissHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, ok := guard(w, r, pool, getenv, now)
		if !ok {
			return
		}
		text := formStr(r, "milestone")
		if text == "" {
			text = "0"
		}
		milestone, ok := pyInt(text)
		if !ok {
			serverError(w, fmt.Errorf("milestone is not an int"))
			return
		}
		owner := h.Workspace.ID
		if owner != 0 && milestone.Sign() != 0 {
			if err := PoolSettings(pool).Set(r.Context(), fmt.Sprintf("celebration_%d", owner), milestone.String()); err != nil {
				serverError(w, err)
				return
			}
		}
		redirect(w, safeLocalPath(formStr(r, "return_to"), "/"))
	}
}

// guard is protect_host_post (admin.router's dependency, so it runs first)
// and then auth.require_login. ok is false after a response was written.
func guard(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) (*session.Host, bool) {
	at := now()
	if !hostweb.CSRF(w, r, getenv, at) {
		return nil, false
	}
	h, err := hostweb.Login(w, r, pool, getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	return h, h != nil
}

// audit is db.audit after require_login: the actor is the signed-in
// username, actor_user_id its id, and impersonator_user_id its id only while
// it previews another workspace (db.set_current_actor).
func audit(ctx context.Context, pool *pgxpool.Pool, h *session.Host, at time.Time, action string, owner int64) error {
	var impersonator any
	if h.Impersonating {
		impersonator = h.Account.ID
	}
	_, err := pool.Exec(ctx, auditSQL, stamp(at), h.Account.Username, action, "", owner, h.Account.ID, impersonator)
	return err
}

// stamp is db.utcnow: UTC, whole seconds, "+00:00".
func stamp(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// formStr is admin_helpers.form_str: the last value of a form field (as
// Starlette's FormData.get), stripped, or "".
func formStr(r *http.Request, key string) string {
	// ParseMultipartForm also parses url-encoded bodies; an error keeps the fields read so far.
	_ = r.ParseMultipartForm(formMaxMemory)
	values := r.PostForm[key]
	if len(values) == 0 {
		return ""
	}
	return pyStrip(values[len(values)-1])
}

// pyInt is Python's int(text) for ASCII text: an optional sign, then digits
// with single underscores between them. ok is false where Python raises
// ValueError; non-ASCII digits are refused too (brief 1290 section 2).
func pyInt(text string) (*big.Int, bool) {
	s := pyStrip(text)
	sign := ""
	if s != "" && (s[0] == '+' || s[0] == '-') {
		sign, s = s[:1], s[1:]
	}
	if s == "" || s[0] == '_' || s[len(s)-1] == '_' || strings.Contains(s, "__") {
		return nil, false
	}
	digits := strings.ReplaceAll(s, "_", "")
	if len(digits) > maxIntDigits {
		return nil, false
	}
	for i := 0; i < len(digits); i++ {
		if digits[i] < '0' || digits[i] > '9' {
			return nil, false
		}
	}
	n, ok := new(big.Int).SetString(sign+digits, 10)
	return n, ok
}

// redirect is RedirectResponse(location, status_code=303): an empty body and
// the Location Starlette quotes with safe=":/%#?=@[]!$&'()*+,;".
func redirect(w http.ResponseWriter, location string) {
	w.Header().Set("Location", starletteQuote(location))
	w.WriteHeader(http.StatusSeeOther)
}

// starletteQuote is urllib.parse.quote(url, safe=":/%#?=@[]!$&'()*+,;").
func starletteQuote(s string) string {
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

// serverError is Python's server_error_handler for a non-HTML request: a
// plain 500. The HTML error page waits for the Go host layout.
func serverError(w http.ResponseWriter, err error) {
	log.Printf("onboarding: %v", err)
	w.Header().Set("Cache-Control", "no-store, private")
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// safeLocalPath is security.safe_local_path (security.py 42-60): a
// normalised same-site path, or def for unsafe input. Where Python's
// urlsplit raises ValueError (a bracketed netloc such as "//[x") this
// returns def; brief 1290 section 2.
func safeLocalPath(value, def string) string {
	raw := pyStrip(value)
	if raw == "" || hasControl(raw) || strings.Contains(raw, `\`) {
		return def
	}
	// urlsplit: text that does not start with "/" has a scheme or a relative
	// path, and both fall back.
	if !strings.HasPrefix(raw, "/") {
		return def
	}
	rest := raw
	if strings.HasPrefix(rest, "//") {
		end := len(rest)
		if i := strings.IndexAny(rest[2:], "/?#"); i >= 0 {
			end = 2 + i
		}
		if end > 2 {
			return def // a netloc
		}
		rest = rest[end:]
	}
	if i := strings.IndexByte(rest, '#'); i >= 0 {
		rest = rest[:i]
	}
	p, query, _ := strings.Cut(rest, "?")
	if !strings.HasPrefix(p, "/") || strings.HasPrefix(p, "//") {
		return def
	}
	decoded := unquote(p)
	if strings.HasPrefix(decoded, "//") || strings.Contains(decoded, `\`) || hasControl(decoded) {
		return def
	}
	// posixpath.normpath equals path.Clean for a path with exactly one leading slash.
	clean := path.Clean(p)
	if !strings.HasPrefix(clean, "/") || strings.HasPrefix(clean, "//") {
		return def
	}
	if query != "" {
		clean += "?" + query
	}
	return clean
}

// hasControl is any(ord(char) < 0x20 for char in s).
func hasControl(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] < 0x20 {
			return true
		}
	}
	return false
}

// unquote is urllib.parse.unquote at the byte level: %XX becomes the byte,
// anything else stays. safeLocalPath only checks ASCII in the result, which
// Python's UTF-8 decoding with errors="replace" leaves as it is.
func unquote(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && isHex(s[i+1]) && isHex(s[i+2]) {
			b.WriteByte(unhex(s[i+1])<<4 | unhex(s[i+2]))
			i += 2
			continue
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

func isHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

func unhex(c byte) byte {
	switch {
	case c >= 'a':
		return c - 'a' + 10
	case c >= 'A':
		return c - 'A' + 10
	}
	return c - '0'
}
