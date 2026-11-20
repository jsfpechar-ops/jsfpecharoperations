package main

// Brief 1726: guest Leon JSON (4 routes) and host guest-question pages (5 routes).
// Dormant until the owner adds these paths to UBYHOST_GO_PATHS (brief 1728).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		guest.RegisterLeonQuestions(mux, pool, os.Getenv, os.LookupEnv, time.Now, m.wrap)
	})
}
