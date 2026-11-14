package main

// Web thread "customer admin" owns this file: the customer list and detail pages
// (briefs 1361, 1364), the funnel redirect, the account toggle and the operator's actions
// and console home (briefs 1590 to 1594). All ten routes of admin_customers.py are here.
// The port stays off until a path is routed to Go.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/customers"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("GET /admin/customers", m.wrap("/admin/customers", customers.ListHandler(pool, os.Getenv, time.Now)))
		mux.Handle("GET /admin/customers/{user_id}", m.wrap("/admin/customers/{user_id}", customers.DetailHandler(pool, os.Getenv, time.Now)))
		mux.Handle("GET /admin/funnel", m.wrap("/admin/funnel", customers.FunnelHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/aktivovat", m.wrap("/admin/customers/{user_id}/aktivovat", customers.ToggleActiveHandler(pool, os.Getenv, time.Now)))
		mux.Handle("GET /admin", m.wrap("/admin", customers.HomeHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/stav", m.wrap("/admin/customers/{user_id}/stav", customers.StatusHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/prodlouzit", m.wrap("/admin/customers/{user_id}/prodlouzit", customers.ExtendTrialHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/overit-znovu", m.wrap("/admin/customers/{user_id}/overit-znovu", customers.ResendVerificationHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/sleva", m.wrap("/admin/customers/{user_id}/sleva", customers.DiscountHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/plan", m.wrap("/admin/customers/{user_id}/plan", customers.PlanChangeHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /admin/customers/{user_id}/priradit", m.wrap("/admin/customers/{user_id}/priradit", customers.AssignPlanHandler(pool, os.Getenv, time.Now)))
	})
}
