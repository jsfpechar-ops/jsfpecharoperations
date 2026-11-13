package main

// Brief 1440 owns this file: the guest guide editor routes of
// App/app/routes/guest_guide.py, ported in go/internal/web/ai (guide*.go).
// They stay on Python until the owner adds their paths to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

func init() {
	registerRoutes(registerWebAIGuide)
}

// registerWebAIGuide adds the guide editor routes. It must not use the pool.
func registerWebAIGuide(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	for _, route := range ai.GuideRoutes(pool, os.Getenv, os.LookupEnv, time.Now) {
		mux.Handle(route.Pattern, m.wrap(route.Label, route.Handler))
	}
}
