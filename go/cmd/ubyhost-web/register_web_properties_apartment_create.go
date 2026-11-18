package main

// Brief 1700b2: the property create (POST /apartments). It stays off until the
// owner adds the path to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesApartmentCreate)
}

// registerWebPropertiesApartmentCreate mounts routes/admin.py apartment_create.
// It must not use the pool while it builds.
func registerWebPropertiesApartmentCreate(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	properties.RegisterApartmentCreate(mux, m.wrap, pool, os.Getenv, time.Now)
}
