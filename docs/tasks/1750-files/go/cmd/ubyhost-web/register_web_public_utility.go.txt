package main

// Brief 1750: robots, manifest, service worker, offline, sitemap, language, favicon.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		deps := public.DepsUtility{Getenv: os.Getenv, Pool: pool, Now: time.Now}
		public.RegisterUtility(mux, deps, m.wrap)
	})
}
