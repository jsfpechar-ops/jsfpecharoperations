package main

// Brief 1521: POST /sync (Sync now; fetches the host's iCal calendars) (go/internal/web/properties).
// Switched off: nothing sends these paths here until UBYHOST_GO_PATHS names them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		properties.RegisterSync(mux, m.wrap, pool, os.Getenv, time.Now, nil)
	})
}
