package main

// Brief 1730: GET /submissions and GET /submissions/{submission_id}. Dormant
// until the owner adds the path to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/submissions"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		submissions.Register(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
