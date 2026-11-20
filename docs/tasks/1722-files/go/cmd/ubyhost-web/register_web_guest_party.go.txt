package main

// Brief 1722: guest party POST routes. Dormant until UBYHOST_GO_PATHS (brief 1728).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		guest.RegisterParty(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
