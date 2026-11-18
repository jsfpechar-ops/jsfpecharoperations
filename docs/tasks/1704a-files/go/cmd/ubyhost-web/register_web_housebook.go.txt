package main

// Brief 1704a: the house book page (GET /housebook). It stays off until the
// owner adds the path to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/housebook"
)

func init() {
	registerRoutes(registerWebHousebook)
}

// registerWebHousebook mounts routes/admin.py housebook_view. It must not use
// the pool while it builds.
func registerWebHousebook(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("GET /housebook", m.wrap("/housebook", housebook.Handler(pool, os.Getenv, time.Now)))
}
