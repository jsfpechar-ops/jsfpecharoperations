package main

// Brief 1702c1: the property settings save (POST /apartments/{id}). It stays
// off until the owner adds the path to UBYHOST_GO_PATHS (brief 1705).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesApartmentUpdate)
}

// registerWebPropertiesApartmentUpdate mounts routes/admin.py
// apartment_update. It must not use the pool while it builds.
func registerWebPropertiesApartmentUpdate(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	properties.RegisterApartmentUpdate(mux, m.wrap, pool, os.Getenv, time.Now)
}
