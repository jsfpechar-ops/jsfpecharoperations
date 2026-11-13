package main

// Web thread "cleaning" owns this file: the cleaning routes that need no host
// page layout. The route function does not touch the pool while it builds.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning"
)

func init() { registerRoutes(registerWebCleaning) }

// registerWebCleaning registers the cleaning routes on mux.
func registerWebCleaning(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("GET /cleaning/schedule", m.wrap("/cleaning/schedule", cleaning.ScheduleHandler(pool, os.Getenv, time.Now)))
	mux.Handle("GET /cleaning/shared/{token}", m.wrap("/cleaning/shared/{token}", cleaning.SharedPageHandler(pool, os.Getenv, time.Now)))
	mux.Handle("GET /cleaning/shared/{token}/schedule", m.wrap("/cleaning/shared/{token}/schedule", cleaning.SharedScheduleHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /cleaning/events/{id}/delete", m.wrap("/cleaning/events/{id}/delete", cleaning.DeleteHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /cleaning/shares/{id}/revoke", m.wrap("/cleaning/shares/{id}/revoke", cleaning.RevokeHandler(pool, os.Getenv, time.Now)))
}
