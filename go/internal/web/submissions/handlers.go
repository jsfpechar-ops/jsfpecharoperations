package submissions

// GET /submissions and GET /submissions/{submission_id} (brief 1730).
// Python: admin.submissions_list and admin.submission_detail.
// Routes stay dormant until the owner adds the path to UBYHOST_GO_PATHS.

import (
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

type listPage struct {
	ListPage
	Lang string
}

type detailPage struct {
	DetailPage
	Lang string
}

func listHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
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
		lang := hostweb.Lang(r)
		p, err := LoadList(r.Context(), pool, host.Workspace.ID)
		if err != nil {
			serverError(w, err)
			return
		}
		page := layout.Page{
			Title: catalog.T(lang, "reports.title", nil),
			Nav:   "submissions", BodyKind: "list", V2: true, HowKey: "reports",
		}
		data := listPage{ListPage: *p, Lang: lang}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, page, pages, "submissions_list", data); err != nil {
			serverError(w, err)
		}
	}
}

func detailHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
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
		id, err := strconv.ParseInt(r.PathValue("submission_id"), 10, 64)
		if err != nil {
			hostweb.NotFoundPage(w, r)
			return
		}
		lang := hostweb.Lang(r)
		p, ok, err := LoadDetail(r.Context(), pool, host.Workspace.ID, id, lang)
		if err != nil {
			serverError(w, err)
			return
		}
		if !ok {
			lang := hostweb.Lang(r)
			errFlash := hostweb.Flash{Text: catalog.T(lang, "flash.error.no_such_submission", nil), Key: "flash.error.no_such_submission"}
			hostweb.Back(w, r, "/submissions", hostweb.Flash{}, errFlash)
			return
		}
		page := layout.Page{
			Title:    detailTitle(lang, id),
			Nav:      "submissions",
			BodyKind: "detail",
			V2:       true,
			BackURL:  "/submissions",
		}
		data := detailPage{DetailPage: *p, Lang: lang}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, page, pages, "submission_detail", data); err != nil {
			serverError(w, err)
		}
	}
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("submissions: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// Register adds GET /submissions and GET /submissions/{submission_id}.
func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	mux.Handle("GET /submissions", wrap("/submissions", listHandler(pool, getenv, now)))
	mux.Handle("GET /submissions/{submission_id}", wrap("/submissions/{submission_id}", detailHandler(pool, getenv, now)))
}
