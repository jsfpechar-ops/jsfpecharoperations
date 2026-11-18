package main

// Brief 1700d: GET /apartments/ruian-suggest on the local ruian_address table.
// It stays off until the owner adds the exact path to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesRuian)
}

// registerWebPropertiesRuian mounts routes/admin.py apartments_ruian_suggest.
// It must not use the pool while it builds.
func registerWebPropertiesRuian(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	properties.RegisterRuianSuggest(mux, m.wrap, pool, os.Getenv, time.Now)
}
