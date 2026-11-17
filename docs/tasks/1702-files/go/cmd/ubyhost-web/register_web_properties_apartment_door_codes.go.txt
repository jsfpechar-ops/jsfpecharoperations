package main

// Brief 1702: the door-code switch of the property page
// (POST /apartments/{id}/door-codes). It stays off until the owner adds the
// path to UBYHOST_GO_PATHS (brief 1705).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesApartmentDoorCodes)
}

// registerWebPropertiesApartmentDoorCodes mounts routes/admin.py
// apartment_door_codes. It must not use the pool while it builds.
func registerWebPropertiesApartmentDoorCodes(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	properties.RegisterApartmentDoorCodes(mux, m.wrap, pool, os.Getenv, time.Now)
}
