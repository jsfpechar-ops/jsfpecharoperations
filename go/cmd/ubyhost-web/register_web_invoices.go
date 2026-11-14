package main

// Web thread "invoice pages" (briefs 1420 to 1429) owns this file: the host
// invoice pages of App/app/routes/invoices.py, ported in
// go/internal/web/invoices. They stay on Python until the owner adds their
// paths to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
)

func init() {
	registerRoutes(registerWebInvoices)
}

// registerWebInvoices adds the invoice routes. It must not use the pool.
func registerWebInvoices(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	for _, route := range invoices.Routes(pool, os.Getenv, time.Now) {
		mux.Handle(route.Pattern, m.wrap(route.Label, route.Handler))
	}
}
