package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	accountPath   = "/settings/account#settings-account"
	stayFeePath   = "/settings/account#settings-stay-fee-emails"
	guestMailPath = "/settings/account#settings-guest-details-mail"
	securityPath  = "/settings/security#settings-security"
	loggedOut     = "/login?notice=logged_out"
	suppressScope = "onboarding" // lifecycle_mail.SUPPRESSION_SCOPE
)

// logout is admin_accounts.logout: this browser only.
func (d deps) logout(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	if h != nil {
		if err := d.audit(r.Context(), nil, at, "logout", "", h.Account.Username, ptr(h.Account.ID)); err != nil {
			serverError(w, err)
			return
		}
	}
	http.SetCookie(w, session.ClearSessionCookie(hostweb.SecureCookies(d.getenv)))
	redirect(w, loggedOut)
}

// logoutAll is admin_accounts.logout_all: every device, and the remembered device.
func (d deps) logoutAll(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	if h == nil {
		redirect(w, "/login")
		return
	}
	ctx := r.Context()
	if err := session.EndAllSessions(ctx, d.pool, h.Account.ID); err != nil {
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, nil, at, "logout_all", "", h.Account.Username, ptr(h.Account.ID)); err != nil {
		serverError(w, err)
		return
	}
	sec := hostweb.SecureCookies(d.getenv)
	http.SetCookie(w, session.ClearSessionCookie(sec))
	http.SetCookie(w, clearCookie(session.DeviceCookieName, sec))
	redirect(w, loggedOut)
}

// ownHost is the shared start of the three Settings switches: the account
// holder only (role host, not previewing). h nil means the response is written.
func (d deps) ownHost(w http.ResponseWriter, r *http.Request, back string) *session.Host {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return nil
	}
	h, ok := d.current(w, r, at)
	if !ok {
		return nil
	}
	if h == nil {
		redirect(w, "/login")
		return nil
	}
	if h.Account.Role != "host" || h.Workspace.ID != h.Account.ID {
		hostweb.Back(w, r, back, none, none)
		return nil
	}
	return h
}

// wanted is str(form.get("enabled", "")) == "1" (not stripped).
func wanted(r *http.Request) bool {
	v, _ := formLast(r, "enabled")
	return v == "1"
}

// onboardingEmails is onboarding_emails_submit (lifecycle_mail.set_opt_out / resubscribe).
func (d deps) onboardingEmails(w http.ResponseWriter, r *http.Request) {
	h := d.ownHost(w, r, accountPath)
	if h == nil {
		return
	}
	on := wanted(r)
	ctx := r.Context()
	at := d.now()
	var current int64
	if err := d.pool.QueryRow(ctx, `SELECT onboarding_emails_opt_out FROM user_account WHERE id = $1`, h.Account.ID).Scan(&current); err != nil {
		serverError(w, err)
		return
	}
	optOut := !on
	if (current != 0) != optOut {
		flag := int64(0)
		action := "onboarding_emails_opted_in"
		if optOut {
			flag, action = 1, "onboarding_emails_opted_out"
		}
		if _, err := d.pool.Exec(ctx, `UPDATE user_account SET onboarding_emails_opt_out = $1, onboarding_emails_opt_out_at = $2 WHERE id = $3`,
			flag, session.UTCNow(at), h.Account.ID); err != nil {
			serverError(w, err)
			return
		}
		if err := d.audit(ctx, nil, at, action, "", h.Account.Username, ptr(h.Account.ID)); err != nil {
			serverError(w, err)
			return
		}
	}
	key := "flash.accounts.onboarding_emails_off"
	if on {
		key = "flash.accounts.onboarding_emails_on"
		if err := d.unsuppress(r, h.Account.ID); err != nil {
			serverError(w, err)
			return
		}
	}
	hostweb.Back(w, r, accountPath, flashFor(r, key), none)
}

// unsuppress is the second half of lifecycle_mail.resubscribe: drop the
// onboarding suppression of every contact address of the workspace.
func (d deps) unsuppress(r *http.Request, userID int64) error {
	ctx := r.Context()
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		return err
	}
	rows, err := d.pool.Query(ctx, `SELECT contact_email FROM legal_entity WHERE owner_user_id = $1 ORDER BY id`, userID)
	if err != nil {
		return err
	}
	var found []string
	for rows.Next() {
		var raw *string
		if err := rows.Scan(&raw); err != nil {
			rows.Close()
			return err
		}
		if raw == nil {
			continue
		}
		if addr := normaliseEmail(*raw); addr != "" && !contains(found, addr) {
			found = append(found, addr)
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, addr := range found {
		if _, err := d.pool.Exec(ctx, `DELETE FROM mail_suppression WHERE email_hash = $1 AND scope = $2`,
			EmailHash(secret, addr), suppressScope); err != nil {
			return err
		}
	}
	return nil
}

func contains(list []string, s string) bool {
	for _, v := range list {
		if v == s {
			return true
		}
	}
	return false
}

// EmailHash is lifecycle_mail.email_hash for a normalised address.
func EmailHash(secret, normalised string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte("mail-suppression\x00" + normalised))
	return hex.EncodeToString(m.Sum(nil))
}

var emailRE = regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)

// normaliseEmail is mail.normalise_email for the two forms a contact address
// takes: a bare address or "Name <addr>" (as ubyport.normaliseEmail).
func normaliseEmail(raw string) string {
	s := pyStrip(raw)
	if strings.ContainsAny(s, ",\"") || strings.Count(s, "<") > 1 || strings.Count(s, ">") > 1 {
		return ""
	}
	addr := s
	if i := strings.Index(s, "<"); i >= 0 {
		j := strings.Index(s, ">")
		if j < i || pyStrip(s[j+1:]) != "" {
			return ""
		}
		addr = s[i+1 : j]
	}
	addr = strings.ToLower(pyStrip(addr))
	if addr == "" || !emailRE.MatchString(addr) || utf8.RuneCountInString(addr) > 254 {
		return ""
	}
	return addr
}

// stayFeeEmails is stay_fee_emails_submit (stay_fee_auto.set_emails_enabled).
// Its audit row names no owner and no require_login ran, so owner is NULL.
func (d deps) stayFeeEmails(w http.ResponseWriter, r *http.Request) {
	h := d.ownHost(w, r, stayFeePath)
	if h == nil {
		return
	}
	on := wanted(r)
	ctx := r.Context()
	at := d.now()
	flag, stamp, action, key := int64(1), any(session.UTCNow(at)), "stay_fee_emails_off", "flash.accounts.stay_fee_emails_off"
	if on {
		flag, stamp, action, key = 0, nil, "stay_fee_emails_on", "flash.accounts.stay_fee_emails_on"
	}
	if _, err := d.pool.Exec(ctx, `UPDATE user_account SET stay_fee_emails_opt_out = $1, stay_fee_emails_opt_out_at = $2 WHERE id = $3`,
		flag, stamp, h.Account.ID); err != nil {
		serverError(w, err)
		return
	}
	detail := "user_id=" + itoa(h.Account.ID) + " by=" + h.Account.Username
	if err := d.audit(ctx, nil, at, action, detail, h.Account.Username, nil); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, stayFeePath, flashFor(r, key), none)
}

// guestDetailsMail is guest_details_mail_submit (guest_mail_pref.set_full_details).
func (d deps) guestDetailsMail(w http.ResponseWriter, r *http.Request) {
	h := d.ownHost(w, r, guestMailPath)
	if h == nil {
		return
	}
	on := wanted(r)
	ctx := r.Context()
	at := d.now()
	flag, action, key := int64(0), "guest_details_mail_off", "flash.accounts.guest_details_mail_off"
	if on {
		flag, action, key = 1, "guest_details_mail_on", "flash.accounts.guest_details_mail_on"
	}
	if _, err := d.pool.Exec(ctx, `UPDATE user_account SET guest_details_mail = $1 WHERE id = $2`, flag, h.Account.ID); err != nil {
		serverError(w, err)
		return
	}
	detail := "user_id=" + itoa(h.Account.ID) + " by=" + h.Account.Username
	if err := d.audit(ctx, nil, at, action, detail, h.Account.Username, ptr(h.Account.ID)); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, guestMailPath, flashFor(r, key), none)
}

// secondFactor is the shared body of two_factor_move and two_factor_disable,
// up to and including reset_totp. done is true when the response is written.
func (d deps) secondFactor(w http.ResponseWriter, r *http.Request, notEnabled, failPath, failAction string) (h *session.Host, account *session.LoginAccount, done bool) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return nil, nil, true
	}
	h, ok := d.login(w, r, at)
	if !ok {
		return nil, nil, true
	}
	ctx := r.Context()
	account, err := session.AccountByID(ctx, d.pool, h.Account.ID)
	if err != nil || account == nil {
		serverError(w, errOr(err))
		return nil, nil, true
	}
	if account.TOTPEnabled == 0 {
		hostweb.Back(w, r, notEnabled, none, none)
		return nil, nil, true
	}
	blocked, err := session.Account2FABlocked(ctx, d.pool, account.ID, at)
	if err != nil {
		serverError(w, err)
		return nil, nil, true
	}
	if blocked {
		hostweb.Back(w, r, failPath, none, flashFor(r, "auth.error.code_locked"))
		return nil, nil, true
	}
	good, err := session.VerifySecondFactor(ctx, d.pool, d.getenv, account, formStr(r, "code", ""), at)
	if err != nil {
		serverError(w, err)
		return nil, nil, true
	}
	if !good {
		if err := session.RecordAccount2FAFailure(ctx, d.pool, account.ID, at); err != nil {
			serverError(w, err)
			return nil, nil, true
		}
		if err := d.audit(ctx, &gated{h}, at, failAction, "", account.Username, ptr(account.ID)); err != nil {
			serverError(w, err)
			return nil, nil, true
		}
		hostweb.Back(w, r, failPath, none, flashFor(r, "auth.error.code_invalid"))
		return nil, nil, true
	}
	if err := session.ResetTOTP(ctx, d.pool, account.ID); err != nil {
		serverError(w, err)
		return nil, nil, true
	}
	refreshed, err := session.AccountByID(ctx, d.pool, account.ID)
	if err != nil || refreshed == nil {
		serverError(w, errOr(err))
		return nil, nil, true
	}
	return h, refreshed, false
}

// twoFactorMove is two_factor_move: the old phone proves itself, setup runs
// again; the new cookie counts as a fresh login (no issued_at).
func (d deps) twoFactorMove(w http.ResponseWriter, r *http.Request) {
	h, refreshed, done := d.secondFactor(w, r, "/account/2fa/setup", "/settings", "two_factor_move_failed")
	if done {
		return
	}
	at := d.now()
	if err := d.audit(r.Context(), &gated{h}, at, "two_factor_moved", "", refreshed.Username, ptr(refreshed.ID)); err != nil {
		serverError(w, err)
		return
	}
	remember := remembers(h.Payload)
	if err := d.attach(w, refreshed.ID, refreshed.SessionVersion, session.IssueOptions{Remember: remember}, at); err != nil {
		serverError(w, err)
		return
	}
	redirect(w, "/account/2fa/setup?moved=1")
}

// twoFactorDisable is two_factor_disable; the new cookie keeps the login time.
func (d deps) twoFactorDisable(w http.ResponseWriter, r *http.Request) {
	h, refreshed, done := d.secondFactor(w, r, securityPath, securityPath, "two_factor_disable_failed")
	if done {
		return
	}
	at := d.now()
	if err := d.audit(r.Context(), &gated{h}, at, "two_factor_disabled", "", refreshed.Username, ptr(refreshed.ID)); err != nil {
		serverError(w, err)
		return
	}
	remember := remembers(h.Payload)
	iat := session.IssuedAt(h.Payload)
	if err := d.attach(w, refreshed.ID, refreshed.SessionVersion, session.IssueOptions{Remember: remember, IssuedAt: &iat}, at); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, securityPath, flashFor(r, "flash.accounts.twofa_disabled"), none)
}

// securityPromptSeen is passkeys.security_prompt_seen: 401 signed out, else 204.
func (d deps) securityPromptSeen(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	if h == nil {
		emptyStatus(w, http.StatusUnauthorized)
		return
	}
	if _, err := d.pool.Exec(r.Context(), `UPDATE user_account SET two_factor_prompted_at = $1 WHERE id = $2 AND two_factor_prompted_at IS NULL`,
		session.UTCNow(at), h.Account.ID); err != nil {
		serverError(w, err)
		return
	}
	emptyStatus(w, http.StatusNoContent)
}
