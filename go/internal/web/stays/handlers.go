package stays

import (
	"context"
	"embed"
	"errors"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed i18n.json
var catalogJSON []byte

//go:embed templates/*.tmpl
var templateFS embed.FS

var catalog = hostweb.Load(catalogJSON)

type apartmentItem struct {
	ID   int64
	Name string
}

type listPage struct {
	View             View
	Apartments       []apartmentItem
	Status           string
	Report           string
	ApartmentID      int64
	DateFrom         string
	DateTo           string
	DateRange        string
	ShowArchive      bool
	ReturnTo         string
	HasAny           int
	FeedCount        int
	DemoAvailable    bool
	CSVExportParams  string
	StayProperty     string
	FilterSummaryHTML string
	PaymentsHidden   bool
	PublicBase       string
	Today            time.Time
	PageSize         int
	PrevURL          string
	NextURL          string
	Groups           map[string][]Row
}

// ListHandler serves GET /reservations (admin.py reservations_list).
func ListHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if host == nil {
			return
		}
		owner := host.Workspace.ID
		ctx := r.Context()
		p := ParseParams(r.URL.Query(), at)
		v, err := List(ctx, pool, getenv, owner, p, at)
		if err != nil {
			serverError(w, err)
			return
		}
		apts, err := loadApartments(ctx, pool, owner)
		if err != nil {
			serverError(w, err)
			return
		}
		hasAny, feedCount, demoAvail, err := loadMeta(ctx, pool, getenv, owner)
		if err != nil {
			serverError(w, err)
			return
		}
		propLabel := catalog.T(hostweb.Lang(r), "host.filter.all_properties", nil)
		for _, a := range apts {
			if p.ApartmentID != 0 && a.ID == p.ApartmentID {
				propLabel = a.Name
			}
		}
		groups := groupRows(v.Rows, at)
		data := listPage{
			View: v, Apartments: apts, Status: p.Status, Report: p.Report,
			ApartmentID: p.ApartmentID, DateFrom: p.DateFrom, DateTo: p.DateTo,
			DateRange: p.DateRange, ShowArchive: p.ShowArchive,
			ReturnTo: returnTo(r), HasAny: hasAny, FeedCount: feedCount, DemoAvailable: demoAvail,
			CSVExportParams: "apartment=" + strconv.FormatInt(p.ApartmentID, 10),
			StayProperty: propLabel, PaymentsHidden: paymentsHidden(getenv),
			PublicBase: publicBaseURL(getenv), Today: pragueToday(at), PageSize: PageSize,
			PrevURL: v.PrevURL, NextURL: v.NextURL, Groups: groups,
		}
		page := layout.Page{
			Title: catalog.T(hostweb.Lang(r), "stays.title", nil),
			Nav: "reservations", BodyKind: "list", V2: true, HowKey: "stays", BodyAlerts: true,
			TurboCache: "cache",
		}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, page, pages, "stays_list", data); err != nil {
			serverError(w, err)
		}
	}
}

func returnTo(r *http.Request) string {
	u := r.URL.Path
	if q := r.URL.RawQuery; q != "" {
		u += "?" + q
	}
	return u
}

func loadApartments(ctx context.Context, pool *pgxpool.Pool, owner int64) ([]apartmentItem, error) {
	rows, err := pool.Query(ctx,
		`SELECT id, internal_name FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY internal_name`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []apartmentItem
	for rows.Next() {
		var a apartmentItem
		if err := rows.Scan(&a.ID, &a.Name); err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func loadMeta(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner int64) (hasAny, feedCount int, demo bool, err error) {
	var one int
	err = pool.QueryRow(ctx,
		`SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id IS NOT DISTINCT FROM $1 LIMIT 1`, owner).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		err = nil
	} else if err != nil {
		return
	} else {
		hasAny = 1
	}
	var n int64
	err = pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL AND f.active = 1`, owner).Scan(&n)
	if err != nil {
		return
	}
	feedCount = int(n)
	demo = strings.ToLower(getenv("UBYHOST_DEMO_ENABLED")) == "1" || getenv("UBYHOST_DEMO_ENABLED") == ""
	return
}

func groupRows(rows []Row, at time.Time) map[string][]Row {
	out := map[string][]Row{"today": {}, "week": {}, "later": {}, "earlier": {}}
	for _, row := range rows {
		g := stayGroup(row.Reservation, at)
		out[g] = append(out[g], row)
	}
	return out
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("stays: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// Register adds GET /reservations to mux.
func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	mux.Handle("GET /reservations", wrap("/reservations", ListHandler(pool, getenv, now)))
}
