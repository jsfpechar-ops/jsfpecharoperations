package main

// Web thread "customer admin" owns this file: the customer list and detail pages
// (briefs 1361, 1364), the funnel redirect and the account toggle. The port stays off until
// a path is routed to Go.

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
	})
}
