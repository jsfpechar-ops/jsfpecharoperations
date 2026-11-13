package main

// The login and account routes that render no page (brief 1282). Caddy sends
// a path here only once it is listed in UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth"
)

func init() { registerRoutes(registerWebAuth) }

func registerWebAuth(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	for _, r := range auth.Routes(pool, os.Getenv, time.Now) {
		mux.Handle(r.Pattern, m.wrap(r.Path, r.Handler))
	}
}
