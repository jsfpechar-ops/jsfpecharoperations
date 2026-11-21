package public

// GET /dev/ui (dev_ui.py): admin-only living catalog.

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// DevUIHandler serves GET /dev/ui for admins (mirrors dev_ui.py).
func DevUIHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if h == nil {
			return
		}
		if h.Account.Role != "admin" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`<!DOCTYPE html><html><head><title>UI catalog</title></head><body><h1>UI catalog</h1><p><span class="ui-num">12 345 Kč</span></p></body></html>`))
	}
}
