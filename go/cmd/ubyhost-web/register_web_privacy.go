package main

// Brief 1370: the two POST routes of the data-subject request register
// (routes/privacy_requests.py). The GET page comes in a later brief. Caddy
// sends a path here only when it is in UBYHOST_GO_PATHS, so these stay off
// until the owner adds them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/privacy"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("POST /privacy-requests", m.wrap("/privacy-requests", privacy.CreateHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /privacy-requests/{id}", m.wrap("/privacy-requests/{id}", privacy.UpdateHandler(pool, os.Getenv, time.Now)))
	})
}
