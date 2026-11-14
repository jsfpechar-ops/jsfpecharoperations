package properties

// Brief 1521: POST /sync, the "Sync now" button (admin.py sync_now, ~3415).
// It fetches the host's iCal calendars, as the ical job does every few minutes
// (go/internal/ical), then runs the deadline watch for the workspace.

import (
	"net"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
)

// RegisterSync adds POST /sync. fetch carries the iCal fetch options
// (net.DefaultResolver and ical.AllowPrivate in production, a test server in tests).
func RegisterSync(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, fetch *ical.FetchOptions) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /sync", wrap("/sync", func(w http.ResponseWriter, r *http.Request) { s.syncNow(w, r, fetch) }))
}

// syncNow is sync_now. Order as FastAPI: CSRF, login, the form, the sync, the
// deadline watch, the redirect.
func (s *server) syncNow(w http.ResponseWriter, r *http.Request, fetch *ical.FetchOptions) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		fail(w, err)
		return
	}
	if h == nil {
		return
	}
	_ = r.ParseMultipartForm(32 << 20)
	returnTo := formReturnTo(r, "/", false)
	opt := ical.FetchOptions{Resolver: net.DefaultResolver, AllowPrivate: ical.AllowPrivate(s.getenv)}
	if fetch != nil {
		opt = *fetch
	}
	owner := h.Workspace.ID
	totals, err := ical.SyncOwner(r.Context(), s.pool, s.getenv, opt, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if _, err := calendar.CheckDeadlines(r.Context(), s.pool, s.getenv, at, &owner); err != nil {
		fail(w, err)
		return
	}
	var bad hostweb.Flash
	if totals.Errors > 0 {
		bad = flashOf(r, "flash.error.feeds_unreadable", nil)
	}
	hostweb.Back(w, r, locationQuote(returnTo), pluralFlash(r, "flash.feeds.synced", totals.Feeds, map[string]any{
		"created": totals.Created, "updated": totals.Updated, "cancelled": totals.Cancelled,
	}), bad)
}
