package onboarding

// Brief 1599 and the briefs after it: the setup wizard of
// App/app/routes/onboarding_wizard.py (GET /apartments/{id}/setup, GET
// /apartments/{id}/setup/{step}, POST /apartments/{id}/setup). This file holds
// the route table, the request gate and the page renderer; wizard_data.go is
// _wizard_context; each route lives in its own wizard_*.go file and adds
// itself with wizardAdd from an init(), so a later brief adds a file instead
// of editing this one. The page bodies are the Go twins of
// App/app/templates/setup_wizard/*.html in wizardtemplates/, drawn inside the
// host layout (hostweb/layout). The strings are wizardtext/i18n.json, written
// by App/scripts/go_host_i18n.py from wizardtext/i18n_keys.txt. Nothing is
// switched on: no path reaches these routes until UBYHOST_GO_PATHS names it.

import (
	"bytes"
	"embed"
	"encoding/json"
	"html/template"
	"io"
	"io/fs"
	"log"
	"net/http"
	"path"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed wizardtext/i18n.json
var wizardTextJSON []byte

// wizardText is the host catalog of the wizard pages and flashes.
var wizardText = hostweb.Load(wizardTextJSON)

//go:embed wizardtemplates/*.tmpl
var wizardFiles embed.FS

// wizardFuncs are the page funcs the wizard templates add to the layout's.
var wizardFuncs = template.FuncMap{
	"wizard_hour":  func(h int) string { return wizardTwo(h) + ":00" },
	"wizard_first": wizardFirstRune,
}

// wizardPages holds one template set per step page: the shared files
// (wizardtemplates/_*.tmpl: the frame of setup_wizard/_layout.html and the
// partials) plus <step>.tmpl, which fills the frame's blocks as the Jinja
// page fills _layout.html's. A step whose file is not here yet (a later
// brief adds it) answers 501. Parsed once; the layout clones a set per request.
var wizardPages = wizardParsePages()

func wizardParsePages() map[string]*layout.Templates {
	out := map[string]*layout.Templates{}
	names, err := fs.Glob(wizardFiles, "wizardtemplates/*.tmpl")
	if err != nil {
		panic("onboarding wizard: " + err.Error())
	}
	for _, name := range names {
		base := path.Base(name)
		if strings.HasPrefix(base, "_") {
			continue
		}
		out[strings.TrimSuffix(base, ".tmpl")] = layout.MustParseFuncs(wizardText, wizardFuncs, wizardFiles, "wizardtemplates/_*.tmpl", name)
	}
	return out
}

// WizardWrap is the metrics wrapper of cmd/ubyhost-web (metrics.wrap).
type WizardWrap func(route string, h http.HandlerFunc) http.Handler

// wizardServer holds what the wizard handlers share.
type wizardServer struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type wizardRoute struct {
	pattern string
	build   func(*wizardServer) http.HandlerFunc
}

var wizardRoutes []wizardRoute

// wizardAdd registers one route ("GET /apartments/{id}/setup"). Call it from init().
func wizardAdd(pattern string, build func(*wizardServer) http.HandlerFunc) {
	wizardRoutes = append(wizardRoutes, wizardRoute{pattern, build})
}

// RegisterWizard adds the wizard routes. It only builds handlers; the pool is
// first used inside a request.
func RegisterWizard(mux *http.ServeMux, wrap WizardWrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &wizardServer{pool: pool, getenv: getenv, now: now}
	for _, r := range wizardRoutes {
		label := r.pattern[strings.Index(r.pattern, " ")+1:]
		mux.Handle(r.pattern, wrap(label, r.build(s)))
	}
}

// wizardPathID reads {id} as FastAPI reads apartment_id: int; text is a 422
// with FastAPI's body.
func wizardPathID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	raw := r.PathValue("id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err == nil && raw != "" && raw[0] != '+' {
		return id, true
	}
	var input bytes.Buffer
	enc := json.NewEncoder(&input)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(raw)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnprocessableEntity)
	_, _ = io.WriteString(w, `{"detail":[{"type":"int_parsing","loc":["path","apartment_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":`+strings.TrimSpace(input.String())+`}]}`)
	return 0, false
}

// wizardLogin is auth.require_login: a nil host means the response is written.
func (s *wizardServer) wizardLogin(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	return h, h != nil
}

// wizardFlash is admin_helpers.flash(request, key): the text in the host's language.
func wizardFlash(r *http.Request, key string) hostweb.Flash {
	return hostweb.Flash{Text: wizardText.T(hostweb.Lang(r), key, nil), Key: key}
}

// wizardBack is admin_helpers.back(path) with no message.
func wizardBack(w http.ResponseWriter, r *http.Request, path string) {
	hostweb.Back(w, r, path, hostweb.Flash{}, hostweb.Flash{})
}

// wizardNotPorted answers a branch whose Go port is still to come (501).
func wizardNotPorted(w http.ResponseWriter, what string) {
	w.Header().Set("Cache-Control", "no-store, private")
	http.Error(w, "Not implemented in Go yet: "+what, http.StatusNotImplemented)
}

// wizardRender is render_wizard: setup_wizard/<step>.html inside the host
// layout (v2, nav apartments, body form). The <title> is wizard.title.
func (s *wizardServer) wizardRender(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, status int, v *wizardView) {
	tpl, ok := wizardPages[v.Step]
	if !ok {
		wizardNotPorted(w, "the "+v.Step+" step page")
		return
	}
	env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: at}
	title := wizardText.T(v.Lang, "wizard.title", map[string]any{"name": v.Apt.InternalName})
	p := layout.Page{Title: title, Nav: "apartments", BodyKind: "form", V2: true, Status: status}
	if err := layout.Render(w, r, env, h, p, tpl, "wizard_page", v); err != nil {
		log.Printf("onboarding wizard: render %s: %v", v.Step, err)
		serverError(w, err)
	}
}

// wizardTwo is "%02d" for an hour.
func wizardTwo(n int) string {
	if n >= 0 && n < 10 {
		return "0" + strconv.Itoa(n)
	}
	return strconv.Itoa(n)
}

// wizardFirstRune is Python's text[:1].
func wizardFirstRune(s string) string {
	for _, r := range s {
		return string(r)
	}
	return ""
}
