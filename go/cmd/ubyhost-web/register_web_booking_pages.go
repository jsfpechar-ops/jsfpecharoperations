package main

// Brief 1540: the static guest pages of the booking site. Off until the owner
// adds their paths to UBYHOST_GO_PATHS. The factories do not touch the pool.

import (
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, _ *pgxpool.Pool) {
		mux.Handle("GET /terms/booking", m.wrap("/terms/booking", booking.TermsHandler()))
		// More specific than GET /p/{slug}/{file} (register_web_booking.go): no conflict.
		mux.Handle("GET /p/{slug}/thanks", m.wrap("/p/{slug}/thanks", booking.ThanksHandler()))
	})
}
