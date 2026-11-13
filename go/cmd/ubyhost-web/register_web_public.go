package main

// Brief 1270: the public legal pages (go/internal/web/public). Caddy sends a
// path here only when it is listed in UBYHOST_GO_PATHS; until then Python
// serves them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		deps := public.Deps{Getenv: os.Getenv, SignedIn: func(r *http.Request) bool {
			// templating.render: a signed-in host without a language choice
			// gets English. Asked only at request time, never while building.
			c, err := r.Cookie(session.CookieName)
			if err != nil || c.Value == "" || pool == nil {
				return false
			}
			h, err := session.Load(r.Context(), pool, c.Value, time.Now(), os.Getenv)
			return err == nil && h != nil
		}}
		for _, path := range public.Paths {
			mux.Handle("GET "+path, m.wrap(path, public.Handler(path, deps)))
		}
	})
}
