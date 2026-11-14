package main

// Brief 1522: POST /entities and POST /entities/{id} (go/internal/web/properties).
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
		properties.RegisterEntities(mux, m.wrap, pool, os.Getenv, time.Now)
	})
}
