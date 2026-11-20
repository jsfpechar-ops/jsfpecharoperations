package main

// Brief 1732: POST reopen-guest, resend-claim, release-claim, filed-by-hand (+ undo).
// Dormant until the owner adds these paths to UBYHOST_GO_PATHS (brief 1737).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stays.RegisterClaimOps(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
