package main

// Brief 1710d: POST .../booking-site/pay, /confirm, /decline, /cancel.
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
		booking.RegisterBookingSiteActions(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
