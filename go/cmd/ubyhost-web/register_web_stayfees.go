package main

// Brief 1330 owns this file: the ported stay-fee actions and the sealed CSV
// (go/internal/web/stayfees). Caddy keeps these paths on Python until
// UBYHOST_GO_PATHS names them.

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
		for _, r := range stayfees.Routes(pool, os.Getenv, time.Now) {
			_, path, _ := strings.Cut(r.Pattern, " ")
			mux.Handle(r.Pattern, m.wrap(path, r.Handler))
		}
	})
}
