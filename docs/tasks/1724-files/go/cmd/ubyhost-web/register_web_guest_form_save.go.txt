package main

// Brief 1724: POST /l/{token}/{reservation_id}/save (guest_form_save). Dormant until UBYHOST_GO_PATHS (brief 1728).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		guest.RegisterFormSave(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
