package main

// Brief 1712: guest cancel POST and invoice PDFs. Off until UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		booking.RegisterCancelPDFs(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
