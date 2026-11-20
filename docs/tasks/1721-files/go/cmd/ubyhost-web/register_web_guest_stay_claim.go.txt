package main

// Brief 1721: GET demo/stay/claim routes and POST claim/confirm.
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
		guest.RegisterStayClaim(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
