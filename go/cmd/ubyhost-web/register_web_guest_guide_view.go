package main

// Brief 1629: guest guide view (QR and stay doors). Dormant until wave G (brief 1728).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		guest.RegisterGuideView(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
