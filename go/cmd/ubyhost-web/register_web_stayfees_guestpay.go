package main

// Brief 1587 owns this file: the guest-pay preview route of the stay fees
// (go/internal/web/stayfees). Caddy keeps the path on Python until
// UBYHOST_GO_PATHS names it.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("POST /stay-fees/{apartment_id}/guest-pay-preview",
			m.wrap("/stay-fees/{apartment_id}/guest-pay-preview",
				stayfees.GuestPayPreviewHandler(pool, os.Getenv, time.Now)))
	})
}
