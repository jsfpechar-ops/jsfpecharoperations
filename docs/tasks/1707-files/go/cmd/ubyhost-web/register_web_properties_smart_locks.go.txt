package main

// Brief 1707: POST smart-locks routes. Dormant until wave P2.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		properties.RegisterSmartLocks(mux, m.wrap, pool, os.Getenv, time.Now)
	})
}
