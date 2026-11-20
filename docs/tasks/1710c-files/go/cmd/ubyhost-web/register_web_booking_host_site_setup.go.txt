package main

// Brief 1710c: host booking-site setup (GET/POST /apartments/{id}/booking-site).
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
		booking.RegisterBookingSiteSetup(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
