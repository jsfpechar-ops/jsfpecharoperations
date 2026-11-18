package main

// Brief 1704c: GET /settings/security and GET /settings/phone, the last two
// groups of the Settings pages (1704b registers the index and the other four).
// They stay off until the owner adds the paths to UBYHOST_GO_PATHS (brief 1705).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/settings"
)

func init() {
	registerRoutes(registerWebSettingsSecurity)
}

// registerWebSettingsSecurity mounts routes/admin.py _settings_page for the
// groups security and phone. It must not use the pool while it builds.
func registerWebSettingsSecurity(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	for _, group := range []string{"security", "phone"} {
		path := "/settings/" + group
		mux.Handle("GET "+path, m.wrap(path, settings.Handler(pool, os.Getenv, time.Now, group)))
	}
}
