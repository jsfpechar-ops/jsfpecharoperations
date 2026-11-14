package main

// Brief 1581 and 1582 own this file: the two stay fee host pages
// (go/internal/web/stayfees, page_*.go). Caddy keeps these paths on Python
// until UBYHOST_GO_PATHS names them.

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
		for _, r := range stayfees.PageRoutes(pool, os.Getenv, time.Now) {
			_, path, _ := strings.Cut(r.Pattern, " ")
			mux.Handle(r.Pattern, m.wrap(path, r.Handler))
		}
	})
}
