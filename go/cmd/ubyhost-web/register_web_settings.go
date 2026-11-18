package main

// Brief 1704b: the Settings pages GET /settings and
// GET /settings/{account,data,technical,help}. They stay off until the owner
// adds the paths to UBYHOST_GO_PATHS (brief 1705). The security and phone
// pages are brief 1704c, which adds its own register file.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/settings"
)

func init() {
	registerRoutes(registerWebSettings)
}

// registerWebSettings mounts routes/admin.py _settings_page for the index and
// four of the six groups. It must not use the pool while it builds.
func registerWebSettings(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("GET /settings", m.wrap("/settings", settings.Handler(pool, os.Getenv, time.Now, "")))
	for _, group := range []string{"account", "data", "technical", "help"} {
		path := "/settings/" + group
		mux.Handle("GET "+path, m.wrap(path, settings.Handler(pool, os.Getenv, time.Now, group)))
	}
}
