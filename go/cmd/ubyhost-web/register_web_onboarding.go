package main

// Brief 1290: the settings-only onboarding POST routes. They stay off until a
// later brief adds their paths to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

func init() {
	registerRoutes(registerWebOnboarding)
}

// registerWebOnboarding mounts the routes of App/app/routes/onboarding.py
// that render no HTML. It must not use the pool while it builds.
func registerWebOnboarding(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("POST /onboarding/dismiss", m.wrap("/onboarding/dismiss", onboarding.DismissHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /onboarding/resume", m.wrap("/onboarding/resume", onboarding.ResumeHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /welcome-back/dismiss", m.wrap("/welcome-back/dismiss", onboarding.WelcomeBackDismissHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /celebrations/dismiss", m.wrap("/celebrations/dismiss", onboarding.CelebrationDismissHandler(pool, os.Getenv, time.Now)))
}
