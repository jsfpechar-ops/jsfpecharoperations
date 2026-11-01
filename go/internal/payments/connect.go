package payments

// Stripe Connect start and return routes (App/app/routes/stripe_connect.py 33-100).
//
// Only the guards are here. The two Stripe calls sit behind Onboarder; brief
// 0674 implements it and registers the routes in main.go.
//
// Known differences from Python, deliberately not ported (production never
// uses them): the staging no-login branch of require_login, the no-accounts
// dev shortcut, and language from request.state.lang (only ?lang= and the
// ubyhost_lang cookie are read). The CSRF form field is read only from
// urlencoded bodies; a multipart body without the x-csrf-token header counts
// as a missing token.

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

var (
	// ErrStripeOff is stripe_connect.StripeOff: the Stripe mode is off.
	ErrStripeOff = errors.New("payments: stripe off")
	// ErrNoEntity means the host has no Stripe entity to onboard.
	ErrNoEntity = errors.New("payments: no stripe entity")
	// ErrNoAccount means there is no Stripe account to read the return for.
	ErrNoAccount = errors.New("payments: no stripe account")
)

// Onboarder is the Stripe side of the Connect routes.
type Onboarder interface {
	OnboardingLink(ctx context.Context, owner int64, baseURL string) (string, error)
	HandleReturn(ctx context.Context, owner int64) error
}

const (
	connectConsentAction = "payments_terms_accepted" // payments_consent.ACTION
	connectConsentDetail = "version=2026-11-01"      // payments_consent.VERSION
	connectCSRFSalt      = "ubyhost-csrf"            // security._csrf_serializer
	connectCSRFMaxAge    = 400 * 24 * time.Hour      // security.CSRF_MAX_AGE
	connectCSRFCookie    = "ubyhost_csrf"            // security.CSRF_COOKIE
	connectCSRFHeader    = "x-csrf-token"            // security.CSRF_HEADER
	connectCSRFField     = "_csrf"                   // security.CSRF_FIELD
	connectLangCookie    = "ubyhost_lang"
	connectMaxBody       = 64 << 10 // POST body limit for the CSRF form field
	connectDefaultBase   = "http://127.0.0.1:8080"
	connectSessionMaxAge = 12 * 60 * 60 // SESSION_MAX_AGE (no "rm")
)

const (
	connectConsentSQL = `SELECT EXISTS (SELECT 1 FROM audit WHERE owner_user_id = $1 AND action = $2 AND detail = $3)`
	connectPausedSQL  = `SELECT status FROM billing_account WHERE owner_user_id = $1`
	connectAuditSQL   = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`
)

// connectExpiredTexts are impersonation.expired in host_i18n.py (en, cs) and
// host_vi_i18n.py (vi). The test checks them against those files.
var connectExpiredTexts = map[string]string{
	"en": "The workspace preview ended after 60 minutes. You are back in your own account.",
	"cs": "Náhled pracovního prostoru po 60 minutách skončil. Jste zpět ve svém účtu.",
	"vi": "Phiên xem trước không gian làm việc đã kết thúc sau 60 phút. Bạn đã quay lại tài khoản của mình.",
}

// ConnectStartHandler serves GET and POST /payments/connect/start
// (stripe_connect.py 60-89). POST runs the CSRF gate first, as the Python
// dependency does.
func ConnectStartHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, c Onboarder) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodPost {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		at := now()
		if r.Method == http.MethodPost && !connectCSRFGate(w, r, getenv, at) {
			return
		}
		ctx := r.Context()
		h, err := connectLogin(w, r, pool, getenv, at)
		if err != nil {
			connectFail(w, err)
			return
		}
		if h == nil {
			return
		}
		if connectOff(getenv) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		owner := h.Workspace.ID
		consented, err := connectConsented(ctx, pool, owner)
		if err != nil {
			connectFail(w, err)
			return
		}
		if !consented {
			http.Redirect(w, r, "/payments/consent", http.StatusSeeOther)
			return
		}
		link, err := c.OnboardingLink(ctx, owner, connectAppBase(getenv))
		switch {
		case err == nil:
			http.Redirect(w, r, link, http.StatusSeeOther)
		case errors.Is(err, ErrStripeOff), errors.Is(err, ErrNoEntity):
			log.Printf("connect start failed: %v", err)
			http.Redirect(w, r, "/", http.StatusSeeOther)
		default:
			connectFail(w, err)
		}
	}
}

// ConnectReturnHandler serves GET /payments/connect/return
// (stripe_connect.py 92-100). Return is not verification; the dashboard reads
// the mirror.
func ConnectReturnHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, c Onboarder) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		h, err := connectLogin(w, r, pool, getenv, now())
		if err != nil {
			connectFail(w, err)
			return
		}
		if h == nil {
			return
		}
		if connectOff(getenv) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if err := c.HandleReturn(r.Context(), h.Workspace.ID); err != nil {
			if !errors.Is(err, ErrStripeOff) && !errors.Is(err, ErrNoAccount) {
				connectFail(w, err)
				return
			}
			log.Printf("connect return failed: %v", err)
		}
		http.Redirect(w, r, "/", http.StatusSeeOther)
	}
}

// connectCSRFGate is _require_csrf(guest=False) (security.py 62-95, 114-208).
// It returns false after writing the response.
func connectCSRFGate(w http.ResponseWriter, r *http.Request, getenv func(string) string, at time.Time) bool {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		connectFail(w, err)
		return false
	}
	token := r.Header.Get(connectCSRFHeader)
	if token == "" {
		r.Body = http.MaxBytesReader(w, r.Body, connectMaxBody)
		if err := r.ParseForm(); err == nil {
			token = r.PostForm.Get(connectCSRFField)
		}
	}
	if connectCSRFValid(secret, token, connectCookie(r, connectCSRFCookie), at) {
		return true
	}
	if !connectSameSite(r, getenv) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"detail":"Cross-site request rejected."}`))
		return false
	}
	http.Redirect(w, r, connectRecovery(r, getenv), http.StatusSeeOther)
	return false
}

// connectCSRFValid checks the signed token against the CSRF cookie. An empty
// cookie never matches.
func connectCSRFValid(secret, token, cookie string, at time.Time) bool {
	if token == "" || cookie == "" {
		return false
	}
	var payload map[string]any
	if err := secure.NewTimedSerializer(secret, connectCSRFSalt).Loads(token, connectCSRFMaxAge, at, &payload); err != nil {
		return false
	}
	nonce, _ := payload["nonce"].(string)
	sum := sha256.Sum256([]byte(cookie))
	return hmac.Equal([]byte(nonce), []byte(hex.EncodeToString(sum[:])))
}

// connectSameSite is _request_is_same_site (security.py 150-164). Behind Caddy
// the request scheme is treated as http.
func connectSameSite(r *http.Request, getenv func(string) string) bool {
	if origin := r.Header.Get("Origin"); origin != "" {
		u, err := url.Parse(origin)
		return err == nil && connectBrowserSite(r, getenv, u.Hostname(), u.Scheme)
	}
	if ref := r.Header.Get("Referer"); ref != "" {
		u, err := url.Parse(ref)
		return err == nil && connectBrowserSite(r, getenv, u.Hostname(), u.Scheme)
	}
	return !strings.EqualFold(r.Header.Get("Sec-Fetch-Site"), "cross-site")
}

// connectBrowserSite is _browser_site_matches (security.py 114-137).
func connectBrowserSite(r *http.Request, getenv func(string) string, hostname, scheme string) bool {
	if !connectHostsEqual(hostname, r.Host) {
		pub := connectPublicHost(getenv)
		if pub == "" || !connectHostsEqual(hostname, pub) {
			return false
		}
	}
	origin := strings.ToLower(scheme)
	if origin == "http" {
		return true
	}
	pubScheme := connectPublicScheme(getenv)
	if origin == "https" {
		return pubScheme == "" || pubScheme == "https"
	}
	return pubScheme != "" && origin == pubScheme
}

// connectRecovery is _csrf_recovery_location (security.py 140-152).
func connectRecovery(r *http.Request, getenv func(string) string) string {
	if ref := r.Header.Get("Referer"); ref != "" {
		if u, err := url.Parse(ref); err == nil && connectBrowserSite(r, getenv, u.Hostname(), u.Scheme) {
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

// connectLogin is require_login (auth.py 481-560). It returns a nil host when
// it has written the response (or failed), and the signed-in host otherwise.
func connectLogin(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, error) {
	ctx := r.Context()
	h, err := session.Load(ctx, pool, connectCookie(r, session.CookieName), at, getenv)
	if err != nil {
		return nil, err
	}
	if h == nil {
		http.Redirect(w, r, "/login?next="+r.URL.Path, http.StatusSeeOther)
		return nil, nil
	}
	if h.ImpersonationExpired {
		return nil, connectEndExpired(w, r, pool, getenv, at, h)
	}
	if !h.Impersonating {
		pending, err := session.AcceptancePending(ctx, pool, h.Account.ID, getenv)
		if err != nil {
			return nil, err
		}
		if pending {
			http.Redirect(w, r, "/account/accept?next="+connectQuotePath(r.URL.Path), http.StatusSeeOther)
			return nil, nil
		}
	}
	if r.Method == http.MethodPost && !h.Impersonating && connectBillingOn(getenv) {
		var status string
		err := pool.QueryRow(ctx, connectPausedSQL, h.Workspace.ID).Scan(&status)
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

// connectEndExpired is end_expired_impersonation (auth.py 430-466): two
// impersonation_stopped rows, a fresh plain cookie, and the notice redirect.
func connectEndExpired(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time, h *session.Host) error {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return err
	}
	admin := h.Account
	target := connectInt(h.Payload["as"])
	owners := []int64{target}
	if admin.ID != target {
		owners = append(owners, admin.ID)
	}
	for _, owner := range owners {
		if _, err := pool.Exec(r.Context(), connectAuditSQL, stampAt(at), admin.Username,
			"impersonation_stopped", "expired", owner, admin.ID, admin.ID); err != nil {
			return err
		}
	}
	token := session.Sign(secret, map[string]any{
		"uid": admin.ID,
		"sv":  admin.SessionVersion,
		"iat": connectInt(h.Payload["iat"]),
	}, at)
	http.SetCookie(w, &http.Cookie{
		Name:     session.CookieName,
		Value:    token,
		Path:     "/",
		MaxAge:   connectSessionMaxAge,
		HttpOnly: true,
		Secure:   connectSecureCookies(getenv),
		SameSite: http.SameSiteStrictMode,
	})
	http.Redirect(w, r, "/admin/customers?msg="+url.PathEscape(connectExpiredTexts[connectLang(r)]), http.StatusSeeOther)
	return nil
}

func connectConsented(ctx context.Context, pool *pgxpool.Pool, owner int64) (bool, error) {
	var ok bool
	err := pool.QueryRow(ctx, connectConsentSQL, owner, connectConsentAction, connectConsentDetail).Scan(&ok)
	return ok, err
}

func connectFail(w http.ResponseWriter, err error) {
	log.Printf("connect route failed: %v", err)
	text(w, http.StatusInternalServerError, "Internal Server Error")
}

// connectMode is config.STRIPE_MODE; anything but test or live is off.
func connectOff(getenv func(string) string) bool {
	m := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STRIPE_MODE")))
	return m != "test" && m != "live"
}

func connectBillingOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// connectPublicBase is config.PUBLIC_BASE_URL with its default and trailing slash removed.
func connectPublicBase(getenv func(string) string) string {
	base := strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL"))
	if base == "" {
		base = connectDefaultBase
	}
	return strings.TrimRight(base, "/")
}

// connectAppBase is config.app_base_url(): UBYHOST_APP_BASE_URL, else the public URL.
func connectAppBase(getenv func(string) string) string {
	if base := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/"); base != "" {
		return base
	}
	return connectPublicBase(getenv)
}

// connectSecureCookies is secure_cookies() (auth.py 880-893).
func connectSecureCookies(getenv func(string) string) bool {
	if strings.ToLower(strings.TrimSpace(getenv("UBYHOST_DEPLOYMENT"))) == "production" {
		return true
	}
	return strings.HasPrefix(strings.ToLower(connectPublicBase(getenv)), "https://")
}

func connectPublicHost(getenv func(string) string) string {
	u, err := url.Parse(connectPublicBase(getenv))
	if err != nil {
		return ""
	}
	return connectCanonical(u.Hostname())
}

func connectPublicScheme(getenv func(string) string) string {
	u, err := url.Parse(connectPublicBase(getenv))
	if err != nil {
		return ""
	}
	return strings.ToLower(u.Scheme)
}

// connectCanonical is _canonical_host: lower case, no port, no leading "www.".
func connectCanonical(host string) string {
	host = strings.ToLower(strings.SplitN(host, ":", 2)[0])
	return strings.TrimPrefix(host, "www.")
}

func connectHostsEqual(a, b string) bool {
	ca := connectCanonical(a)
	return ca != "" && ca == connectCanonical(b)
}

// connectLang is the language of the expired notice: ?lang=, then the
// ubyhost_lang cookie, else en.
func connectLang(r *http.Request) string {
	for _, v := range []string{r.URL.Query().Get("lang"), connectCookie(r, connectLangCookie)} {
		switch v = strings.ToLower(strings.TrimSpace(v)); v {
		case "en", "cs", "vi":
			return v
		}
	}
	return "en"
}

// connectQuotePath is Python quote(path): slashes kept, segments escaped.
func connectQuotePath(p string) string {
	parts := strings.Split(p, "/")
	for i, part := range parts {
		parts[i] = url.PathEscape(part)
	}
	return strings.Join(parts, "/")
}

// connectInt reads a JSON-decoded integer claim; anything else is 0.
func connectInt(v any) int64 {
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

func connectCookie(r *http.Request, name string) string {
	if c, err := r.Cookie(name); err == nil {
		return c.Value
	}
	return ""
}
