package main

// Brief 1544: the guest's private booking page. Off until the owner adds the
// path to UBYHOST_GO_PATHS (see brief 1550). The cancel button posts to
// /p/{slug}/b/{id}/{token}/cancel, a different path that stays on Python.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("GET /p/{slug}/b/{booking_id}/{token}", m.wrap("/p/{slug}/b/{booking_id}/{token}",
			booking.ManageHandler(pool, os.Getenv, time.Now, payments.QRDataURI)))
	})
}
