package main

// The passkey routes (brief 1760). They are registered on the mux but stay
// dormant: Caddy sends a path here only once it is listed in
// UBYHOST_GO_PATHS, and these paths are not listed until the login cutover
// (brief 1761) has been tested.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth"
)

func init() { registerRoutes(registerWebAuthPasskeys) }

func registerWebAuthPasskeys(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	for _, r := range auth.PasskeyRoutes(pool, os.Getenv, time.Now) {
		mux.Handle(r.Pattern, m.wrap(r.Path, r.Handler))
	}
}
