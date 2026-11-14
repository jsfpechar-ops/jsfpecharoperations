package exports

// Brief 1608: GET /settings/archived (exports.settings_archived_view), the
// archive browser, with templates/archived.tmpl (the port of
// settings_archived.html) inside the host layout.

import (
	"context"
	"embed"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

//go:embed templates/*.tmpl
var templateFiles embed.FS

// pages is the parsed archive page (the layout shell plus templates/*.tmpl).
var pages = layout.MustParseFuncs(catalog, map[string]any{"date_cz": dateCZ}, templateFiles, "templates/*.tmpl")

// archivedTypes is exports.ARCHIVED_TYPES; anything else is "all".
var archivedTypes = map[string]bool{"all": true, "stays": true, "properties": true, "housebook": true, "entities": true}

// The reads of settings_archived_view (db.null_safe_eq is IS NOT DISTINCT FROM).
const (
	archivedStaysCountSQL = `SELECT COUNT(*) FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.archived_at IS NOT NULL AND a.owner_user_id IS NOT DISTINCT FROM $1`
	archivedPropertiesCountSQL = `SELECT COUNT(*) FROM apartment
		WHERE archived_at IS NOT NULL AND owner_user_id IS NOT DISTINCT FROM $1`
	archivedGuestsCountSQL = `SELECT COUNT(*) FROM guest g JOIN reservation r ON r.id = g.reservation_id
		JOIN apartment a ON a.id = r.apartment_id
		WHERE g.archived_at IS NOT NULL AND a.owner_user_id IS NOT DISTINCT FROM $1`
	archivedEntitiesCountSQL = `SELECT COUNT(*) FROM legal_entity
		WHERE archived_at IS NOT NULL AND owner_user_id IS NOT DISTINCT FROM $1`
	archivedStaysSQL = `SELECT r.id, r.date_from, r.date_to, a.internal_name, r.archived_at FROM reservation r
		JOIN apartment a ON a.id = r.apartment_id
		WHERE r.archived_at IS NOT NULL AND a.owner_user_id IS NOT DISTINCT FROM $1
		ORDER BY r.archived_at DESC, r.id DESC`
	archivedPropertiesSQL = `SELECT a.id, a.internal_name, a.archived_at,
		(SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id) AS reservations
		FROM apartment a
		WHERE a.archived_at IS NOT NULL AND a.owner_user_id IS NOT DISTINCT FROM $1
		ORDER BY a.archived_at DESC`
	archivedEntitiesSQL = `SELECT e.id, e.name, e.archived_at, COALESCE(e.ico, '') FROM legal_entity e
		WHERE e.archived_at IS NOT NULL AND e.owner_user_id IS NOT DISTINCT FROM $1
		ORDER BY e.archived_at DESC`
)

// dateCZ is the date_cz filter (validation.fmt_date): DD.MM.YYYY when the
// first ten characters are a date, else the value unchanged.
func dateCZ(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		return t.Format("02.01.2006")
	}
	return v
}

type archivedCounts struct{ All, Stays, Properties, Housebook, Entities int }

type archivedStay struct {
	ID                                       int64
	DateFrom, DateTo, InternalName, Archived string
}

type archivedProperty struct {
	ID                     int64
	InternalName, Archived string
	Reservations           int64
}

type archivedGuest struct {
	GuestID                                                   int64
	Apartment, StayFrom, StayTo, Surname, FirstName, Archived string
}

type archivedEntity struct {
	ID                  int64
	Name, Archived, ICO string
}

type pill struct {
	Label, Href string
	Current     bool
}

// archivedData is the context of settings_archived.html.
type archivedData struct {
	Type                 string
	Counts               archivedCounts
	TitleHead, TitleLast string // settings_back_header: title.rsplit(' ', 1)
	Pills                []pill
	ReturnTo             string // the return_to of every restore form
	Stays                []archivedStay
	Properties           []archivedProperty
	Housebook            []archivedGuest
	Entities             []archivedEntity
}

// Show is "item_type in ('all', kind)".
func (d archivedData) Show(kind string) bool { return d.Type == "all" || d.Type == kind }

func scanCount(ctx context.Context, pool *pgxpool.Pool, sql string, owner any) (int, error) {
	var n int64
	err := pool.QueryRow(ctx, sql, owner).Scan(&n)
	return int(n), err
}

// loadArchived reads the counts and the lists of item type kind.
func loadArchived(ctx context.Context, d deps, owner any, kind string) (*archivedData, error) {
	a := &archivedData{Type: kind}
	var err error
	for _, c := range []struct {
		sql string
		dst *int
	}{
		{archivedStaysCountSQL, &a.Counts.Stays}, {archivedPropertiesCountSQL, &a.Counts.Properties},
		{archivedGuestsCountSQL, &a.Counts.Housebook}, {archivedEntitiesCountSQL, &a.Counts.Entities},
	} {
		if *c.dst, err = scanCount(ctx, d.pool, c.sql, owner); err != nil {
			return nil, err
		}
	}
	a.Counts.All = a.Counts.Stays + a.Counts.Properties + a.Counts.Housebook + a.Counts.Entities
	if a.Show("stays") {
		rows, err := d.pool.Query(ctx, archivedStaysSQL, owner)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var s archivedStay
			var archived *string
			if err := rows.Scan(&s.ID, &s.DateFrom, &s.DateTo, &s.InternalName, &archived); err != nil {
				rows.Close()
				return nil, err
			}
			s.Archived = str(archived)
			a.Stays = append(a.Stays, s)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}
	if a.Show("properties") {
		rows, err := d.pool.Query(ctx, archivedPropertiesSQL, owner)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var p archivedProperty
			var archived *string
			if err := rows.Scan(&p.ID, &p.InternalName, &archived, &p.Reservations); err != nil {
				rows.Close()
				return nil, err
			}
			p.Archived = str(archived)
			a.Properties = append(a.Properties, p)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}
	if a.Show("housebook") {
		// housebook.housebook_archived_rows: SELECT g.*, so every guest field
		// is decrypted and a broken token is a 500, as in Python.
		guests, _, err := queryRows(ctx, d.pool, archivedHousebookSQL, owner)
		if err != nil {
			return nil, err
		}
		for _, g := range guests {
			if err := hydrate(d.getenv, g); err != nil {
				return nil, err
			}
			a.Housebook = append(a.Housebook, archivedGuest{
				GuestID: g.int("id"), Apartment: g.str("internal_name"),
				StayFrom: orStr(g.str("stay_from"), g.str("res_from")), StayTo: orStr(g.str("stay_to"), g.str("res_to")),
				Surname: g.str("surname"), FirstName: g.str("first_name"), Archived: g.str("archived_at"),
			})
		}
	}
	if a.Show("entities") {
		rows, err := d.pool.Query(ctx, archivedEntitiesSQL, owner)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var e archivedEntity
			var archived *string
			if err := rows.Scan(&e.ID, &e.Name, &archived, &e.ICO); err != nil {
				rows.Close()
				return nil, err
			}
			e.Archived = str(archived)
			a.Entities = append(a.Entities, e)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}
	return a, nil
}

// ArchivedHandler is exports.settings_archived_view.
func ArchivedHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		kind := "all"
		if values, present := r.URL.Query()["type"]; present {
			kind = values[len(values)-1]
		}
		if !archivedTypes[kind] {
			kind = "all"
		}
		data, err := loadArchived(r.Context(), d, ownerID(h), kind)
		if err != nil {
			serverError(w, err)
			return
		}
		if err := renderArchived(w, r, d, h, at, data); err != nil {
			serverError(w, err)
		}
	}
}

// renderArchived fills the title and pill values and renders the page.
func renderArchived(w http.ResponseWriter, r *http.Request, d deps, h *session.Host, at time.Time, data *archivedData) error {
	lang := layout.Lang(r, h)
	t := func(key string, count int) string {
		return catalog.T(lang, key, map[string]any{"count": count})
	}
	title := catalog.T(lang, "archive.title", nil)
	if i := strings.LastIndex(title, " "); i >= 0 {
		data.TitleHead, data.TitleLast = title[:i], title[i+1:]
	} else {
		data.TitleLast = title
	}
	for _, p := range []struct {
		kind, key string
		count     int
	}{
		{"all", "archive.chip.all_count", data.Counts.All},
		{"stays", "archive.chip.stays_count", data.Counts.Stays},
		{"properties", "archive.chip.properties_count", data.Counts.Properties},
		{"housebook", "archive.chip.housebook_count", data.Counts.Housebook},
		{"entities", "archive.chip.entities_count", data.Counts.Entities},
	} {
		data.Pills = append(data.Pills, pill{Label: t(p.key, p.count), Href: "/settings/archived?type=" + p.kind, Current: data.Type == p.kind})
	}
	data.ReturnTo = "/settings/archived"
	if data.Type != "all" {
		data.ReturnTo += "?type=" + data.Type
	}
	page := layout.Page{Title: title, Nav: "settings", BodyKind: "list", V2: true, BackURL: "/settings", BodyAlerts: true}
	return layout.Render(w, r, layout.Env{Pool: d.pool, Getenv: d.getenv, Now: at}, h, page, pages, "archived", data)
}
