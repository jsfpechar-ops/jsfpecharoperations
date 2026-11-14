package main

// Brief 1370: the two POST routes of the data-subject request register
// (routes/privacy_requests.py); brief 1615: the GET list page. Caddy sends a
// path here only when it is in UBYHOST_GO_PATHS, so these stay off until the
// owner adds them. GET and POST share /privacy-requests, so that path is
// switched as a whole.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/privacy"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("GET /privacy-requests", m.wrap("/privacy-requests", privacy.ListHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /privacy-requests", m.wrap("/privacy-requests", privacy.CreateHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /privacy-requests/{id}", m.wrap("/privacy-requests/{id}", privacy.UpdateHandler(pool, os.Getenv, time.Now)))
	})
}
