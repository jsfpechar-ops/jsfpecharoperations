package main

// Brief 1596: the demo reset route (POST /demo/reset). It stays off until the
// owner adds the path to UBYHOST_GO_PATHS. POST /demo (demo.seed) is not in
// Go yet (brief 1597 is blocked).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

func init() {
	registerRoutes(registerWebOnboardingDemo)
}

// registerWebOnboardingDemo mounts routes/onboarding.py reset_demo. It must
// not use the pool while it builds.
func registerWebOnboardingDemo(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("POST /demo/reset", m.wrap("/demo/reset", onboarding.DemoResetHandler(pool, os.Getenv, time.Now)))
}
