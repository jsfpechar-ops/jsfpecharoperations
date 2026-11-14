package main

// Web thread "subscription billing" owns this file: /predplatne
// (routes/billing.py) and /admin/fakturace (routes/admin_billing.py), package
// go/internal/web/billing. Caddy keeps these paths on Python until
// UBYHOST_GO_PATHS names them.

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	billingweb "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		for _, r := range billingweb.Routes(pool, os.Getenv, time.Now) {
			_, path, _ := strings.Cut(r.Pattern, " ")
			mux.Handle(r.Pattern, m.wrap(path, r.Handler))
		}
	})
}
