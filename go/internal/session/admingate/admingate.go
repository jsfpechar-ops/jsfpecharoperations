// Package admingate is _require_admin (App/app/routes/admin_accounts.py
// 716-723): require_login, then 403 for an account that is not an admin
// (brief 1280). It lives apart from session because hostweb imports session.
package admingate

import (
	"io"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// AdminsOnlyTexts are auth.error.admins_only in host_i18n.py (en, cs) and
// host_vi_i18n.py (vi). The test checks them against those files.
var AdminsOnlyTexts = map[string]string{
	"en": "Administrators only.",
	"cs": "Pouze pro administrátory.",
	"vi": "Chỉ dành cho quản trị viên.",
}

// Require returns the signed-in admin's host, or nil when it has written the
// response (login redirect, or the 403). Python checks current_user, the real
// account, so an admin previewing a host workspace still passes. The 403 is
// Starlette's Response(text, status_code=403): the UTF-8 text with no
// Content-Type header.
func Require(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, error) {
	h, err := hostweb.Login(w, r, pool, getenv, at)
	if h == nil || err != nil {
		return nil, err
	}
	if h.Account.Role != "admin" {
		text, ok := AdminsOnlyTexts[hostweb.Lang(r)]
		if !ok {
			text = AdminsOnlyTexts["en"]
		}
		w.Header()["Content-Type"] = nil
		w.WriteHeader(http.StatusForbidden)
		_, _ = io.WriteString(w, text)
		return nil, nil
	}
	return h, nil
}
