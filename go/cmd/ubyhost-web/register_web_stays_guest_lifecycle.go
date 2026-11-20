package main

// Brief 1735: guest lifecycle POST routes. Dormant until UBYHOST_GO_PATHS (brief 1737).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stays.RegisterGuestLifecycle(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
