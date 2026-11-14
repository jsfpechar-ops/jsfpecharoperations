package main

// Brief 1520: POST /alerts/{id}/dismiss, GET /smart-locks, GET /menu
// (go/internal/web/properties). Switched off: nothing sends these paths here
// until UBYHOST_GO_PATHS names them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		properties.RegisterMisc(mux, m.wrap, pool, os.Getenv, time.Now)
	})
}
