package main

// Brief 1731: POST quick-edit, remove-empty-slot, archive, unarchive, delete-demo.
// Dormant until the owner adds the paths to UBYHOST_GO_PATHS.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stays.RegisterEditPosts(mux, pool, os.Getenv, time.Now, m.wrap, completionHooks(pool))
		stays.RegisterArchiveOld(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
