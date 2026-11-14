package auth

// The three account writes of the admin customer pages, ported from
// App/app/routes/admin_accounts.py (brief 1504): POST /admin/users (user_create
// 745-771), POST /admin/users/{id}/invite (user_invite 774-785) and POST
// /admin/users/{id}/email (user_email_set 788-851), with _send_invite (731-742).
// Every answer is a 303 back to the customer pages with a flash, as
// admin_helpers.back writes it.

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const customersPath = "/admin/customers"

// adminUserFlash is admin_helpers.flash with params: the key's text in the
// request language, %(name)s filled.
func adminUserFlash(r *http.Request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(hostweb.Lang(r), key, params), Key: key}
}

// adminUserUnique is db.is_unique_violation on PostgreSQL.
func adminUserUnique(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

// adminUserEmail is (account["email"] or ""), the stored login address as it is.
func adminUserEmail(a *session.LoginAccount) string {
	if a.Email == nil {
		return ""
	}
	return *a.Email
}

// sendInvite is _send_invite: a fresh invitation link (purpose invite,
// remember, three days), queued as account_invite in English and sent at
// once with mail.send_now. With mail off nothing is queued or sent.
func (d deps) sendInvite(ctx context.Context, target *session.LoginAccount, at time.Time) error {
	token, err := session.IssueLoginLink(ctx, d.pool, target, session.PurposeInvite, "", true, "/", at)
	if err != nil {
		return err
	}
	id, err := mail.QueueLinkMail(ctx, d.pool, d.getenv, mail.KindAccountInvite, target.ID, adminUserEmail(target),
		token, session.LinkTTL[session.PurposeInvite]/60, "", at)
	if err != nil {
		return err
	}
	return mail.SendNow(ctx, d.pool, d.getenv, id)
}

// userCreate is user_create: a new host account for the e-mail, then its
// invitation.
func (d deps) userCreate(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	email := normaliseEmail(formStr(r, "email", ""))
	if email == "" {
		hostweb.Back(w, r, customersPath, none, flashFor(r, "users.email.error.invalid"))
		return
	}
	ctx := r.Context()
	taken, err := session.EmailTaken(ctx, d.pool, email, 0)
	if err != nil {
		serverError(w, err)
		return
	}
	if taken {
		hostweb.Back(w, r, customersPath, none, flashFor(r, "users.email.error.taken"))
		return
	}
	userID, err := session.CreateAccount(ctx, d.pool, email, formStr(r, "display_name", ""), "host", "", at)
	switch {
	case errors.Is(err, session.ErrEmailInvalid), errors.Is(err, session.ErrUnknownRole), errors.Is(err, session.ErrUsername):
		// auth raises catalogue keys; the message is resolved in the page language.
		hostweb.Back(w, r, customersPath, none, flashFor(r, err.Error()))
		return
	case adminUserUnique(err):
		hostweb.Back(w, r, customersPath, none, flashFor(r, "users.email.error.taken"))
		return
	case err != nil:
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, &gated{h}, at, "user_created", "user="+itoa(userID), h.Account.Username, ptr(userID)); err != nil {
		serverError(w, err)
		return
	}
	target, err := session.AccountByID(ctx, d.pool, userID)
	if err != nil || target == nil {
		serverError(w, errOr(err))
		return
	}
	if err := d.sendInvite(ctx, target, at); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, customersPath, adminUserFlash(r, "users.invite.sent", map[string]any{"email": email}), none)
}

// userInvite is user_invite: a fresh invitation for a host who never used theirs.
func (d deps) userInvite(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	userID, ok := pathID(w, r, "user_id")
	if !ok {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	back := customersPath + "/" + itoa(userID)
	ctx := r.Context()
	target, err := session.AccountByID(ctx, d.pool, userID)
	if err != nil {
		serverError(w, err)
		return
	}
	if target == nil || pyStrip(adminUserEmail(target)) == "" {
		hostweb.Back(w, r, back, none, flashFor(r, "users.invite.no_email"))
		return
	}
	if err := d.sendInvite(ctx, target, at); err != nil {
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, &gated{h}, at, "invite_sent", "", h.Account.Username, ptr(userID)); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, back, adminUserFlash(r, "users.invite.sent", map[string]any{"email": adminUserEmail(target)}), none)
}

// userEmailSet is user_email_set: set a first login address, or change one
// (with a support reason, a notice to both addresses, every session ended;
// the admin's own browser gets a fresh session).
func (d deps) userEmailSet(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	userID, ok := pathID(w, r, "user_id")
	if !ok {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	back := customersPath + "/" + itoa(userID)
	ctx := r.Context()
	var stored *string
	err := d.pool.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, userID).Scan(&stored)
	if errors.Is(err, pgx.ErrNoRows) {
		hostweb.Back(w, r, back, none, flashFor(r, "users.email.error.not_found"))
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	email := normaliseEmail(formStr(r, "email", ""))
	if email == "" {
		hostweb.Back(w, r, back, none, flashFor(r, "users.email.error.invalid"))
		return
	}
	oldEmail := ""
	if stored != nil {
		oldEmail = strings.ToLower(pyStrip(*stored))
	}
	if email == oldEmail {
		hostweb.Back(w, r, back, flashFor(r, "users.email.unchanged"), none)
		return
	}
	reason := ""
	if oldEmail != "" {
		if reason = supportReason(formStr(r, "reason", "")); reason == "" {
			hostweb.Back(w, r, back, none, flashFor(r, "users.email.error.reason"))
			return
		}
	}
	taken, err := session.EmailTaken(ctx, d.pool, email, userID)
	if err != nil {
		serverError(w, err)
		return
	}
	if taken {
		hostweb.Back(w, r, back, none, flashFor(r, "users.email.error.taken"))
		return
	}
	if err := session.SetAccountEmail(ctx, d.pool, userID, email, at); err != nil {
		if adminUserUnique(err) {
			hostweb.Back(w, r, back, none, flashFor(r, "users.email.error.taken"))
			return
		}
		serverError(w, err)
		return
	}
	action, detail := "email_set", "to="+mail.MaskEmail(email)
	if oldEmail != "" {
		action, detail = "email_changed", "from="+mail.MaskEmail(oldEmail)+" "+detail+" reason="+reason
	}
	if err := d.audit(ctx, &gated{h}, at, action, detail, h.Account.Username, ptr(userID)); err != nil {
		serverError(w, err)
		return
	}
	if oldEmail != "" {
		if _, err := mail.QueueEmailChanged(ctx, d.pool, d.getenv, userID, oldEmail, email, session.UTCNow(at), "support", true, at); err != nil {
			serverError(w, err)
			return
		}
	}
	if oldEmail != "" && userID == h.Account.ID {
		// The change ended every session of this account, the admin's own
		// included; hand this browser a fresh one (no workspace, the same
		// login time and "remember me").
		var sv int64
		if err := d.pool.QueryRow(ctx, `SELECT session_version FROM user_account WHERE id = $1`, userID).Scan(&sv); err != nil {
			serverError(w, err)
			return
		}
		iat := session.IssuedAt(h.Payload)
		if err := d.attach(w, userID, sv, session.IssueOptions{Remember: remembers(h.Payload), IssuedAt: &iat}, at); err != nil {
			serverError(w, err)
			return
		}
	}
	hostweb.Back(w, r, back, flashFor(r, "users.email.saved"), none)
}
