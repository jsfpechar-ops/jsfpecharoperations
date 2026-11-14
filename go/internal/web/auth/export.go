package auth

// Brief 1510: POST /admin/users/{id}/export (user_workspace_export,
// admin_accounts.py 1013-1039). Dormant until the path is in UBYHOST_GO_PATHS.
// identity_visible is always true for admins (_require_admin already ran); not ported.

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/exports"
)

// workspaceExport streams a ZIP of the workspace for an admin with a fresh login.
func (d deps) workspaceExport(w http.ResponseWriter, r *http.Request) {
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
	if !session.IsFresh(h.Payload, 0, at) {
		hostweb.Back(w, r, "/settings/security#settings-security", none, flashFor(r, "auth.error.recent_login"))
		return
	}
	ctx := r.Context()
	back := "/admin/customers/" + itoa(userID)
	var found int64
	err := d.pool.QueryRow(ctx, `SELECT id FROM user_account WHERE id = $1`, userID).Scan(&found)
	if err == pgx.ErrNoRows {
		hostweb.Back(w, r, back, none, flashFor(r, "flash.error.no_such_user"))
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	path, err := exports.BuildWorkspaceZip(ctx, d.pool, d.getenv, userID, at)
	if err != nil {
		serverError(w, err)
		return
	}
	defer os.Remove(path)
	if err := d.audit(ctx, &gated{h}, at, "workspace_exported", "user="+itoa(userID),
		h.Account.Username, ptr(userID)); err != nil {
		serverError(w, err)
		return
	}
	f, err := os.Open(path)
	if err != nil {
		serverError(w, err)
		return
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		serverError(w, err)
		return
	}
	w.Header().Set("Content-Type", "application/zip")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="workspace-%d.zip"`, userID))
	w.Header().Set("Content-Length", strconv.FormatInt(info.Size(), 10))
	w.WriteHeader(http.StatusOK)
	_, _ = io.Copy(w, f)
}
