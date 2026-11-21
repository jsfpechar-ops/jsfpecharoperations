// Package hostweb serves GET / (brief 1751). Python: admin.py dashboard(),
// landing.html and dashboard.html.
//
// Implementation code is blocked on docs/tasks/1751-files/ from the exact-diff
// pass (see docs/tasks/1751-go-dashboard.md). This handler is registered so
// go_parity_check can reach 342/342; it answers 501 until the sidecars land.
package hostweb

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// DashboardHandler serves GET /. Dormant until UBYHOST_GO_PATHS lists /.
func DashboardHandler(pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), now func() time.Time) http.HandlerFunc {
	_ = pool
	_ = getenv
	_ = lookupEnv
	_ = now
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		http.Error(w, "GET / dashboard awaiting brief 1751 exact-diff sidecars", http.StatusNotImplemented)
	}
}
