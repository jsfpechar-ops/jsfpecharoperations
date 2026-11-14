package cleaning

// Host pages of the cleaning area (brief 1570 and the briefs after it). The
// Python reference is App/app/routes/cleaning.py; the page bodies are the Go
// twins of cleaning.html, cleaning_edit.html and cleaning_properties.html (and,
// in the later briefs, cleaning_settings.html and cleaning_shares.html), drawn
// inside the host layout (hostweb/layout). Routes register through hostAdd from
// an init() in each file; go/cmd/ubyhost-web/register_web_cleaning_host.go
// hands them to the mux. Nothing is switched on until the owner routes the paths.

import (
	"embed"
	"errors"
	"html/template"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed hosttemplates/*.tmpl
var hostFiles embed.FS

// hostPages is parsed once; the layout clones it per request. The page
// catalog is the calendar.*, status.* and common.* texts of i18n.json "host".
var hostPages = layout.MustParseFuncs(hostweb.Catalog(texts.Host), template.FuncMap{
	"ct":      ct,
	"scales":  func() []string { return []string{"month", "week", "year"} },
	"shows":   func() []string { return []string{"property", "label", "guests"} },
	"errtext": errText,
}, hostFiles, "hosttemplates/*.tmpl")

// errText is the error line of the cleaning forms: ct(error ~ '_error') for
// notes, property and code, ct(error) for every other key.
func errText(lang, key string) string {
	switch key {
	case "notes", "property", "code":
		return ct(lang, key+"_error")
	}
	return ct(lang, key)
}

// suffix ends the <title> of the pages whose Python block title is "<text> · UbyHost".
const suffix = " · UbyHost"

// Wrap is the metrics wrapper of cmd/ubyhost-web (metrics.wrap).
type Wrap func(route string, h http.HandlerFunc) http.Handler

// hostServer holds what the host handlers share.
type hostServer struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type hostRoute struct {
	pattern string
	build   func(*hostServer) http.HandlerFunc
}

var hostRoutes []hostRoute

// hostAdd registers one host route ("GET /cleaning/new"). Call it from init().
func hostAdd(pattern string, build func(*hostServer) http.HandlerFunc) {
	hostRoutes = append(hostRoutes, hostRoute{pattern, build})
}

// RegisterHost adds the host routes of this package. It only builds handlers;
// the pool is first used inside a request.
func RegisterHost(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &hostServer{pool: pool, getenv: getenv, now: now}
	for _, r := range hostRoutes {
		label := r.pattern[strings.Index(r.pattern, " ")+1:]
		mux.Handle(r.pattern, wrap(label, r.build(s)))
	}
}

// login is auth.require_login: a nil host means the response is written.
func (s *hostServer) login(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		serverError(w)
		return nil, false
	}
	return h, h != nil
}

// csrf is the router dependency security.protect_host_post: it runs before
// the path parameters are read and before the login.
func (s *hostServer) csrf(w http.ResponseWriter, r *http.Request, at time.Time) bool {
	return hostweb.CSRF(w, r, s.getenv, at)
}

// pathID reads an integer path parameter; FastAPI answers 422 for text.
func pathID(w http.ResponseWriter, r *http.Request, name string) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue(name), 10, 64)
	if err != nil {
		writeDetail(w, http.StatusUnprocessableEntity, "Unprocessable Entity")
		return 0, false
	}
	return id, true
}

// page renders one host page: routes/cleaning._render (PRIVATE headers). title is the whole <title> text.
func (s *hostServer) page(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, status int, title, name, bodyKind string, data any) {
	setPrivate(w)
	env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: at}
	p := layout.Page{Title: title, Nav: "cleaning", BodyKind: bodyKind, V2: true, Status: status}
	if err := layout.Render(w, r, env, h, p, hostPages, name, data); err != nil {
		serverError(w)
	}
}

// redirect is RedirectResponse(..., 303, headers=PRIVATE).
func redirect(w http.ResponseWriter, location string) {
	setPrivate(w)
	w.Header().Set("Location", location)
	w.WriteHeader(http.StatusSeeOther)
}

// lastOf is Starlette's QueryParams.get: the last value of a repeated key.
func lastOf(v url.Values, key string) (string, bool) {
	vs, ok := v[key]
	if !ok || len(vs) == 0 {
		return "", false
	}
	return vs[len(vs)-1], true
}

// queryOr is request.query_params.get(key, fallback): the fallback only when the key is absent.
func queryOr(v url.Values, key, fallback string) string {
	if s, ok := lastOf(v, key); ok {
		return s
	}
	return fallback
}

// pyStrip is Python str.strip(): Unicode white space plus \x1c to \x1f.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) })
}

func runeLen(s string) int { return utf8.RuneCountInString(s) }

// period is routes/cleaning._period: from or cal_date or today, to or +30 days.
func period(q url.Values, at time.Time) (time.Time, time.Time, error) {
	start := ""
	for _, key := range []string{"from", "cal_date"} {
		if v, _ := lastOf(q, key); v != "" {
			start = v
			break
		}
	}
	if start == "" {
		start = iso(today(at))
	}
	first, err := parseDate(start)
	if err != nil {
		return first, first, err
	}
	end, _ := lastOf(q, "to")
	if end == "" {
		end = iso(first.AddDate(0, 0, 30))
	}
	return parseRange(iso(first), end)
}

// indexPage is what cleaning.tmpl reads (the shared page's page struct, plus the notice).
type indexPage struct {
	Lang, Today, Date, Source, From, To, Notice string
	Props                                       []propOut
	ListHTML, LabelsScript, CalScripts          template.HTML
}

func init() { hostAdd("GET /cleaning", (*hostServer).index) }

// index is routes/cleaning.index (lines 128-144).
func (s *hostServer) index() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		q := r.URL.Query()
		first, last, err := period(q, at)
		var p *payload
		if err == nil {
			lang := hostweb.Lang(r)
			p, err = buildPayload(r.Context(), s.pool, s.getenv, r, first, last, nil, false, ownerID(h), lang, at)
		}
		switch {
		case errors.Is(err, errNotFound):
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		case errors.Is(err, errDates) || (err != nil && err.Error() == "dates"):
			writeDetail(w, http.StatusUnprocessableEntity, "Invalid cleaning range")
			return
		case err != nil:
			serverError(w)
			return
		}
		lang := hostweb.Lang(r)
		notice, _ := lastOf(q, "notice")
		data := indexPage{
			Lang: lang, Today: iso(today(at)), Date: iso(first), Source: "/cleaning/schedule",
			From: iso(first), To: iso(last), Notice: notice, Props: p.Properties,
			ListHTML: template.HTML(p.ListHTML), LabelsScript: labelsScript(lang), CalScripts: calScripts(lang, p.Properties),
		}
		s.page(w, r, h, at, 0, ct(lang, "title")+suffix, "cleaning", "list", data)
	}
}

// editPage is what cleaning_edit.tmpl reads.
type editPage struct {
	Lang     string
	Event    *eventView
	Values   formValues
	Homes    []home
	Error    string
	TimesURL string
}

// eventView is the part of the cleaning_event row the editor shows.
type eventView struct {
	ID, ApartmentID, Revision int64
	Auto                      bool
}

// formValues is the editor's `values`: raw text, as Python's dict(form).
type formValues struct{ ScheduledDate, ApartmentID, Notes, Revision string }

// editor is routes/cleaning._editor.
func (s *hostServer) editor(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, v formValues, ev *eventView, errKey string, status int) {
	homes, err := properties(r.Context(), s.pool, ownerID(h), nil)
	if err != nil {
		serverError(w)
		return
	}
	lang := hostweb.Lang(r)
	times := "/apartments/"
	if v.ApartmentID != "" {
		times = "/apartments/" + v.ApartmentID + "?view=settings&section=property#arrival-departure"
	}
	title := ct(lang, "add")
	if ev != nil {
		title = ct(lang, "edit")
	}
	title += suffix
	s.page(w, r, h, at, status, title, "cleaning_edit", "list",
		editPage{Lang: lang, Event: ev, Values: v, Homes: homes, Error: errKey, TimesURL: times})
}

func init() { hostAdd("GET /cleaning/new", (*hostServer).newEvent) }

// newEvent is routes/cleaning.new_event (lines 165-173).
func (s *hostServer) newEvent() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		q := r.URL.Query()
		s.editor(w, r, h, at, formValues{
			ScheduledDate: queryOr(q, "date", iso(today(at))),
			ApartmentID:   queryOr(q, "property", ""),
		}, nil, "", 0)
	}
}

func init() { hostAdd("GET /cleaning/events/{id}/edit", (*hostServer).editEvent) }

// editEvent is routes/cleaning.edit_event (lines 204-213).
func (s *hostServer) editEvent() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		owner := ownerID(h)
		if err := reconcile(r.Context(), s.pool, owner, at); err != nil {
			serverError(w)
			return
		}
		ev, err := eventFor(r.Context(), s.pool, owner, id)
		if err != nil {
			serverError(w)
			return
		}
		if ev == nil || ev.State != "scheduled" {
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		notes := ""
		if ev.NotesEnc != nil && *ev.NotesEnc != "" {
			if notes, err = (&fieldReader{getenv: s.getenv, at: at}).decrypt(*ev.NotesEnc); err != nil {
				serverError(w)
				return
			}
		}
		s.editor(w, r, h, at, formValues{
			ScheduledDate: ev.Date, ApartmentID: strconv.FormatInt(ev.ApartmentID, 10),
			Notes: notes, Revision: strconv.FormatInt(ev.Revision, 10),
		}, &eventView{ID: ev.ID, ApartmentID: ev.ApartmentID, Revision: ev.Revision, Auto: ev.Source != nil}, "", 0)
	}
}

// propertiesPage is what cleaning_properties.tmpl reads.
type propertiesPage struct {
	Lang  string
	Homes []home
}

func init() { hostAdd("GET /cleaning/properties", (*hostServer).chooseProperty) }

// chooseProperty is routes/cleaning.choose_property (lines 265-271).
func (s *hostServer) chooseProperty() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		homes, err := properties(r.Context(), s.pool, ownerID(h), nil)
		if err != nil {
			serverError(w)
			return
		}
		lang := hostweb.Lang(r)
		s.page(w, r, h, at, 0, ct(lang, "settings")+suffix, "cleaning_properties", "list", propertiesPage{Lang: lang, Homes: homes})
	}
}
