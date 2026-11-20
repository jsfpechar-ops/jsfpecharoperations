package main

// Brief 1741: POST /reservations/submit-ready and POST /reservations/{id}/submit.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stays.RegisterSubmit(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
