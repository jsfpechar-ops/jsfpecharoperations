package main

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stays.Register(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}