package main

// Brief 1320/1321 owns this file: the host download routes of
// App/app/routes/exports.py, ported in go/internal/web/exports. They stay on
// Python until the owner adds their paths to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/exports"
)

func init() {
	registerRoutes(registerWebExports)
}

// registerWebExports adds the export routes. It must not use the pool.
func registerWebExports(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	for _, route := range exports.Routes(pool, os.Getenv, time.Now) {
		mux.Handle(route.Pattern, m.wrap(route.Label, route.Handler))
	}
}
