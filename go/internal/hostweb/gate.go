package hostweb

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// security._csrf_serializer salt.
const csrfSalt = "ubyhost-csrf"

// security.CSRF_MAX_AGE.
const csrfMaxAge = 400 * 24 * time.Hour

// security.CSRF_COOKIE.
const csrfCookie = "ubyhost_csrf"

// security.CSRF_HEADER.
const csrfHeader = "x-csrf-token"

// security.CSRF_FIELD.
const csrfField = "_csrf"

// csrfMaxBody limits the POST body read for the CSRF form field.
const csrfMaxBody = 64 << 10

const pausedSQL = `SELECT status FROM billing_account WHERE owner_user_id = $1`

const auditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`

// ExpiredTexts are impersonation.expired in host_i18n.py (en, cs) and
// host_vi_i18n.py (vi). The test checks them against those files.
var ExpiredTexts = map[string]string{
	"en": "The workspace preview ended after 60 minutes. You are back in your own account.",
	"cs": "Náhled pracovního prostoru po 60 minutách skončil. Jste zpět ve svém účtu.",
	"vi": "Phiên xem trước không gian làm việc đã kết thúc sau 60 phút. Bạn đã quay lại tài khoản của mình.",
}

// Login is require_login (auth.py 481-560). It returns a nil host when it has
// written the response (or failed), and the signed-in host otherwise.
func Login(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, error) {
	ctx := r.Context()
	h, err := session.Load(ctx, pool, Cookie(r, session.CookieName), at, getenv)
	if err != nil {
		return nil, err
	}
	if h == nil {
		http.Redirect(w, r, "/login?next="+r.URL.Path, http.StatusSeeOther)
		return nil, nil
	}
	if h.ImpersonationExpired {
		return nil, endExpired(w, r, pool, getenv, at, h)
	}
	if !h.Impersonating {
		pending, err := session.AcceptancePending(ctx, pool, h.Account.ID, getenv)
		if err != nil {
			return nil, err
		}
		if pending {
			http.Redirect(w, r, "/account/accept?next="+QuotePath(r.URL.Path), http.StatusSeeOther)
			return nil, nil
		}
	}
	if r.Method == http.MethodPost && !h.Impersonating && billingOn(getenv) {
		var status string
		err := pool.QueryRow(ctx, pausedSQL, h.Workspace.ID).Scan(&status)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, err
		}
		if status == "paused" {
			http.Redirect(w, r, "/predplatne?paused=1", http.StatusSeeOther)
			return nil, nil
		}
	}
	return h, nil
}

// endExpired is end_expired_impersonation (auth.py 430-466): two
// impersonation_stopped rows, a fresh plain cookie, and the notice redirect.
func endExpired(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time, h *session.Host) error {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return err
	}
	admin := h.Account
	target := claimInt(h.Payload["as"])
	owners := []int64{target}
	if admin.ID != target {
		owners = append(owners, admin.ID)
	}
	for _, owner := range owners {
		if _, err := pool.Exec(r.Context(), auditSQL, stampAt(at), admin.Username,
			"impersonation_stopped", "expired", owner, admin.ID, admin.ID); err != nil {
			return err
		}
	}
	token := session.Sign(secret, map[string]any{
		"uid": admin.ID,
		"sv":  admin.SessionVersion,
		"iat": claimInt(h.Payload["iat"]),
	}, at)
	http.SetCookie(w, &http.Cookie{
		Name:     session.CookieName,
		Value:    token,
		Path:     "/",
		MaxAge:   sessionMaxAge,
		HttpOnly: true,
		Secure:   SecureCookies(getenv),
		SameSite: http.SameSiteStrictMode,
	})
	http.Redirect(w, r, "/admin/customers?msg="+url.PathEscape(ExpiredTexts[Lang(r)]), http.StatusSeeOther)
	return nil
}

// CSRF is _require_csrf(guest=False) (security.py 62-95, 114-208). It returns
// false after writing the response.
func CSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, at time.Time) bool {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		fail(w, err)
		return false
	}
	token := r.Header.Get(csrfHeader)
	if token == "" {
		r.Body = http.MaxBytesReader(w, r.Body, csrfMaxBody)
		if err := r.ParseForm(); err == nil {
			token = r.PostForm.Get(csrfField)
		}
	}
	if csrfValid(secret, token, Cookie(r, csrfCookie), at) {
		return true
	}
	if !sameSite(r, getenv) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"detail":"Cross-site request rejected."}`))
		return false
	}
	http.Redirect(w, r, recovery(r, getenv), http.StatusSeeOther)
	return false
}

// csrfValid checks the signed token against the CSRF cookie. An empty cookie
// never matches.
func csrfValid(secret, token, cookie string, at time.Time) bool {
	if token == "" || cookie == "" {
		return false
	}
	var payload map[string]any
	if err := secure.NewTimedSerializer(secret, csrfSalt).Loads(token, csrfMaxAge, at, &payload); err != nil {
		return false
	}
	nonce, _ := payload["nonce"].(string)
	sum := sha256.Sum256([]byte(cookie))
	return hmac.Equal([]byte(nonce), []byte(hex.EncodeToString(sum[:])))
}

// sameSite is _request_is_same_site (security.py 150-164). Behind Caddy the
// request scheme is treated as http.
func sameSite(r *http.Request, getenv func(string) string) bool {
	if origin := r.Header.Get("Origin"); origin != "" {
		u, err := url.Parse(origin)
		return err == nil && browserSite(r, getenv, u.Hostname(), u.Scheme)
	}
	if ref := r.Header.Get("Referer"); ref != "" {
		u, err := url.Parse(ref)
		return err == nil && browserSite(r, getenv, u.Hostname(), u.Scheme)
	}
	return !strings.EqualFold(r.Header.Get("Sec-Fetch-Site"), "cross-site")
}

// browserSite is _browser_site_matches (security.py 114-137).
func browserSite(r *http.Request, getenv func(string) string, hostname, scheme string) bool {
	if !hostsEqual(hostname, r.Host) {
		pub := publicHost(getenv)
		if pub == "" || !hostsEqual(hostname, pub) {
			return false
		}
	}
	origin := strings.ToLower(scheme)
	if origin == "http" {
		return true
	}
	pubScheme := publicScheme(getenv)
	if origin == "https" {
		return pubScheme == "" || pubScheme == "https"
	}
	return pubScheme != "" && origin == pubScheme
}

// recovery is _csrf_recovery_location (security.py 140-152).
func recovery(r *http.Request, getenv func(string) string) string {
	if ref := r.Header.Get("Referer"); ref != "" {
		if u, err := url.Parse(ref); err == nil && browserSite(r, getenv, u.Hostname(), u.Scheme) {
			path := u.Path
			if path == "" {
				path = "/"
			}
			if path == "/login" {
				return "/login?notice=form_expired"
			}
			q := u.Query()
			q.Set("err", "This form expired. Please try again.")
			return path + "?" + q.Encode()
		}
	}
	return "/login?notice=form_expired"
}
