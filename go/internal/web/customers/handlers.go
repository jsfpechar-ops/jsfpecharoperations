package customers

import (
	_ "embed"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the host strings this package reads. The golden test checks it
// against host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

// page is routes/admin_customers.PAGE.
const page = "/admin/customers"

// requireAdmin is _require_admin (routes/admin_accounts.py): the signed-in
// real account must be an admin, so an impersonating admin passes. It returns
// ok=false after writing the response (a login redirect, the 403 text or a
// 500). It is replaced by admingate.Require in a later brief.
func requireAdmin(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(w, r, pool, getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	if h.Account.Role != "admin" {
		// Starlette's Response(text, 403) sends no Content-Type; a nil value
		// stops net/http from adding one.
		w.Header()["Content-Type"] = nil
		w.WriteHeader(http.StatusForbidden)
		_, _ = io.WriteString(w, catalog.T(hostweb.Lang(r), "auth.error.admins_only", nil))
		return nil, false
	}
	return h, true
}

// FunnelHandler serves GET /admin/funnel (admin_accounts.funnel_admin): the
// funnel moved into Reports on the billing page.
func FunnelHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if _, ok := requireAdmin(w, r, pool, getenv, now()); !ok {
			return
		}
		w.Header().Set("Location", "/admin/fakturace#reports")
		w.WriteHeader(http.StatusSeeOther)
	}
}

// ToggleActiveHandler serves POST /admin/customers/{user_id}/aktivovat
// (admin_customers.customer_toggle_active). The CSRF check runs first, as the
// Python app-wide dependency does.
func ToggleActiveHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		admin, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		userID, err := strconv.ParseInt(r.PathValue("user_id"), 10, 64)
		if err != nil {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return
		}
		ctx := r.Context()
		var username string
		var wasActive int64
		err = pool.QueryRow(ctx, "SELECT username, active FROM user_account WHERE id = $1", userID).Scan(&username, &wasActive)
		if errors.Is(err, pgx.ErrNoRows) {
			// HTTPException(404) answers FastAPI's JSON body.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
			return
		}
		if err != nil {
			serverError(w, err)
			return
		}
		back := fmt.Sprintf("%s/%d", page, userID)
		lang := hostweb.Lang(r)
		if userID == admin.Account.ID {
			key := "auth.error.own_disable"
			hostweb.Back(w, r, back, hostweb.Flash{}, hostweb.Flash{Text: catalog.T(lang, key, nil), Key: key})
			return
		}
		active, action, key := int64(1), "user_enabled", "customers.ops.enabled"
		if wasActive != 0 {
			active, action, key = 0, "user_disabled", "customers.ops.disabled"
		}
		if err := setActive(r, pool, admin, userID, active, action, at); err != nil {
			serverError(w, err)
			return
		}
		msg := catalog.T(lang, key, map[string]any{"username": username})
		hostweb.Back(w, r, back, hostweb.Flash{Text: msg, Key: key}, hostweb.Flash{})
	}
}

// setActive flips the account and writes the audit row in one transaction:
// db.execute UPDATE and db.audit (actor operator:<admin>, the admin's id, and
// impersonator_user_id only while the admin is inside another workspace).
func setActive(r *http.Request, pool *pgxpool.Pool, admin *session.Host, userID, active int64, action string, at time.Time) error {
	ctx := r.Context()
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx,
		"UPDATE user_account SET active = $1, session_version = session_version + 1 WHERE id = $2",
		active, userID); err != nil {
		return err
	}
	var impersonator any
	if admin.Impersonating {
		impersonator = admin.Account.ID
	}
	if _, err := tx.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		stamp(at), "operator:"+admin.Account.Username, action, "", userID, admin.Account.ID, impersonator); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// stamp is db.utcnow: UTC, whole seconds, "+00:00".
func stamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("customers: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}
