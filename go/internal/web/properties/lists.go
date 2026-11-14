package properties

// The two list pages of the property settings area (brief 1302): GET
// /entities (admin.py entities ~858 and _entities_page ~903, the list without
// an open editor) and GET /apartments for a workspace with no live property
// (apartments_list ~1344, the empty state). The bodies are
// templates/lists.tmpl, rendered inside the host layout (hostweb/layout).
//
// What is not ported answers 501 instead of showing a different page:
//   - /entities?edit=N: the business editor with Invoice details (billing);
//   - /entities when the workspace has an open alert: _host_alerts.html is
//     inside the page body and is ported with brief 1381;
//   - /apartments with a live property: the setup chips read filing state
//     (validation issues, ubyport_auth_failed alerts), calendars, the lock
//     and the guest link.

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// RegisterLists adds GET /entities and GET /apartments. It only builds
// handlers; the pool is first used inside a request.
func RegisterLists(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &Pages{pool: pool, getenv: getenv, now: now}
	for _, route := range []struct {
		path string
		h    http.HandlerFunc
	}{
		{"/entities", s.entities},
		{"/apartments", s.apartments},
	} {
		mux.Handle("GET "+route.path, wrap(route.path, route.h))
	}
}

// notPorted answers a branch this package does not render yet (see the top).
func notPorted(w http.ResponseWriter, what string) {
	http.Error(w, "not served by Go yet: "+what, http.StatusNotImplemented)
}

// queryLast is Starlette's query_params.get: the last value of a key.
func queryLast(r *http.Request, key string) string {
	values := r.URL.Query()[key]
	if len(values) == 0 {
		return ""
	}
	return values[len(values)-1]
}

// editAsked is entities()'s `edit_id and edit_id.isdigit()`. Python's isdigit
// also takes non-ASCII digits, so any non-ASCII value counts as asked too.
func editAsked(v string) bool {
	if v == "" {
		return false
	}
	digits := true
	for _, r := range v {
		if r > unicode.MaxASCII {
			return true
		}
		if r < '0' || r > '9' {
			digits = false
		}
	}
	return digits
}

// Banner is onboarding_banner(onboarding): shown when the setup is not
// complete and not dismissed; URL is onboarding.setup_url.
type Banner struct {
	Show       bool
	URL        string
	ReturnPath string
}

const (
	dismissedSQL      = `SELECT value FROM settings WHERE key = $1`
	firstApartmentSQL = `SELECT a.id, COALESCE(a.addr_house_no, ''), COALESCE(a.addr_zip, ''), COALESCE(a.addr_obec, ''),
  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1)
FROM apartment a WHERE a.archived_at IS NULL AND a.owner_user_id IS NOT DISTINCT FROM $1 ORDER BY a.id LIMIT 1`
	manualStaysSQL = `SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = $1 AND r.status = 'active' AND r.source = 'manual'`
)

// onboardingBanner is the part of onboarding.progress the banner reads:
// is_dismissed, wizard_step (name, address, bookings, complete) and setup_url.
func (s *Pages) onboardingBanner(ctx context.Context, workspace int64, path string) (Banner, error) {
	b := Banner{ReturnPath: path}
	if workspace != 0 {
		var v *string
		err := s.pool.QueryRow(ctx, dismissedSQL, "onboarding_dismissed_"+strconv.FormatInt(workspace, 10)).Scan(&v)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return b, err
		}
		if v != nil && *v == "1" {
			return b, nil
		}
	}
	var id, feeds int64
	var house, zip, obec string
	err := s.pool.QueryRow(ctx, firstApartmentSQL, workspace).Scan(&id, &house, &zip, &obec, &feeds)
	if errors.Is(err, pgx.ErrNoRows) {
		return Banner{Show: true, URL: "/apartments/new", ReturnPath: path}, nil // step "name"
	}
	if err != nil {
		return b, err
	}
	base := "/apartments/" + strconv.FormatInt(id, 10)
	if !addressComplete(house, zip, obec) {
		return Banner{Show: true, URL: base + "?view=settings&section=property#address", ReturnPath: path}, nil
	}
	if feeds == 0 {
		var manual int64
		if err := s.pool.QueryRow(ctx, manualStaysSQL, id).Scan(&manual); err != nil {
			return b, err
		}
		if manual == 0 {
			return Banner{Show: true, URL: base + "?view=bookings#calendars", ReturnPath: path}, nil
		}
	}
	return b, nil // "complete"
}

// addressComplete is onboarding._address_complete: house number, ZIP and
// municipality not blank, and five digits in the ZIP (normalise_zip).
func addressComplete(house, zip, obec string) bool {
	if pyStrip(house) == "" || pyStrip(zip) == "" || pyStrip(obec) == "" {
		return false
	}
	n := 0
	for _, r := range zip {
		if unicode.IsDigit(r) {
			n++
		}
	}
	return n == 5
}

// entityRow is one legal_entity row of _entities_list_context.
type entityRow struct {
	ID                                 int64
	Name, Seat, ICO, Email, ArchivedAt string
	Apartments                         int64
}

// ArchivedCZ is entity.archived_at | date_cz.
func (e entityRow) ArchivedCZ() string { return dateCZ(e.ArchivedAt) }

const entityColumns = `SELECT e.id, e.name, COALESCE(e.seat, ''), COALESCE(e.ico, ''), COALESCE(e.contact_email, ''), COALESCE(e.archived_at, ''),
  (SELECT COUNT(*) FROM apartment a WHERE a.legal_entity_id = e.id OR a.data_controller_entity_id = e.id)
FROM legal_entity e WHERE e.owner_user_id IS NOT DISTINCT FROM $1 `

const (
	liveEntitiesSQL     = entityColumns + `AND e.archived_at IS NULL ORDER BY e.name`
	archivedEntitiesSQL = entityColumns + `AND e.archived_at IS NOT NULL ORDER BY e.archived_at DESC`
	openAlertsSQL       = `SELECT COUNT(*) FROM alert WHERE resolved_at IS NULL AND (owner_user_id = $1 OR kind IN ('job_failed', 'turnstile_unavailable', 'ttlock_budget'))`
)

func (s *Pages) entityRows(ctx context.Context, sql string, owner int64) ([]entityRow, error) {
	rows, err := s.pool.Query(ctx, sql, owner)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (entityRow, error) {
		var e entityRow
		err := row.Scan(&e.ID, &e.Name, &e.Seat, &e.ICO, &e.Email, &e.ArchivedAt, &e.Apartments)
		return e, err
	})
}

// dateCZ is the date_cz filter (validation.fmt_date): DD.MM.YYYY from the
// first ten characters, else the value unchanged.
func dateCZ(v string) string {
	head := v
	if len(head) > 10 {
		head = head[:10]
	}
	if t, err := time.Parse("2006-01-02", head); err == nil {
		return t.Format("02.01.2006")
	}
	return v
}

type entitiesData struct {
	Banner             Banner
	TitleHead          string // settings_back_header: title.rsplit(' ', 1)
	TitleLast          string
	Entities, Archived []entityRow
	AccountEmail       string
	NextPath           string
	Editor             *editorView   // the open business editor (brief 1523)
	NewForm            *businessForm // the add form, with its typed values after a register lookup
}

func (s *Pages) entities(w http.ResponseWriter, r *http.Request) {
	now := s.now()
	host, err := hostweb.Login(w, r, s.pool, s.getenv, now)
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	edit := queryLast(r, "edit")
	if editAsked(edit) && !allDigits(edit) {
		// int() of a non-ASCII digit string is not reproduced.
		notPorted(w, "the business editor (?edit= with a non-ASCII number)")
		return
	}
	ctx := r.Context()
	ws := host.Workspace.ID
	var alerts int64
	if err := s.pool.QueryRow(ctx, openAlertsSQL, ws).Scan(&alerts); err != nil {
		fail(w, err)
		return
	}
	if alerts > 0 {
		notPorted(w, "host alerts on this page")
		return
	}
	d := &entitiesData{NextPath: safeLocalPath(queryLast(r, "next"), "")}
	// account_email: the signed-in account (the admin inside a workspace).
	if err := s.pool.QueryRow(ctx, accountEmailSQL, host.Account.ID).Scan(&d.AccountEmail); err != nil && !errors.Is(err, pgx.ErrNoRows) {
		fail(w, err)
		return
	}
	if allDigits(edit) {
		if err := s.openEditor(ctx, d, ws, edit); err != nil {
			fail(w, err)
			return
		}
	}
	if err := s.renderEntities(w, r, host, now, d); err != nil {
		fail(w, err)
	}
}

const (
	liveApartmentSQL = `SELECT COUNT(*) FROM apartment WHERE archived_at IS NULL AND owner_user_id IS NOT DISTINCT FROM $1`
	liveEntitySQL    = `SELECT COUNT(*) FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL`
)

type apartmentsData struct {
	Banner      Banner
	HasOperator bool
}

func (s *Pages) apartments(w http.ResponseWriter, r *http.Request) {
	now := s.now()
	host, err := hostweb.Login(w, r, s.pool, s.getenv, now)
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	ctx := r.Context()
	ws := host.Workspace.ID
	var live, operators int64
	if err := s.pool.QueryRow(ctx, liveApartmentSQL, ws).Scan(&live); err != nil {
		fail(w, err)
		return
	}
	if live > 0 {
		notPorted(w, "the property list")
		return
	}
	if err := s.pool.QueryRow(ctx, liveEntitySQL, ws).Scan(&operators); err != nil {
		fail(w, err)
		return
	}
	d := apartmentsData{HasOperator: operators > 0}
	if d.Banner, err = s.onboardingBanner(ctx, ws, "/apartments"); err != nil {
		fail(w, err)
		return
	}
	page := layout.Page{Title: catalog.T(hostweb.Lang(r), "apartments.title", nil), Nav: "apartments", BodyKind: "list", V2: true, HowKey: "properties"}
	if err := layout.Render(w, r, layout.Env{Pool: s.pool, Getenv: s.getenv, Now: now}, host, page, pages, "apartments", d); err != nil {
		fail(w, err)
	}
}
