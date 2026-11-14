package auth

// Brief 1509: POST /admin/users/{id}/schedule-deletion, ported from
// user_schedule_deletion (App/app/routes/admin_accounts.py 1042-1068).
// Dormant: Caddy sends the path here only once it is in UBYHOST_GO_PATHS.

import (
	"errors"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// workspaceDeletionDays is WORKSPACE_DELETION_DAYS (G-D11).
const workspaceDeletionDays = 30

// deletionFlash is admin_helpers.flash with params, in the request language.
func deletionFlash(r *http.Request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(hostweb.Lang(r), key, params), Key: key}
}

// deletionDue is (datetime.now(timezone.utc) + timedelta(days=30))
// .replace(microsecond=0).isoformat().
func deletionDue(at time.Time) string {
	return session.UTCNow(at.Add(workspaceDeletionDays * 24 * time.Hour))
}

// scheduleDeletion is user_schedule_deletion: an admin sets the account's
// deletion date 30 days ahead, after typing its username. The workspace's
// contact addresses get the "scheduled" notice (mail_notify.workspace_deletion);
// the retention job sends the week-before reminder and deletes, not this route.
func (d deps) scheduleDeletion(w http.ResponseWriter, r *http.Request) {
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
	ctx := r.Context()
	back := "/admin/customers/" + itoa(userID)
	var username *string
	err := d.pool.QueryRow(ctx, `SELECT username FROM user_account WHERE id = $1`, userID).Scan(&username)
	if errors.Is(err, pgx.ErrNoRows) {
		hostweb.Back(w, r, back, none, flashFor(r, "flash.error.no_such_user"))
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	// _form_str(form, "confirm") != target["username"]: a NULL username never matches.
	if username == nil || formStr(r, "confirm", "") != *username {
		hostweb.Back(w, r, back, none, flashFor(r, "flash.error.confirm_username"))
		return
	}
	due := deletionDue(at)
	if _, err := d.pool.Exec(ctx, `UPDATE user_account SET deletion_due_at = $1 WHERE id = $2`, due, userID); err != nil {
		serverError(w, err)
		return
	}
	if _, err := mail.QueueWorkspaceDeletion(ctx, d.pool, d.getenv, userID, due, mail.DeletionScheduled, at); err != nil {
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, &gated{h}, at, "workspace_deletion_scheduled", "user="+itoa(userID)+" due="+due,
		h.Account.Username, ptr(userID)); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, back, deletionFlash(r, "flash.users.deletion_scheduled", map[string]any{"date": due}), none)
}
