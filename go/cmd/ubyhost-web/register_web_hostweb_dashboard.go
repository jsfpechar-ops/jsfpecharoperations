package main

// Brief 1751: GET / (landing, app login at /, signed-in dashboard). Dormant
// until the path is added to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/hostweb"
)

func init() {
	registerRoutes(registerWebHostwebDashboard)
}

func registerWebHostwebDashboard(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	// Exact root only ({ $ } disambiguates from the method-only catch-all patterns).
	mux.Handle("GET /{$}", m.wrap("/", hostweb.DashboardHandler(pool, os.Getenv, os.LookupEnv, time.Now)))
	mux.Handle("POST /dashboard/dismiss-guest-link-nudge", m.wrap("/dashboard/dismiss-guest-link-nudge", hostweb.DismissGuestLinkNudgeHandler(pool, os.Getenv, time.Now)))
}
