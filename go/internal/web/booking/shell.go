package booking

// The guest page shell: the port of App/app/templates/base.html for a page
// rendered with show_nav = false (every public booking page, the guest bank
// page, the QR preview). The host layout (go/internal/hostweb/layout) always
// wraps its body in the host_page frame, so it cannot serve these pages.
//
// What differs from Python on purpose: no CSRF cookie and no csrf-token meta.
// No public booking form carries a CSRF field (the Python router has no CSRF
// dependency), and csrf.js does nothing without the meta. Everything else
// (head, scripts, skip link, main, skeleton, the three dialogs) is the same
// markup, with the same ?v= values, so the same CSS and scripts load.
//
// Page files define "guest.content" (the base.html content block) and may
// redefine "guest.head" (head_extra). They read their data as {{.Data}} and
// translate with {{.T "key"}}. Sets are built by newSet inside a handler
// factory, never in a package-level var, so a later file may add template
// funcs in its init() before any set is parsed.

import (
	"bytes"
	"embed"
	"html/template"
	"io"
	"log"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed templates
var guestFS embed.FS

//go:embed i18n.json
var guestJSON []byte

// guestStrings is the catalog written by App/scripts/go_host_i18n.py from
// i18n_keys.txt in this directory.
var guestStrings = hostweb.Load(guestJSON)

// guestFuncs are the funcs every guest set gets. Add to it from init().
var guestFuncs = template.FuncMap{}

// Alternate is a <link rel="alternate" hreflang>.
type Alternate struct{ Code, Href string }

// Guest is what a guest page template receives.
type Guest struct {
	Lang       string
	Title      string
	Head       template.HTML // head_extra, built by the handler from trusted markup only
	Meta       string        // meta_description
	Canonical  string
	Alternates []Alternate
	Data       any
}

// T is the page's t(): the catalog string in the page language, with
// %(name)s placeholders filled from name, value pairs.
func (g Guest) T(key string, kv ...any) string {
	params := map[string]any{}
	for i := 0; i+1 < len(kv); i += 2 {
		if name, ok := kv[i].(string); ok {
			params[name] = kv[i+1]
		}
	}
	return guestStrings.T(g.Lang, key, params)
}

// fragment returns an embedded static HTML file as trusted markup.
func fragment(name string) template.HTML {
	raw, err := guestFS.ReadFile("templates/" + name)
	if err != nil {
		panic("booking: missing fragment " + name)
	}
	return template.HTML(raw)
}

// newSet parses the shell and the named page files (names under templates/).
func newSet(files ...string) *template.Template {
	funcs := template.FuncMap{"fragment": fragment}
	for k, v := range guestFuncs {
		funcs[k] = v
	}
	set := template.Must(template.New("guest.base").Funcs(funcs).ParseFS(guestFS, "templates/shell.tmpl"))
	paths := make([]string, len(files))
	for i, f := range files {
		paths[i] = "templates/" + f
	}
	return template.Must(set.ParseFS(guestFS, paths...))
}

// pageLang is property_page._page_lang: ?lang=cs|en, then the saved language
// cookie, then Czech. It sets no cookie.
func pageLang(r *http.Request) string {
	for _, v := range []string{r.URL.Query().Get("lang"), hostweb.Cookie(r, "ubyhost_lang")} {
		if v == "cs" || v == "en" {
			return v
		}
	}
	return "cs"
}

// writeGuest renders the page into a buffer first, so a failed template is a
// clean 500 and never a half page. extra headers are set after Content-Type.
func writeGuest(w http.ResponseWriter, r *http.Request, set *template.Template, status int, g Guest, extra map[string]string) {
	var buf bytes.Buffer
	if err := set.ExecuteTemplate(&buf, "guest.base", g); err != nil {
		log.Printf("booking guest page: %v", err)
		text(w, http.StatusInternalServerError, "Internal Server Error")
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	for k, v := range extra {
		h.Set(k, v)
	}
	w.WriteHeader(status)
	if r.Method != http.MethodHead {
		_, _ = io.Copy(w, &buf)
	}
}
