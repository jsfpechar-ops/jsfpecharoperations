package booking

// Host booking sites list (brief 1710b): payments.booking_sites.
// Python: App/app/routes/payments.py 530-551.

import (
	"context"
	"embed"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed booking_sites_list_i18n.json
var bookingSitesListI18nJSON []byte

//go:embed templates/booking_sites.tmpl
var bookingSitesFS embed.FS

var (
	bookingSitesCatalog = hostweb.Load(bookingSitesListI18nJSON)
	bookingSitesPages   = layout.MustParseFuncs(bookingSitesCatalog, nil, bookingSitesFS, "templates/booking_sites.tmpl")
)

type bookingSitesServer struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type bookingSiteRow struct {
	ID           int64
	InternalName string
	Published    bool
}

type bookingSitesData struct {
	Allowed bool
	Rows    []bookingSiteRow
}

const listApartmentsSQL = `SELECT a.id, a.internal_name, COALESCE(p.published, 0) AS published
	FROM apartment a
	LEFT JOIN property_page p ON p.apartment_id = a.id
	WHERE a.owner_user_id = $1 AND a.archived_at IS NULL AND a.active = 1
	ORDER BY a.internal_name, a.id`

func listOwnerApartments(ctx context.Context, db DB, ownerID int64) ([]bookingSiteRow, error) {
	rows, err := db.Query(ctx, listApartmentsSQL, ownerID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []bookingSiteRow
	for rows.Next() {
		var r bookingSiteRow
		var published int
		if err := rows.Scan(&r.ID, &r.InternalName, &published); err != nil {
			return nil, err
		}
		r.Published = published != 0
		out = append(out, r)
	}
	return out, rows.Err()
}

func bookingSitesFail(w http.ResponseWriter, err error) {
	log.Printf("booking booking_sites_list: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// RegisterBookingSitesList registers GET /booking-sites (dormant until UBYHOST_GO_PATHS).
func RegisterBookingSitesList(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	s := &bookingSitesServer{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /booking-sites", wrap("/booking-sites", s.list()))
}

func (s *bookingSitesServer) list() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
		if err != nil {
			bookingSitesFail(w, err)
			return
		}
		if h == nil {
			return
		}
		ctx := r.Context()
		ownerID := h.Workspace.ID
		rows, err := listOwnerApartments(ctx, s.pool, ownerID)
		if err != nil {
			bookingSitesFail(w, err)
			return
		}
		if len(rows) == 1 {
			http.Redirect(w, r, fmt.Sprintf("/apartments/%d/booking-site", rows[0].ID), http.StatusSeeOther)
			return
		}
		allowed, err := SiteAllowed(ctx, s.pool, s.getenv, ownerID)
		if err != nil {
			bookingSitesFail(w, err)
			return
		}
		lang := hostweb.Lang(r)
		title := bookingSitesCatalog.T(lang, "bsite.title", nil)
		page := layout.Page{Title: title, Nav: "booking_sites", BodyKind: "list", V2: true}
		w.Header().Set("Cache-Control", "no-store, private")
		data := bookingSitesData{Allowed: allowed, Rows: rows}
		env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: at}
		if err := layout.Render(w, r, env, h, page, bookingSitesPages, "booking_sites", data); err != nil {
			bookingSitesFail(w, err)
		}
	}
}
