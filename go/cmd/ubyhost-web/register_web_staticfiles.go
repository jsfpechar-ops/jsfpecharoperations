package main

// Serve /static/* from App/app/static in the Go image (brief 1782; until 1804 Caddy disk).

import (
	"net/http"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/staticfiles"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		staticfiles.Register(mux, os.Getenv, m.wrap)
	})
}
