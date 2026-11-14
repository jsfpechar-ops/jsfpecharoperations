package main

// Brief 1595: the onboarding checklist page (GET /onboarding). It stays off
// until the owner adds the path to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

func init() {
	registerRoutes(registerWebOnboardingPage)
}

// registerWebOnboardingPage mounts routes/onboarding.py onboarding_view. It
// must not use the pool while it builds.
func registerWebOnboardingPage(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("GET /onboarding", m.wrap("/onboarding", onboarding.OnboardingPageHandler(pool, os.Getenv, os.LookupEnv, time.Now)))
}
