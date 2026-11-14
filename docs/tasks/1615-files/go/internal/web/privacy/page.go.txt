package privacy

// GET /privacy-requests: routes/privacy_requests.py privacy_requests_list
// with the template privacy_requests.html (brief 1615).

import (
	"embed"
	"html/template"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

// pageFuncs are the Jinja filters the template uses that the layout lacks.
var pageFuncs = template.FuncMap{"date_cz": dateCZ}

var pages = layout.MustParseFuncs(catalog, pageFuncs, templateFS, "templates/*.tmpl")

// listData is the context privacy_requests_list renders.
type listData struct {
	Requests     []Request
	Channels     []string
	RequestTypes []string
	SubjectKinds []string
	Statuses     []string
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

// ListHandler is GET /privacy-requests (privacy_requests_list).
func ListHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			fail(w, err)
			return
		}
		if h == nil {
			return
		}
		owner := h.Workspace.ID
		rows, err := ListForOwner(r.Context(), pool, &owner)
		if err != nil {
			fail(w, err)
			return
		}
		data := listData{
			Requests:     rows,
			Channels:     Channels,
			RequestTypes: RequestTypes,
			SubjectKinds: SubjectKinds,
			Statuses:     Statuses,
		}
		lang := layout.Lang(r, h)
		page := layout.Page{Title: catalog.T(lang, "privacy_requests.title", nil), Nav: "privacy_requests", BodyKind: "list", V2: true}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, page, pages, "privacy_requests", data); err != nil {
			fail(w, err)
		}
	}
}
