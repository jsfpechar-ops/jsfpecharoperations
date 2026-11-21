package main

// Brief 1723: guest registration form pages (/l/{token}/{reservation_id}/…).
// Dormant until UBYHOST_GO_PATHS (brief 1728). Depends on 1720–1722 guest shell.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		guest.RegisterFormPages(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
