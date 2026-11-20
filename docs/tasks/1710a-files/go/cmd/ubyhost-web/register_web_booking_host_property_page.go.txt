package main

// Brief 1710a: host property page review routes (GET/POST page, photo move/delete).
// Dormant until the owner adds these paths to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		booking.RegisterPropertyPageHost(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
