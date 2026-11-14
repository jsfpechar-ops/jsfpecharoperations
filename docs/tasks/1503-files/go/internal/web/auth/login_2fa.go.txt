package auth

// The second step of a login with an authenticator, ported from
// App/app/routes/admin_accounts.py two_factor_login (275-316) and the login
// limits of App/app/rate_limit.py (login_blocked 66-70, record_login_failure
// 73-76) (brief 1503). GET /login/2fa is twoFactorLoginGet (brief 1282); the
// page itself is renderTwoFactorLogin (brief 1502).

import (
	"net/http"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// rate_limit._WINDOW_SECONDS, _LOGIN_MAX_FAILURES and _LOGIN_IP_MAX_FAILURES.
const (
	loginFailWindow   = 15 * 60
	loginFailMax      = 12
	loginFailIPMax    = 30
	loginFailScope    = "login_fail"
	loginFailIPScope  = "login_fail_ip"
	twoFactorLocked   = "auth.error.code_locked"
	twoFactorBadCode  = "auth.error.code_invalid"
	twoFactorExpired  = "/login?notice=2fa_expired"
	twoFactorStartURL = "/login"
)

// loginBlocked is rate_limit.login_blocked(client_key, ip_key): the per
// account-and-address budget, then (ipKey is never empty here) the per
// address one; each check prunes its old rows first, as Python's does.
func (d deps) loginBlocked(r *http.Request, clientKey, ipKey string, at time.Time) (bool, error) {
	ctx := r.Context()
	if b, err := session.RateBlocked(ctx, d.pool, loginFailScope, clientKey, loginFailMax, loginFailWindow, at); b || err != nil {
		return b, err
	}
	if ipKey == "" {
		return false, nil
	}
	return session.RateBlocked(ctx, d.pool, loginFailIPScope, ipKey, loginFailIPMax, loginFailWindow, at)
}

// recordLoginFailure is rate_limit.record_login_failure(client_key, ip_key).
func (d deps) recordLoginFailure(r *http.Request, clientKey, ipKey string, at time.Time) error {
	if err := session.RateRecord(r.Context(), d.pool, loginFailScope, clientKey, at); err != nil {
		return err
	}
	if ipKey == "" {
		return nil
	}
	return session.RateRecord(r.Context(), d.pool, loginFailIPScope, ipKey, at)
}

// pendingUserID is pending["uid"] as the SQL parameter Python passes: the
// integer the signed token carries; anything else matches no account.
func pendingUserID(p map[string]any) (int64, bool) {
	switch v := p["uid"].(type) {
	case int64:
		return v, true
	case float64:
		if v == float64(int64(v)) {
			return int64(v), true
		}
	}
	return 0, false
}

// pendingNext is str(pending.get("next") or "/").
func pendingNext(p map[string]any) string {
	if s, ok := p["next"].(string); ok && s != "" {
		return s
	}
	return "/"
}

// twoFactorLogin is two_factor_login: check the code against the account the
// pending token names, under the login and per-account 2FA limits, then
// finish the login (method link+totp, action two_factor_login).
func (d deps) twoFactorLogin(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	raw := formStr(r, "pending", "")
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		serverError(w, err)
		return
	}
	pending, ok := session.ReadTwoFactorPending(secret, raw, at)
	if !ok {
		// The pending token lives 10 minutes, shorter than the 15-minute
		// lockout: say so instead of a bare login form.
		redirect(w, twoFactorExpired)
		return
	}
	ctx := r.Context()
	var account *session.LoginAccount
	if uid, ok := pendingUserID(pending); ok {
		if account, err = session.AccountByID(ctx, d.pool, uid); err != nil {
			serverError(w, err)
			return
		}
	}
	if account == nil {
		redirect(w, twoFactorStartURL)
		return
	}
	clientKey := clientip.Key(r, d.getenv, account.Username+":2fa")
	ipKey := clientip.Key(r, d.getenv, "")
	blocked, err := d.loginBlocked(r, clientKey, ipKey, at)
	if err == nil && !blocked {
		blocked, err = session.Account2FABlocked(ctx, d.pool, account.ID, at)
	}
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		if err := d.renderTwoFactorLogin(w, r, raw, twoFactorLocked, http.StatusTooManyRequests); err != nil {
			serverError(w, err)
		}
		return
	}
	good, err := session.VerifySecondFactor(ctx, d.pool, d.getenv, account, formStr(r, "code", ""), at)
	if err != nil {
		serverError(w, err)
		return
	}
	if !good {
		if err := d.recordLoginFailure(r, clientKey, ipKey, at); err != nil {
			serverError(w, err)
			return
		}
		if err := session.RecordAccount2FAFailure(ctx, d.pool, account.ID, at); err != nil {
			serverError(w, err)
			return
		}
		if err := d.audit(ctx, nil, at, "two_factor_failed", "", account.Username, ptr(account.ID)); err != nil {
			serverError(w, err)
			return
		}
		if err := d.renderTwoFactorLogin(w, r, raw, twoFactorBadCode, http.StatusUnauthorized); err != nil {
			serverError(w, err)
		}
		return
	}
	if err := d.finishLogin(w, r, account, remembers(pending), pendingNext(pending), MethodLinkTOTP, ActionTwoFactorLogin, at); err != nil {
		serverError(w, err)
	}
}
