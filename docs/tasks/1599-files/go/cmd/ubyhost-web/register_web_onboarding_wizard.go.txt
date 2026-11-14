package main

// Briefs 1599 to 1602: the property setup wizard (App/app/routes/onboarding_wizard.py,
// go/internal/web/onboarding/wizard*.go). Switched off: nothing sends these
// paths here until UBYHOST_GO_PATHS names them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		onboarding.RegisterWizard(mux, m.wrap, pool, os.Getenv, time.Now)
	})
}
