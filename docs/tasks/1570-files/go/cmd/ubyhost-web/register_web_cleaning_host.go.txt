package main

// Cleaning host pages and their form posts (go/internal/web/cleaning, host.go
// and the files after it). Switched off: nothing sends these paths here until
// UBYHOST_GO_PATHS names them. register_web_cleaning.go holds the first routes.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		cleaning.RegisterHost(mux, m.wrap, pool, os.Getenv, time.Now)
	})
}
