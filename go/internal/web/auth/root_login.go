package auth

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// RootLoginHandler serves the login form at GET / on the app host (admin.py
// dashboard() signed-out branch on app_host). It sets X-Robots-Tag like Python.
func RootLoginHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool: pool, getenv: getenv, now: now}
	return d.rootLoginForm
}

func (d deps) rootLoginForm(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	if h != nil {
		if d.refreshed(w, h, at) {
			redirect(w, "/")
		}
		return
	}
	data, err := d.loginPageData(r.Context(), r, at)
	if err != nil {
		serverError(w, err)
		return
	}
	data.Next = queryLast(r, "next")
	w.Header().Set("X-Robots-Tag", "noindex, nofollow")
	d.render(w, r, nil, at, "login", data, http.StatusOK)
}
