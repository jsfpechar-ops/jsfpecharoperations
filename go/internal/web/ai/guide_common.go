package ai

// The guest guide editor (brief 1440 and later). Port of
// App/app/routes/guest_guide.py: this file is the part every route shares: the
// route table, the CSRF/path/login gate in FastAPI's order, the ownership
// check (_home), flashes and redirects, and the page templates. Every
// package-level name here starts with "guide" so it cannot meet a name of
// another file in package ai.

import (
	"context"
	"embed"
	"errors"
	"html"
	"html/template"
	"io"
	"log"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed guide/i18n.json
var guideStringsJSON []byte

// guideCatalog is the host catalog of the guide pages, generated from
// App/app/host_i18n.py by App/scripts/go_host_i18n.py (guide/i18n_keys.txt).
var guideCatalog = hostweb.Load(guideStringsJSON)

//go:embed guide/templates/*.tmpl
var guideTemplateFiles embed.FS

// guidePages is parsed once; the layout clones it per request.
var guidePages = layout.MustParseFuncs(guideCatalog, guideFuncs, guideTemplateFiles, "guide/templates/*.tmpl")

// guideFuncs are the page funcs of the guide templates. They are not bound to
// the request, so a caller passes translated text in.
var guideFuncs = template.FuncMap{
	// guide_pairs "a" "A" "b" "B" is the Jinja list [("a", "A"), ("b", "B")].
	"guide_pairs": func(kv ...string) [][]string {
		var out [][]string
		for i := 0; i+1 < len(kv); i += 2 {
			out = append(out, []string{kv[i], kv[i+1]})
		}
		return out
	},
	// guide_section_open and guide_section_close are {% call ui_section(title, id=, tip=) %} ... {% endcall %}.
	"guide_section_open":  guideSectionOpen,
	"guide_section_close": func() template.HTML { return "</section>" },
}

// guideSectionOpen is the head of macro ui_section (_ui_layout.html): the id,
// the h2 and, with a tip, the last word of the title in its own no-wrap span
// followed by the tip (layout.uiSection puts the tip inside that span; Python
// does not, so this is written out here).
func guideSectionOpen(id, title string, tip template.HTML) template.HTML {
	var b strings.Builder
	b.WriteString(`<section class="ui-section"`)
	if id != "" {
		b.WriteString(` id="` + html.EscapeString(id) + `"`)
	}
	b.WriteString(`><div class="ui-section-h">`)
	if tip != "" {
		head, last := "", title
		if i := strings.LastIndex(title, " "); i >= 0 {
			head, last = title[:i]+" ", title[i+1:]
		}
		b.WriteString(`<h2>` + html.EscapeString(head) + `<span class="tip-nowrap">` + html.EscapeString(last) + `</span>` + string(tip) + `</h2>`)
	} else {
		b.WriteString(`<h2>` + html.EscapeString(title) + `</h2>`)
	}
	b.WriteString(`</div>`)
	return template.HTML(b.String())
}

// GuideRoute is one pattern for http.ServeMux with its metrics label.
type GuideRoute struct {
	Pattern string
	Label   string
	Handler http.HandlerFunc
}

type guideRouteSpec struct {
	method, path string
	h            func(*guideServer, http.ResponseWriter, *http.Request)
}

// guideRouteSpecs is filled by init() in each guide*.go file.
var guideRouteSpecs []guideRouteSpec

func guideAdd(method, path string, h func(*guideServer, http.ResponseWriter, *http.Request)) {
	guideRouteSpecs = append(guideRouteSpecs, guideRouteSpec{method, path, h})
}

// GuideRoutes lists the guide editor routes. It does not use the pool: the
// handlers read it only when a request comes in.
func GuideRoutes(pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), now func() time.Time) []GuideRoute {
	s := &guideServer{pool: pool, getenv: getenv, lookupEnv: lookupEnv, now: now}
	out := make([]GuideRoute, 0, len(guideRouteSpecs))
	for _, spec := range guideRouteSpecs {
		h, method := spec.h, spec.method
		out = append(out, GuideRoute{
			Pattern: method + " " + spec.path,
			Label:   spec.path,
			Handler: func(w http.ResponseWriter, r *http.Request) {
				// @router.get / @router.post answer any other method (HEAD too) with 405.
				if r.Method != method {
					w.Header().Set("Allow", method)
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusMethodNotAllowed)
					_, _ = io.WriteString(w, `{"detail":"Method Not Allowed"}`)
					return
				}
				h(s, w, r)
			},
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Pattern < out[j].Pattern })
	return out
}

type guideServer struct {
	pool      *pgxpool.Pool
	getenv    func(string) string
	lookupEnv func(string) (string, bool)
	now       func() time.Time
}

// guidePathID is what pydantic's lax int accepts from a string, once ASCII
// whitespace is trimmed: a sign, digit groups joined by single underscores,
// and a fraction of zeros only.
var guidePathID = regexp.MustCompile(`^([+-]?[0-9]+(?:_[0-9]+)*)(?:\.0+)?$`)

// guideParseID is the FastAPI int path parameter. A number past int64 is a
// valid int to Python that matches no row, so it becomes 0 (no row has id 0).
func guideParseID(raw string) (int64, bool) {
	m := guidePathID.FindStringSubmatch(strings.Trim(raw, " \t\n\r\v\f"))
	if m == nil {
		return 0, false
	}
	id, err := strconv.ParseInt(strings.ReplaceAll(m[1], "_", ""), 10, 64)
	if err != nil {
		return 0, true
	}
	return id, true
}

// guideStamp is db.utcnow(): UTC, whole seconds, "+00:00".
func guideStamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// guideReq is what every handler starts with.
type guideReq struct {
	host *session.Host
	apt  int64 // {id}
	item int64 // {item}, 0 when the route has none
	arg  int64 // {photo}, 0 when the route has none
	lang string
	at   time.Time
	r    *http.Request
}

// enter runs the gate in FastAPI's order: for a POST the CSRF dependency
// first, then the int path parameters (422 when one is not an int), then
// auth.require_login. It returns false when it has written the response.
func (s *guideServer) enter(w http.ResponseWriter, r *http.Request) (*guideReq, bool) {
	at := s.now()
	if r.Method == http.MethodPost && !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, false
	}
	q := &guideReq{lang: hostweb.Lang(r), at: at, r: r}
	for _, p := range []struct {
		name string
		dst  *int64
	}{{"id", &q.apt}, {"item", &q.item}, {"photo", &q.arg}} {
		raw := r.PathValue(p.name)
		if raw == "" {
			continue
		}
		id, ok := guideParseID(raw)
		if !ok {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return nil, false
		}
		*p.dst = id
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		guideFail(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	q.host = h
	if r.Method == http.MethodPost {
		_ = r.ParseMultipartForm(32 << 20) // an unreadable body is an empty form
	}
	return q, true
}

func guideFail(w http.ResponseWriter, err error) {
	log.Printf("guide route failed: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// guideNotFound is HTTPException(404) as FastAPI answers it.
func guideNotFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
}

// guideApartment is the apartment row the guide routes read.
type guideApartment struct {
	ID                  int64
	InternalName        string
	CheckinInfo         string
	CheckoutInfo        string
	LeonEnabled         bool
	LeonTermsVersion    string
	LeonTermsAcceptedAt string
	LeonTermsAcceptedBy *int64
}

const guideApartmentSQL = `SELECT id, internal_name, COALESCE(checkin_info, ''), COALESCE(checkout_info, ''),
       leon_enabled <> 0, COALESCE(leon_terms_version, ''), COALESCE(leon_terms_accepted_at, ''), leon_terms_accepted_by
  FROM apartment
 WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2 AND COALESCE(archived_at, '') = ''`

// home is _home: the apartment of the signed-in workspace, not archived
// (access.apartment scopes by owner_user_id). A missing, foreign or archived
// property is a 404; ok is false when it has written the response.
func (s *guideServer) home(w http.ResponseWriter, q *guideReq) (*guideApartment, bool) {
	var a guideApartment
	err := s.pool.QueryRow(q.r.Context(), guideApartmentSQL, q.apt, q.host.Workspace.ID).Scan(
		&a.ID, &a.InternalName, &a.CheckinInfo, &a.CheckoutInfo, &a.LeonEnabled,
		&a.LeonTermsVersion, &a.LeonTermsAcceptedAt, &a.LeonTermsAcceptedBy)
	if errors.Is(err, pgx.ErrNoRows) {
		guideNotFound(w)
		return nil, false
	}
	if err != nil {
		guideFail(w, err)
		return nil, false
	}
	return &a, true
}

func (q *guideReq) base() string { return "/apartments/" + strconv.FormatInt(q.apt, 10) + "/guide" }

// flash is admin_helpers.flash: a translated text with the key it was raised under.
func (q *guideReq) flash(key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: guideCatalog.T(q.lang, key, params), Key: key}
}

// back is admin_helpers.back.
func (q *guideReq) back(w http.ResponseWriter, path string, msg, err hostweb.Flash) {
	hostweb.Back(w, q.r, path, msg, err)
}

// guideQueryValue is request.query_params.get(name): the last value wins.
func guideQueryValue(r *http.Request, name string) string {
	vals := r.URL.Query()[name]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}

// guideFormValue is Starlette's form.get(name): the last value wins; ok is false
// when the field is not in the form.
func guideFormValue(r *http.Request, name string) (string, bool) {
	vals, ok := r.PostForm[name]
	if !ok || len(vals) == 0 {
		return "", false
	}
	return vals[len(vals)-1], true
}

// render is _render: the page inside the host layout with
// Cache-Control: no-store. Nav is "apartments" for every guide page.
func (s *guideServer) render(w http.ResponseWriter, q *guideReq, name string, p layout.Page, status int, data any) {
	p.Nav = "apartments"
	p.Status = status
	w.Header().Set("Cache-Control", "no-store")
	env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: q.at}
	if err := layout.Render(w, q.r, env, q.host, p, guidePages, name, data); err != nil {
		guideFail(w, err)
	}
}

const guideAuditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
	VALUES ($1, $2, $3, $4, $5, $6, $7)`

// audit is db.audit for the signed-in account acting in its workspace.
func (s *guideServer) audit(ctx context.Context, q *guideReq, action, detail string) error {
	var impersonator *int64
	if q.host.Impersonating {
		id := q.host.Account.ID
		impersonator = &id
	}
	_, err := s.pool.Exec(ctx, guideAuditSQL, guideStamp(q.at), q.host.Account.Username, action, detail,
		q.host.Workspace.ID, q.host.Account.ID, impersonator)
	return err
}
