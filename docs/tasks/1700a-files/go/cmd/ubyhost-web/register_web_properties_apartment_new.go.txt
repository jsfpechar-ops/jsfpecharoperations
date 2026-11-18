package main

// Brief 1700a: the new-property form (GET /apartments/new). It stays off until
// the owner adds the path to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesApartmentNew)
}

// registerWebPropertiesApartmentNew mounts routes/admin.py apartment_new. It
// must not use the pool while it builds.
func registerWebPropertiesApartmentNew(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	properties.RegisterApartmentNew(mux, m.wrap, pool, os.Getenv, time.Now)
}
