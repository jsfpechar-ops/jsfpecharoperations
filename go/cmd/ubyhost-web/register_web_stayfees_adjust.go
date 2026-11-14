package main

// Brief 1584 owns this file: the stay-fee adjustment add route
// (go/internal/web/stayfees). Caddy keeps this path on Python until
// UBYHOST_GO_PATHS names it.

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		for _, r := range stayfees.AdjustRoutes(pool, os.Getenv, time.Now) {
			_, path, _ := strings.Cut(r.Pattern, " ")
			mux.Handle(r.Pattern, m.wrap(path, r.Handler))
		}
	})
}
