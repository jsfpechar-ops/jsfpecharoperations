package properties

// Brief 1520: three small routes of App/app/routes/admin.py.
//   - POST /alerts/{id}/dismiss  (dismiss_alert, ~5216)
//   - GET  /smart-locks          (smart_locks_page, ~712; the redirect only)
//   - GET  /menu                 (menu_view, ~5257)
// The POST /smart-locks/* routes call the TTLock gateway and are not here.

import (
	"errors"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// RegisterMisc adds the three routes. It does not touch the pool.
func RegisterMisc(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	p := &Pages{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /alerts/{id}/dismiss", wrap("/alerts/{id}/dismiss", s.dismissAlert))
	mux.Handle("GET /smart-locks", wrap("/smart-locks", p.smartLocks))
	mux.Handle("GET /menu", wrap("/menu", p.menu))
}

const (
	alertOwnedSQL       = `SELECT kind, apartment_id, owner_user_id FROM alert WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
	alertResolveSQL     = `UPDATE alert SET resolved_at = $1, user_dismissed = 1 WHERE id = $2`
	pinAlertsOwnerSQL   = `SELECT id FROM alert WHERE resolved_at IS NULL AND kind = 'guest_pin_rotated' AND owner_user_id = $1`
	pinAlertsNoOwnerSQL = `SELECT id FROM alert WHERE resolved_at IS NULL AND kind = 'guest_pin_rotated'`
)

// refererPath is admin.py _redirect_path_from_referer: the path and query of
// Referer when it names this host, else def. Like urlparse, ";params" of the
// last path segment are dropped and the fragment is ignored.
func refererPath(r *http.Request, def string) string {
	referer := pyStrip(r.Header.Get("Referer"))
	if referer == "" {
		return def
	}
	u, err := url.Parse(referer)
	if err != nil {
		return def
	}
	siteHost := strings.ToLower(strings.SplitN(r.Host, ":", 2)[0])
	if siteHost == "" || strings.ToLower(u.Hostname()) != siteHost {
		return def
	}
	path := u.EscapedPath()
	if i := strings.LastIndex(path, "/"); i >= 0 {
		if j := strings.Index(path[i+1:], ";"); j >= 0 {
			path = path[:i+1+j]
		}
	}
	if path == "" {
		path = def
	}
	if !strings.HasPrefix(path, "/") || strings.HasPrefix(path, "//") {
		return def
	}
	if u.RawQuery != "" {
		return path + "?" + u.RawQuery
	}
	return path
}

// dismissAlert is POST /alerts/{id}/dismiss (admin.py dismiss_alert).
func (s *server) dismissAlert(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	var kind string
	var apartment, owner *int64
	err := s.pool.QueryRow(ctx, alertOwnedSQL, q.id, q.host.Workspace.ID).Scan(&kind, &apartment, &owner)
	if errors.Is(err, pgx.ErrNoRows) {
		// Starlette Response("No such alert.", 404): no Content-Type header.
		w.Header()["Content-Type"] = nil
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte("No such alert."))
		return
	}
	if err != nil {
		fail(w, err)
		return
	}
	fetch := r.Header.Get("x-requested-with") == "fetch"
	locked := func(key string) {
		if fetch {
			w.WriteHeader(http.StatusConflict)
			return
		}
		q.back(w, r, refererPath(r, "/"), hostweb.Flash{}, q.flash(key, nil))
	}
	switch kind {
	case "dates_changed_resign":
		// The card is the filing gate; dismissing it would let old dates through.
		locked("flash.error.resign_card_locked")
		return
	case "submission_outcome_unknown":
		if apartment != nil {
			doubt, err := ubyport.ApartmentInDoubt(ctx, s.pool, *apartment)
			if err != nil {
				fail(w, err)
				return
			}
			if doubt {
				locked("flash.error.unknown_card_locked")
				return
			}
		}
	}
	if _, err := s.pool.Exec(ctx, alertResolveSQL, stamp(q.at), q.id); err != nil {
		fail(w, err)
		return
	}
	if kind == "guest_pin_rotated" {
		// One card stands for every property whose PIN was rotated (0148).
		sql, args := pinAlertsNoOwnerSQL, []any{}
		if owner != nil {
			sql, args = pinAlertsOwnerSQL, []any{*owner}
		}
		rows, err := s.pool.Query(ctx, sql, args...)
		if err != nil {
			fail(w, err)
			return
		}
		ids, err := pgx.CollectRows(rows, pgx.RowTo[int64])
		if err != nil {
			fail(w, err)
			return
		}
		for _, id := range ids {
			if _, err := s.pool.Exec(ctx, alertResolveSQL, stamp(q.at), id); err != nil {
				fail(w, err)
				return
			}
		}
	}
	if fetch {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	q.back(w, r, refererPath(r, "/"), hostweb.Flash{}, hostweb.Flash{})
}

// flashOf is a translated flash for a handler that has no request struct.
func flashOf(r *http.Request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(hostweb.Lang(r), key, params), Key: key}
}

// doorCodesEnabled is ttlock.enabled(): UBYHOST_DOOR_CODES is 1, true or yes
// (exact case) and both TTLock app credentials are set.
func doorCodesEnabled(getenv func(string) string) bool {
	switch getenv("UBYHOST_DOOR_CODES") {
	case "1", "true", "yes":
	default:
		return false
	}
	return pyStrip(getenv("UBYHOST_TTLOCK_CLIENT_ID")) != "" && pyStrip(getenv("UBYHOST_TTLOCK_CLIENT_SECRET")) != ""
}

var lockPropertyPath = regexp.MustCompile(`^/apartments/([0-9]+)(?:/setup/door_lock)?$`)

const (
	lockAccountSQL  = `SELECT 1 FROM lock_account WHERE owner_user_id = $1 AND provider = 'ttlock'`
	ownApartmentSQL = `SELECT 1 FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
	firstActiveSQL  = `SELECT id FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL AND active <> 0 ORDER BY internal_name, id LIMIT 1`
)

// smartLocks is GET /smart-locks (admin.py smart_locks_page, with
// _lock_tab_url and _lock_property_return): the lock panel lives on each
// property's Door lock tab, so old links are sent there.
func (p *Pages) smartLocks(w http.ResponseWriter, r *http.Request) {
	host, err := hostweb.Login(w, r, p.pool, p.getenv, p.now())
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	if !doorCodesEnabled(p.getenv) {
		hostweb.Back(w, r, "/apartments", hostweb.Flash{}, flashOf(r, "flash.error.smart_locks_unavailable", nil))
		return
	}
	ctx, owner := r.Context(), host.Workspace.ID
	anchor := "smart-locks-how"
	var one int
	switch err := p.pool.QueryRow(ctx, lockAccountSQL, owner).Scan(&one); {
	case err == nil:
		anchor = "smart-locks-list"
	case !errors.Is(err, pgx.ErrNoRows):
		fail(w, err)
		return
	}
	returnTo := safeLocalPath(queryLast(r, "return_to"), "/apartments")
	target := ""
	path := strings.SplitN(strings.SplitN(returnTo, "#", 2)[0], "?", 2)[0]
	if m := lockPropertyPath.FindStringSubmatch(path); m != nil {
		if id, err := strconv.ParseInt(m[1], 10, 64); err == nil {
			switch err := p.pool.QueryRow(ctx, ownApartmentSQL, id, owner).Scan(&one); {
			case err == nil:
				target = "/apartments/" + m[1] + "?view=settings&section=lock&sec=lock#sec-lock"
			case !errors.Is(err, pgx.ErrNoRows):
				fail(w, err)
				return
			}
		}
	}
	if target == "" {
		var first int64
		switch err := p.pool.QueryRow(ctx, firstActiveSQL, owner).Scan(&first); {
		case err == nil:
			target = "/apartments/" + strconv.FormatInt(first, 10) + "?view=settings&section=lock#" + anchor
		case errors.Is(err, pgx.ErrNoRows):
			target = "/apartments"
		default:
			fail(w, err)
			return
		}
	}
	hostweb.Back(w, r, target, hostweb.Flash{}, hostweb.Flash{})
}

const (
	monthSQL = `SELECT COALESCE(SUM(n), 0), COALESCE(SUM(sent), 0) FROM (
  SELECT (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id) AS n,
         (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id AND g.submit_state = 'sent') AS sent
  FROM reservation r JOIN apartment a ON a.id = r.apartment_id
  WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL AND COALESCE(r.source, '') != 'demo'
    AND r.date_from < $2 AND r.date_to > $3) m`
	displayNameSQL = `SELECT COALESCE(display_name, '') FROM user_account WHERE id = $1`
)

type menuData struct {
	Initial        string
	Guests, Police int64
	IsAdmin        bool
}

// pragueDay is claim.prague_today().
func pragueDay(at time.Time) time.Time {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		loc = time.UTC
	}
	t := at.In(loc)
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC)
}

// menu is GET /menu (admin.py menu_view). The Python view also calls
// cleaning.schedule(owner, today, today) for a badge: that range is empty, so
// the count is always 0 and the badge never shows. The call's only effect is
// cleaning.reconcile, which Go does when a cleaning page is opened (deviation,
// brief 1520 section 2).
func (p *Pages) menu(w http.ResponseWriter, r *http.Request) {
	now := p.now()
	host, err := hostweb.Login(w, r, p.pool, p.getenv, now)
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	ctx := r.Context()
	today := pragueDay(now)
	start := time.Date(today.Year(), today.Month(), 1, 0, 0, 0, 0, time.UTC)
	end := start.AddDate(0, 1, 0)
	d := menuData{IsAdmin: host.Account.Role == "admin"}
	if err := p.pool.QueryRow(ctx, monthSQL, host.Workspace.ID, end.Format("2006-01-02"), start.Format("2006-01-02")).Scan(&d.Guests, &d.Police); err != nil {
		fail(w, err)
		return
	}
	var display string
	if err := p.pool.QueryRow(ctx, displayNameSQL, host.Workspace.ID).Scan(&display); err != nil && !errors.Is(err, pgx.ErrNoRows) {
		fail(w, err)
		return
	}
	name := display
	if name == "" {
		name = host.Workspace.Username
	}
	for _, c := range name {
		d.Initial = strings.ToUpper(string(c))
		break
	}
	page := layout.Page{Title: catalog.T(hostweb.Lang(r), "nav.menu", nil), Nav: "menu", BodyKind: "list", V2: true}
	if err := layout.Render(w, r, layout.Env{Pool: p.pool, Getenv: p.getenv, Now: now}, host, page, pages, "menu", d); err != nil {
		fail(w, err)
	}
}
