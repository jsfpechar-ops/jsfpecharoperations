package auth

// GET /admin/operations (operations_admin, admin_accounts.py 929-950), brief
// 1508. The page itself is in package opspage; this is the admin gate.

import (
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth/opspage"
)

// operationsAdmin is operations_admin: _require_admin, then the System page.
func (d deps) operationsAdmin(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	if err := opspage.Serve(w, r, d.pool, d.getenv, at, h); err != nil {
		serverError(w, err)
	}
}
