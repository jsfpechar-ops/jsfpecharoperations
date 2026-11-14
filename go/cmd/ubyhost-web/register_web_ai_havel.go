package main

// Web thread "ai" owns this file: the Havel routes (GET /havel, POST /havel,
// POST /havel/support, POST /havel/not-helped) and the Leon setup wizard routes
// (GET and POST /apartments/{id}/leon/setup, GET .../setup/{step}, POST
// .../setup/try), ported in go/internal/web/ai (briefs 1430 to 1437).
// They stay on Python until the owner adds their paths to UBYHOST_GO_PATHS.
// The model client is built here from the environment; building it touches
// neither the pool nor the network.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

func init() { registerRoutes(registerWebAIHavel) }

// registerWebAIHavel adds the Havel routes. It must not use the pool.
func registerWebAIHavel(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	deps := ai.HavelDeps{
		Pool:  pool,
		Env:   ai.HavelEnv(os.LookupEnv),
		Now:   time.Now,
		Model: anthropic.NewService(pool, anthropic.ConfigFromEnv(os.LookupEnv)),
	}
	for _, route := range append(ai.HavelRoutes(deps), ai.LeonRoutes(deps)...) {
		mux.Handle(route.Pattern, m.wrap(route.Label, route.Handler))
	}
}
