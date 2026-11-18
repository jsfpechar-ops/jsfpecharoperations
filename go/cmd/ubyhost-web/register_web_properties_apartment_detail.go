package main

// Brief 1701: the property page (GET /apartments/{id}). It stays off until the
// owner adds the path to UBYHOST_GO_PATHS (brief 1705).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesApartmentDetail)
}

// registerWebPropertiesApartmentDetail mounts routes/admin.py apartment_detail.
// It must not use the pool while it builds.
func registerWebPropertiesApartmentDetail(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	properties.RegisterApartmentDetail(mux, m.wrap, pool, os.Getenv, time.Now)
}
