package main

// Brief 1541: the public property page and its no-JS quote step. Off until the
// owner adds the paths to UBYHOST_GO_PATHS (see the brief for the order).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("GET /p/{slug}", m.wrap("/p/{slug}", booking.PropertyPageHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /p/{slug}/book", m.wrap("/p/{slug}/book", booking.BookHandler(pool, os.Getenv, time.Now)))
	})
}
