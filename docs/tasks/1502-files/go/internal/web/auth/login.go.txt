package auth

// The login pages, ported from App/app/routes/admin_accounts.py login_form,
// login_submit, login_link_form and login_link_submit (lines 60-267) with
// _login_page_context, _try_staging_password_login, _dev_link_visible and
// _link_page, and the middleware's login_redirect_url (main.py,
// site_urls.py 60-72) for the two GET paths (brief 1502). The pages render
// through authpage (the auth_base.html port).

import (
	"context"
	"crypto/subtle"
	"errors"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth/authpage"
)

// turnstileLoginAction is the action the login widget and check use.
const turnstileLoginAction = "host_login"

// Python's login error keys and their status codes.
const (
	errTurnstile       = "auth.error.turnstile"
	errEmailInvalid    = "auth.error.email_invalid"
	errLinkRateLimited = "auth.error.link_rate_limited"
	errStagingPassword = "auth.error.staging_password"
)

// loginVerifier is the Turnstile check of the login form. Tests replace it to
// point the real Verifier at a fake siteverify server.
var loginVerifier = func(d deps) turnstile.Verifier {
	return turnstile.Verifier{Pool: d.pool, Getenv: d.getenv, Now: d.now}
}

// sendLinkNow is the BackgroundTask mail.send_now(outbox_id): it runs after
// the page is written and never changes the answer. Tests replace it to run
// in line.
var sendLinkNow = func(d deps, outboxID int64) {
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := mail.SendNow(ctx, d.pool, d.getenv, outboxID); err != nil {
			log.Printf("web/auth: login link send_now: %v", err)
		}
	}()
}

// deployment is config.DEPLOYMENT: UBYHOST_DEPLOYMENT lower-cased, default "local".
func deployment(getenv func(string) string) string {
	v := getenv("UBYHOST_DEPLOYMENT")
	if v == "" {
		v = "local"
	}
	return strings.ToLower(v)
}

// pageEnv is the authpage environment of one request.
func (d deps) pageEnv(at time.Time) authpage.Env {
	return authpage.Env{Getenv: d.getenv, Now: at}
}

// render is templating.render(request, name, data, status_code) for an
// auth_base page; a failure answers 500.
func (d deps) render(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, name string, data any, status int) {
	if err := authpage.Render(w, r, d.pageEnv(at), h, name, data, status); err != nil {
		serverError(w, err)
	}
}

// refreshed is the middleware's refresh_session_cookie on an answer that
// renders no page. ok is false after a 500.
func (d deps) refreshed(w http.ResponseWriter, h *session.Host, at time.Time) bool {
	if h == nil {
		return true
	}
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		serverError(w, err)
		return false
	}
	c, err := session.RefreshSession(secret, h.Payload, w.Header(), hostweb.SecureCookies(d.getenv), at)
	if err != nil {
		serverError(w, err)
		return false
	}
	if c != nil {
		http.SetCookie(w, c)
	}
	return true
}

// loginHostRedirect is the middleware's site_urls.login_redirect_url for a GET
// (or HEAD) of /login or /login/link on the public host while a separate app
// host is set: a 302 to the same path and query there, with no Referer. It
// reports whether it answered.
func loginHostRedirect(w http.ResponseWriter, r *http.Request, getenv func(string) string) bool {
	public := hostweb.PublicBase(getenv)
	app := hostweb.AppBase(getenv)
	if strings.TrimRight(app, "/") == strings.TrimRight(public, "/") {
		return false
	}
	u, err := url.Parse(public)
	if err != nil {
		return false
	}
	if !strings.EqualFold(requestHostname(r), u.Hostname()) {
		return false
	}
	target := strings.TrimRight(app, "/") + r.URL.Path
	if r.URL.RawQuery != "" {
		target += "?" + r.URL.RawQuery
	}
	w.Header().Set("Location", target)
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.WriteHeader(http.StatusFound)
	return true
}

// requestHostname is request.url.hostname: the Host header without its port.
func requestHostname(r *http.Request) string {
	host := r.Host
	if strings.HasPrefix(host, "[") {
		if i := strings.IndexByte(host, ']'); i > 0 {
			return host[1:i]
		}
	}
	if i := strings.LastIndexByte(host, ':'); i >= 0 {
		return host[:i]
	}
	return host
}

// queryLast is request.query_params.get(key, ""): the last value.
func queryLast(r *http.Request, key string) string {
	vals := r.URL.Query()[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}

// cutChars is Python's s[:n] on a str.
func cutChars(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

// loginPageData is _login_page_context: skip_turnstile and, on staging, the
// staging hints.
func (d deps) loginPageData(ctx context.Context, r *http.Request, at time.Time) (authpage.LoginData, error) {
	var data authpage.LoginData
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		return data, err
	}
	if data.SkipTurnstile, err = session.DeviceCookieValid(ctx, d.pool, secret,
		hostweb.Cookie(r, session.DeviceCookieName), at); err != nil {
		return data, err
	}
	if deployment(d.getenv) == "staging" {
		if data.StagingLoginEmail, err = d.stagingAdminLoginEmail(ctx); err != nil {
			return data, err
		}
		data.StagingPasswordEnabled = stagingExpectedPassword(d.getenv) != ""
		if data.StagingAdminUsername, err = d.stagingAdminUsername(ctx); err != nil {
			return data, err
		}
	}
	return data, nil
}

// loginForm is login_form (GET /login).
func (d deps) loginForm(w http.ResponseWriter, r *http.Request) {
	if loginHostRedirect(w, r, d.getenv) {
		return
	}
	at := d.now()
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	if h != nil {
		if d.refreshed(w, h, at) {
			redirect(w, "/")
		}
		return
	}
	data, err := d.loginPageData(r.Context(), r, at)
	if err != nil {
		serverError(w, err)
		return
	}
	data.Next = queryLast(r, "next")
	d.render(w, r, nil, at, "login", data, http.StatusOK)
}

// loginSubmit is login_submit (POST /login): the staging password, the
// Turnstile check (skipped for a trusted device), the rate limits, then the
// login link mail and the same "check your e-mail" page whether or not the
// address has an account.
func (d deps) loginSubmit(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	ctx := r.Context()
	rawEmail := cutChars(formStr(r, "email", ""), 254)
	email := normaliseEmail(rawEmail)
	next := safeLocalPath(formStr(r, "next", ""), "/")
	remember := true
	lang := loginLanguage(r)
	verifier := loginVerifier(d)
	token, _ := formLast(r, "cf-turnstile-response")

	again := func(errKey string, status int) {
		h, ok := d.current(w, r, at)
		if !ok {
			return
		}
		data, err := d.loginPageData(ctx, r, at)
		if err != nil {
			serverError(w, err)
			return
		}
		data.Error, data.Email, data.Next = errKey, rawEmail, next
		if errKey == errTurnstile {
			data.SkipTurnstile = false
		}
		d.render(w, r, h, at, "login", data, status)
	}

	if deployment(d.getenv) == "staging" && stagingExpectedPassword(d.getenv) != "" {
		if password := formStr(r, "staging_password", ""); password != "" {
			ok, err := verifier.Verify(ctx, r, token, turnstileLoginAction)
			if err != nil {
				serverError(w, err)
				return
			}
			if !ok {
				again(errTurnstile, http.StatusForbidden)
				return
			}
			username := formStr(r, "username", "")
			if !stagingPasswordOK(d.getenv, password) {
				again(errStagingPassword, http.StatusForbidden)
				return
			}
			account, err := d.stagingAccountForPasswordLogin(ctx, username, email)
			if err != nil {
				serverError(w, err)
				return
			}
			if account != nil && account.Active != 0 {
				if err := d.finishLogin(w, r, account, remember, next, MethodStagingPassword, ActionLogin, at); err != nil {
					serverError(w, err)
				}
				return
			}
		}
		again(errStagingPassword, http.StatusForbidden)
		return
	}

	ipKey := clientip.Key(r, d.getenv, "")
	trusted := false
	if email != "" {
		secret, err := secure.LoadSecret(d.getenv)
		if err != nil {
			serverError(w, err)
			return
		}
		if trusted, err = session.TrustedDevice(ctx, d.pool, secret, hostweb.Cookie(r, session.DeviceCookieName), email, at); err != nil {
			serverError(w, err)
			return
		}
		if trusted {
			blocked, err := session.LinkRequestBlocked(ctx, d.pool, ipKey, email, at)
			if err != nil {
				serverError(w, err)
				return
			}
			trusted = !blocked
		}
	}
	if !trusted {
		ok, err := verifier.Verify(ctx, r, token, turnstileLoginAction)
		if err != nil {
			serverError(w, err)
			return
		}
		if !ok {
			again(errTurnstile, http.StatusForbidden)
			return
		}
	}
	if email == "" {
		again(errEmailInvalid, http.StatusBadRequest)
		return
	}
	blocked, err := session.LinkRequestBlocked(ctx, d.pool, ipKey, email, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		again(errLinkRateLimited, http.StatusTooManyRequests)
		return
	}
	if err := session.LinkRecordRequest(ctx, d.pool, ipKey, email, at); err != nil {
		serverError(w, err)
		return
	}
	data := authpage.LoginSentData{Email: email, Remember: remember, Next: next}
	account, err := session.AccountByEmail(ctx, d.pool, email)
	if err != nil {
		serverError(w, err)
		return
	}
	var outboxID int64
	if account != nil {
		link, err := session.IssueLoginLink(ctx, d.pool, account, session.PurposeLogin, "", remember, next, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if outboxID, err = mail.QueueLinkMail(ctx, d.pool, d.getenv, mail.KindLoginLink, account.ID, email, link,
			session.LinkTTL[session.PurposeLogin]/60, lang, at); err != nil {
			serverError(w, err)
			return
		}
		if err := d.audit(ctx, nil, at, "login_link_sent", "", "anonymous", ptr(account.ID)); err != nil {
			serverError(w, err)
			return
		}
		if devLinkVisible(d.getenv) {
			data.DevLink = "/login/link?t=" + link
		}
	}
	if deployment(d.getenv) == "staging" {
		data.StagingConsoleMail = true
	}
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	d.render(w, r, h, at, "login_sent", data, http.StatusOK)
	if outboxID > 0 {
		sendLinkNow(d, outboxID)
	}
}

// devLinkVisible is _dev_link_visible: a local run with the console mail backend.
func devLinkVisible(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return deployment(getenv) == "local" && backend == "console"
}

// linkPage is _link_page: login_link.html, never cached, no Referer onward.
func (d deps) linkPage(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, data authpage.LoginLinkData, status int) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Referrer-Policy", "no-referrer")
	d.render(w, r, h, at, "login_link", data, status)
}

// loginLinkForm is login_link_form (GET /login/link): a "Log in" button;
// opening the link spends nothing (mail scanners).
func (d deps) loginLinkForm(w http.ResponseWriter, r *http.Request) {
	if loginHostRedirect(w, r, d.getenv) {
		return
	}
	at := d.now()
	ctx := r.Context()
	token := queryLast(r, "t")
	row, err := session.PeekLoginLink(ctx, d.pool, token, nil, at)
	if err != nil {
		serverError(w, err)
		return
	}
	var account *session.LoginAccount
	if row != nil {
		if account, err = session.AccountForLink(ctx, d.pool, row); err != nil {
			serverError(w, err)
			return
		}
	}
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	// A signed-in host who opens a spent link (Back after logging in) goes
	// to the app; a valid link for another account still shows its button.
	if h != nil && (account == nil || account.ID == h.Account.ID) {
		if d.refreshed(w, h, at) {
			redirect(w, "/")
		}
		return
	}
	if row == nil || account == nil {
		d.linkPage(w, r, h, at, authpage.LoginLinkData{Expired: true}, http.StatusGone)
		return
	}
	d.linkPage(w, r, h, at, authpage.LoginLinkData{Token: token, Invite: row.Purpose == session.PurposeInvite}, http.StatusOK)
}

// loginLinkSubmit is login_link_submit (POST /login/link): spend the link,
// then the 2FA step or the session.
func (d deps) loginLinkSubmit(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	ctx := r.Context()
	token := formStr(r, "t", "")
	ipKey := clientip.Key(r, d.getenv, "")
	blocked, err := session.LinkConsumeBlocked(ctx, d.pool, ipKey, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		if h, ok := d.current(w, r, at); ok {
			d.linkPage(w, r, h, at, authpage.LoginLinkData{Expired: true, Locked: true}, http.StatusTooManyRequests)
		}
		return
	}
	row, err := session.ConsumeLoginLink(ctx, d.pool, token, nil, at)
	if err != nil {
		serverError(w, err)
		return
	}
	account, err := session.AccountForLink(ctx, d.pool, row)
	if err != nil {
		serverError(w, err)
		return
	}
	if account == nil {
		if err := session.LinkRecordConsumeFailure(ctx, d.pool, ipKey, at); err != nil {
			serverError(w, err)
			return
		}
		if h, ok := d.current(w, r, at); ok {
			d.linkPage(w, r, h, at, authpage.LoginLinkData{Expired: true}, http.StatusGone)
		}
		return
	}
	if account.EmailVerifiedAt == nil || *account.EmailVerifiedAt == "" {
		if _, err := d.pool.Exec(ctx, `UPDATE user_account SET email_verified_at = $1 WHERE id = $2`,
			session.UTCNow(at), account.ID); err != nil {
			serverError(w, err)
			return
		}
	}
	if account.Role == "admin" && row.Purpose == session.PurposeInvite {
		// The bootstrap link has done its job; nothing on disk should still
		// hold a working one. The Go container mounts the data volume
		// read-only, so this fails there as any OSError does in Python: the
		// file stays, but the link in it is spent.
		if dir := d.getenv("UBYHOST_DATA_DIR"); dir != "" {
			if err := os.Remove(filepath.Join(dir, "initial_admin_login")); err != nil && !errors.Is(err, os.ErrNotExist) {
				log.Printf("web/auth: initial_admin_login not removed")
			}
		}
	}
	remember := row.Remember != 0
	next := "/"
	if row.NextPath != nil && *row.NextPath != "" {
		next = *row.NextPath
	}
	if account.TOTPEnabled != 0 {
		secret, err := secure.LoadSecret(d.getenv)
		if err != nil {
			serverError(w, err)
			return
		}
		pending, err := session.IssueTwoFactorPending(secret, account.ID, remember, next, at)
		if err != nil {
			serverError(w, err)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		if err := d.renderTwoFactorLogin(w, r, pending, "", http.StatusOK); err != nil {
			serverError(w, err)
		}
		return
	}
	if err := d.finishLogin(w, r, account, remember, next, MethodLink, ActionLogin, at); err != nil {
		serverError(w, err)
	}
}

// renderTwoFactorLogin writes two_factor_login.html with the given pending
// token in both hidden "pending" fields and, when errorKey is not "", the
// auth-alert box with t(errorKey) (plus the "log in again" link for
// auth.error.code_locked), as Python's render does, for current_user (the
// "Not you?" form and the English fallback when someone is signed in). It
// sets Content-Type and writes status; it does not set Cache-Control; it sets
// no cookie when the request carries the CSRF nonce cookie (apart from the
// language cookie for a new ?lang= and a due remember-me refresh, as Python).
// Brief 1503 calls it for POST /login/2fa. Nothing is written on an error.
func (d deps) renderTwoFactorLogin(w http.ResponseWriter, r *http.Request, pending, errorKey string, status int) error {
	at := d.now()
	h, err := session.Load(r.Context(), d.pool, hostweb.Cookie(r, session.CookieName), at, d.getenv)
	if err != nil {
		return err
	}
	return authpage.Render(w, r, d.pageEnv(at), h, "two_factor_login",
		authpage.TwoFactorLoginData{Pending: pending, Error: errorKey}, status)
}

// adminUsername is config.ADMIN_USERNAME: UBYHOST_ADMIN_USERNAME stripped and
// lower-cased, default "admin".
func adminUsername(getenv func(string) string) string {
	raw := getenv("UBYHOST_ADMIN_USERNAME")
	if raw == "" {
		raw = "admin"
	}
	return strings.ToLower(pyStrip(raw))
}

// normaliseStagingSecret is auth._normalise_staging_secret: stripped, one pair
// of matching outer quotes removed.
func normaliseStagingSecret(value string) string {
	text := pyStrip(value)
	if len(text) >= 2 && text[0] == text[len(text)-1] && (text[0] == '"' || text[0] == '\'') {
		text = pyStrip(text[1 : len(text)-1])
	}
	return text
}

// stagingExpectedPassword is auth.staging_expected_password.
func stagingExpectedPassword(getenv func(string) string) string {
	if deployment(getenv) != "staging" {
		return ""
	}
	return normaliseStagingSecret(getenv("UBYHOST_STAGING_LOGIN_PASSWORD"))
}

// stagingPasswordOK is auth.staging_password_ok (constant time).
func stagingPasswordOK(getenv func(string) string, provided string) bool {
	expected := stagingExpectedPassword(getenv)
	if deployment(getenv) != "staging" || expected == "" || provided == "" {
		return false
	}
	given := normaliseStagingSecret(provided)
	if given == "" || utf8.RuneCountInString(given) != utf8.RuneCountInString(expected) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(given), []byte(expected)) == 1
}

// stagingAdminUsername is auth.staging_admin_username.
func (d deps) stagingAdminUsername(ctx context.Context) (string, error) {
	var name string
	err := d.pool.QueryRow(ctx, `SELECT username FROM user_account WHERE role = 'admin' AND active = 1 ORDER BY id LIMIT 1`).Scan(&name)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	if err == nil && pyStrip(name) != "" {
		return pyStrip(name), nil
	}
	if v := adminUsername(d.getenv); v != "" {
		return v, nil
	}
	return "admin", nil
}

// stagingAdminLoginEmail is auth.staging_admin_login_email ("" for None).
func (d deps) stagingAdminLoginEmail(ctx context.Context) (string, error) {
	if deployment(d.getenv) != "staging" {
		return "", nil
	}
	var email *string
	err := d.pool.QueryRow(ctx, `SELECT email FROM user_account WHERE role = 'admin' ORDER BY id LIMIT 1`).Scan(&email)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	if err == nil && email != nil && pyStrip(*email) != "" {
		return pyStrip(*email), nil
	}
	if v := pyStrip(d.getenv("UBYHOST_ADMIN_EMAIL")); v != "" {
		return v, nil
	}
	return authpage.OperatorEmail(d.getenv), nil
}

// stagingAccountForPasswordLogin is auth.staging_account_for_password_login:
// the account named by username, else by e-mail, else the first active admin.
func (d deps) stagingAccountForPasswordLogin(ctx context.Context, username, email string) (*session.LoginAccount, error) {
	if deployment(d.getenv) != "staging" {
		return nil, nil
	}
	var account *session.LoginAccount
	var err error
	if username != "" {
		if account, err = session.AccountByUsername(ctx, d.pool, username); err != nil {
			return nil, err
		}
	}
	if account == nil && email != "" {
		if account, err = session.AccountByEmail(ctx, d.pool, email); err != nil {
			return nil, err
		}
	}
	if account != nil {
		return account, nil
	}
	var id int64
	err = d.pool.QueryRow(ctx, `SELECT id FROM user_account WHERE role = 'admin' AND active = 1 ORDER BY id LIMIT 1`).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return session.AccountByID(ctx, d.pool, id)
}
