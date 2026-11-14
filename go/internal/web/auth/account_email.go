package auth

// The login address change of App/app/routes/admin_accounts.py (brief 1506):
// POST /account/email (account_email_request 612-653) mails a confirmation
// link to the new address; GET and POST /account/email/confirm
// (account_email_confirm_form 663-669, account_email_confirm_submit
// 672-713) show the confirm button and make the change, ending every
// session and telling the old address.

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgconn"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// acctEmailPurposes is (login_link.EMAIL_CHANGE,).
var acctEmailPurposes = []string{session.PurposeEmailChange}

type acctEmailData struct {
	Expired      bool
	Token, Email string
}

// accountEmailRequest is account_email_request (POST /account/email). A
// taken address gets the same answer as a free one and no mail, so the form
// does not tell which addresses other accounts use.
func (d deps) accountEmailRequest(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.login(w, r, at)
	if !ok {
		return
	}
	if h.Impersonating {
		hostweb.Back(w, r, accountPath, none, acctFlash(r, "auth.error.admins_only", nil))
		return
	}
	if !session.IsFresh(h.Payload, 0, at) {
		hostweb.Back(w, r, accountPath, none, acctFlash(r, "auth.error.recent_login", nil))
		return
	}
	ctx := r.Context()
	account, err := session.AccountByID(ctx, d.pool, h.Account.ID)
	if err != nil || account == nil {
		serverError(w, errOr(err))
		return
	}
	email := normaliseEmail(formStr(r, "email", ""))
	if email == "" {
		hostweb.Back(w, r, accountPath, none, acctFlash(r, "users.email.error.invalid", nil))
		return
	}
	current := ""
	if account.Email != nil {
		current = session.NormaliseUsername(*account.Email) // (email or "").strip().lower()
	}
	if email == current {
		hostweb.Back(w, r, accountPath, acctFlash(r, "users.email.unchanged", nil), none)
		return
	}
	ipKey := clientip.Key(r, d.getenv, "")
	blocked, err := session.LinkRequestBlocked(ctx, d.pool, ipKey, email, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		hostweb.Back(w, r, accountPath, none, acctFlash(r, "auth.error.link_rate_limited", nil))
		return
	}
	if err := session.LinkRecordRequest(ctx, d.pool, ipKey, email, at); err != nil {
		serverError(w, err)
		return
	}
	taken, err := session.EmailTaken(ctx, d.pool, email, account.ID)
	if err != nil {
		serverError(w, err)
		return
	}
	var outboxID int64
	if !taken {
		token, err := session.IssueLoginLink(ctx, d.pool, account, session.PurposeEmailChange, email, false, "", at)
		if err != nil {
			serverError(w, err)
			return
		}
		outboxID, err = mail.QueueLinkMail(ctx, d.pool, d.getenv, mail.KindEmailConfirm, account.ID, email, token,
			session.LinkTTL[session.PurposeEmailChange]/60, hostweb.Lang(r), at)
		if err != nil {
			serverError(w, err)
			return
		}
		if err := d.audit(ctx, &gated{h}, at, "email_change_requested", "to="+mail.MaskEmail(email),
			h.Account.Username, ptr(account.ID)); err != nil {
			serverError(w, err)
			return
		}
	}
	hostweb.Back(w, r, accountPath, acctFlash(r, "settings.account.email_sent", map[string]any{"email": email}), none)
	if !taken {
		pool, getenv := d.pool, d.getenv
		acctBackground(func() { _ = acctSendNow(context.Background(), pool, getenv, outboxID) })
	}
}

// acctEmailPage is _email_confirm_page: the page with no-store and no-referrer.
func (d deps) acctEmailPage(w http.ResponseWriter, r *http.Request, data acctEmailData, status int, at time.Time) {
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Referrer-Policy", "no-referrer")
	d.acctPageOr500(w, r, acctPage{Name: "account_email_confirm", TitleKey: "account.email_confirm.page_title",
		Status: status, LangNext: "/login", SignedIn: h != nil, Data: data}, at)
}

// accountEmailConfirmForm is account_email_confirm_form (GET
// /account/email/confirm?t=): a button, so a mail scanner that opens the
// link does not make the change.
func (d deps) accountEmailConfirmForm(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	ctx := r.Context()
	token := acctLastQuery(r, "t")
	row, err := session.PeekLoginLink(ctx, d.pool, token, acctEmailPurposes, at)
	if err != nil {
		serverError(w, err)
		return
	}
	account, err := session.AccountForLink(ctx, d.pool, row)
	if err != nil {
		serverError(w, err)
		return
	}
	if row == nil || account == nil {
		d.acctEmailPage(w, r, acctEmailData{Expired: true}, http.StatusGone, at)
		return
	}
	d.acctEmailPage(w, r, acctEmailData{Token: token, Email: row.Email}, http.StatusOK, at)
}

// accountEmailConfirmSubmit is account_email_confirm_submit (POST
// /account/email/confirm): spend the link, make the new address the login
// address (every session ends), mark it verified, audit, tell the old
// address, and send the visitor to log in again.
func (d deps) accountEmailConfirmSubmit(w http.ResponseWriter, r *http.Request) {
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
		d.acctEmailPage(w, r, acctEmailData{Expired: true}, http.StatusTooManyRequests, at)
		return
	}
	row, err := session.ConsumeLoginLink(ctx, d.pool, token, acctEmailPurposes, at)
	if err != nil {
		serverError(w, err)
		return
	}
	account, err := session.AccountForLink(ctx, d.pool, row)
	if err != nil {
		serverError(w, err)
		return
	}
	taken := false
	if account != nil {
		if taken, err = session.EmailTaken(ctx, d.pool, row.Email, account.ID); err != nil {
			serverError(w, err)
			return
		}
	}
	if account == nil || taken {
		if err := session.LinkRecordConsumeFailure(ctx, d.pool, ipKey, at); err != nil {
			serverError(w, err)
			return
		}
		d.acctEmailPage(w, r, acctEmailData{Expired: true}, http.StatusGone, at)
		return
	}
	oldEmail := ""
	if account.Email != nil {
		oldEmail = session.NormaliseUsername(*account.Email)
	}
	if err := session.SetAccountEmail(ctx, d.pool, account.ID, row.Email, at); err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			d.acctEmailPage(w, r, acctEmailData{Expired: true}, http.StatusGone, at)
			return
		}
		serverError(w, err)
		return
	}
	stamp := session.UTCNow(at)
	if _, err := d.pool.Exec(ctx, `UPDATE user_account SET email_verified_at = $1 WHERE id = $2`, stamp, account.ID); err != nil {
		serverError(w, err)
		return
	}
	detail := "from=" + mail.MaskEmail(oldEmail) + " to=" + mail.MaskEmail(row.Email) + " by=self"
	if err := d.audit(ctx, nil, at, "email_changed", detail, account.Username, ptr(account.ID)); err != nil {
		serverError(w, err)
		return
	}
	if _, err := mail.QueueEmailChanged(ctx, d.pool, d.getenv, account.ID, oldEmail, row.Email, stamp, "self", false, at); err != nil {
		serverError(w, err)
		return
	}
	http.SetCookie(w, session.ClearSessionCookie(hostweb.SecureCookies(d.getenv)))
	redirect(w, "/login?notice=email_changed")
}
