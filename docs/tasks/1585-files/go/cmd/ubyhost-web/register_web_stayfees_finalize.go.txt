package main

// Brief 1585 owns this file: POST /stay-fees/{apartment_id}/finalize. The PDF
// renderer is stayFeeRenderer (register_job_stay_fee_mail.go); while it is nil
// the route seals nothing. Dormant until UBYHOST_GO_PATHS names the path.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("POST /stay-fees/{apartment_id}/finalize", m.wrap("/stay-fees/{apartment_id}/finalize",
			stayfees.FinalizeHandler(pool, os.Getenv, time.Now, stayFeeRenderer)))
	})
}
