package guest

// Brief 1720b: POST /l/{token}/pin — verify_pin parity (dual rate limits, Turnstile,
// ubyhost_pin session). Pin page HTML is rendered on errors; GET pick stays in 1720c.

import (
	"context"
	"fmt"
	"html/template"
	"io"
	"log"
	"math"
	"net/http"
	"net/url"
	"path"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

var pinSet = func() *template.Template {
	t := template.Must(template.New("guest.base").Funcs(tplFuncs).ParseFS(templateFS,
		"templates/base.tmpl", "templates/host_fragment.tmpl", "templates/pin.tmpl"))
	return t
}()

// PinView is guest/pin.html context layered on Page.
type PinView struct {
	Page
	PinError         string
	ReturnTo         string
	RequireTurnstile bool
	TurnstileSiteKey string
	LangQuery        string
}

// T delegates to Page.T for templates.
func (p PinView) T(key string, kv ...any) string { return p.Page.T(key, kv...) }

func safeReturnTo(requested, token, lang string) string {
	fallback := GuestLink(token, 0, "") + LangQuery(GuestLanguage(lang), "")
	raw := ai.HavelSafeLocalPath(requested, "")
	if raw == "" {
		return fallback
	}
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "" || u.Host != "" {
		return fallback
	}
	norm := path.Clean(u.Path)
	prefix := GuestLink(token, 0, "")
	if norm != prefix && !strings.HasPrefix(norm, prefix+"/") {
		return fallback
	}
	out := norm
	if u.RawQuery != "" {
		out += "?" + u.RawQuery
	}
	return out + u.Fragment
}

func linkChallenged(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, apt *Apartment, secret string, now time.Time) (bool, error) {
	if apt == nil || !turnstile.Required(getenv) {
		return false, nil
	}
	expected := strings.TrimSpace(apt.PermalinkPIN)
	lockKey := PinLockKey(secret, apt.PermalinkToken, expected)
	return pinTokenBlocked(ctx, pool, lockKey, now)
}

func sharedPinPage(r *http.Request, pool *pgxpool.Pool, getenv func(string) string, token, lang string, apt *Apartment, now time.Time) (PinView, *http.Cookie, error) {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return PinView{}, nil, err
	}
	lang = GuestLanguage(lang)
	csrf, csrfCookie, err := guestCSRF(r, secret, getenv, now)
	if err != nil {
		return PinView{}, nil, err
	}
	lockToken := token
	if apt != nil && apt.PermalinkToken != "" {
		lockToken = apt.PermalinkToken
	}
	failures, err := pinFailureCount(r.Context(), pool, clientip.Key(r, getenv, lockToken), now)
	if err != nil {
		return PinView{}, nil, err
	}
	challenged, err := linkChallenged(r.Context(), pool, getenv, apt, secret, now)
	if err != nil {
		return PinView{}, nil, err
	}
	p := PinView{
		Page: Page{
			Lang:            lang,
			Token:           token,
			LangURLs:        LangURLs(r, ""),
			PrivacyURL:      GuestLink(token, 0, "/privacy") + LangQuery(lang, ""),
			LoadSignatureJS: true,
			CSRFToken:       csrf,
			GuestEndonyms:   GuestEndonyms,
		},
		ReturnTo:         r.URL.Path,
		RequireTurnstile: failures >= 3 || challenged,
		TurnstileSiteKey: turnstile.PageSiteKey(getenv),
		LangQuery:        LangQuery(lang, ""),
	}
	if apt != nil {
		p.Facility = Facility(apt)
		p.FacilityTone = int(apt.ID % 10)
	}
	if r.URL.RawQuery != "" {
		p.ReturnTo += "?" + r.URL.RawQuery
	}
	return p, csrfCookie, nil
}

func writePinPage(w http.ResponseWriter, r *http.Request, status int, p PinView, extra map[string]string, csrfCookie *http.Cookie, lang string, getenv func(string) string) {
	if csrfCookie != nil {
		http.SetCookie(w, &http.Cookie{
			Name: LangCookie, Value: lang, Path: "/", MaxAge: langCookieAge,
			SameSite: http.SameSiteLaxMode, Secure: hostweb.SecureCookies(getenv),
		})
		http.SetCookie(w, csrfCookie)
	}
	var buf strings.Builder
	if err := pinSet.ExecuteTemplate(&buf, "guest.base", p); err != nil {
		log.Printf("guest pin page: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	for k, v := range extra {
		h.Set(k, v)
	}
	w.WriteHeader(status)
	if r.Method != http.MethodHead {
		_, _ = io.WriteString(w, buf.String())
	}
}

func (d shellDeps) verifyPin(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	lang := Language(r)
	key := r.PathValue("token")
	now := d.now()
	if !hostweb.CSRF(w, r, d.getenv, now) {
		return
	}
	apt, _, early := OpenLink(r, d.pool, key, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return
	}
	if apt == nil {
		http.NotFound(w, r)
		return
	}
	returnTo := safeReturnTo(r.PostFormValue("return_to"), key, lang)
	pinError := func(msgKey string) {
		view, csrfCookie, err := sharedPinPage(r, d.pool, d.getenv, key, lang, apt, now)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		view.PinError = view.T(msgKey)
		view.ReturnTo = returnTo
		writePinPage(w, r, http.StatusOK, view, map[string]string{}, csrfCookie, view.Lang, d.getenv)
	}
	entered := strings.TrimSpace(r.PostFormValue("pin"))
	expected := strings.TrimSpace(apt.PermalinkPIN)
	lockToken := apt.PermalinkToken
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	pinKey := clientip.Key(r, d.getenv, lockToken)
	pinLockKey := PinLockKey(secret, lockToken, expected)
	linkLocked, err := pinTokenBlocked(ctx, d.pool, pinLockKey, now)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	if linkLocked && !turnstile.Required(d.getenv) {
		pinError("pin_locked_out")
		return
	}
	failures, _ := pinFailureCount(ctx, d.pool, pinKey, now)
	if linkLocked || failures >= 3 {
		tsToken := r.PostFormValue("cf-turnstile-response")
		ok, err := turnstile.Verifier{Pool: d.pool, Getenv: d.getenv, Now: d.now}.Verify(ctx, r, tsToken, "guest_pin")
		if err != nil || !ok {
			pinError("security_check_failed")
			return
		}
	}
	blocked, err := pinBlocked(ctx, d.pool, pinKey, now)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	if blocked {
		pinError("pin_rate_limited")
		return
	}
	if !pinMatches(secret, lockToken, entered, expected) {
		_ = recordPinFailure(ctx, d.pool, pinKey, pinLockKey, now)
		aptID := apt.ID
		var owner int64
		_ = d.pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, aptID).Scan(&owner)
		if linkLocked, _ = pinTokenBlocked(ctx, d.pool, pinLockKey, now); linkLocked && turnstile.Required(d.getenv) {
			_ = ubyport.RaiseAlert(ctx, d.pool, "warning", "guest_pin_challenged",
				"Guest link now asks for a security check after repeated wrong PINs.",
				"Guests can still open it after the check. Generate a new PIN if the link may have leaked.",
				fmt.Sprintf("guest_pin_challenged:%d", aptID), &aptID, nil, &owner, nil)
			_ = ubyport.Audit(ctx, d.pool, "guest_pin_token_challenged", fmt.Sprintf("apartment=%d", aptID), &owner)
		} else if linkLocked {
			_ = ubyport.RaiseAlert(ctx, d.pool, "critical", "guest_pin_locked_out",
				"Guest link locked out for 24 hours after repeated wrong PINs.",
				"Every guest using this link is refused until you generate a new PIN.",
				fmt.Sprintf("guest_pin_locked_out:%d", aptID), &aptID, nil, &owner, nil)
			_ = ubyport.Audit(ctx, d.pool, "guest_pin_token_locked", fmt.Sprintf("apartment=%d", aptID), &owner)
		}
		failures, _ = pinFailureCount(ctx, d.pool, pinKey, now)
		if failures >= pinMaxFailures {
			_ = ubyport.RaiseAlert(ctx, d.pool, "warning", "guest_pin_abuse",
				"Guest link temporarily blocked after repeated wrong PINs.",
				"Review the message PIN and rotate it if the link may have been shared.",
				fmt.Sprintf("guest_pin_abuse:%d", aptID), &aptID, nil, &owner, nil)
			_ = ubyport.Audit(ctx, d.pool, "guest_pin_rate_limited", fmt.Sprintf("apartment=%d", aptID), &owner)
		}
		if failures > 0 {
			time.Sleep(time.Duration(math.Min(2, 0.15*float64(failures))) * time.Second)
		}
		pinError("pin_wrong")
		return
	}
	if err := attachPinSession(w, secret, lockToken, expected, d.getenv, now); err != nil {
		log.Printf("guest pin session: %v", err)
	}
	WithLang(w, d.getenv, GuestLanguage(lang))
	http.Redirect(w, r, returnTo, http.StatusSeeOther)
}
