package public

import (
	"bytes"
	"embed"
	"net/http"
	"strings"
	"text/template"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

// Paths lists the routes this package serves, in registration order.
var Paths = []string{"/legal", "/terms", "/privacy", "/dpa", "/subprocessors"}

// sharedFiles are parsed into every page's template set.
var sharedFiles = []string{"templates/base.tmpl", "templates/header.tmpl", "templates/footer.tmpl",
	"templates/posthog.tmpl", "templates/toc.tmpl", "templates/cookie_table.tmpl", "templates/operator.tmpl"}

var sets = parseSets()

// parseSets builds one template set per page: the shared files plus
// templates/<page>.tmpl, which defines "title" and "content".
func parseSets() map[string]*template.Template {
	out := map[string]*template.Template{}
	for _, path := range Paths {
		files := append(append([]string{}, sharedFiles...), "templates"+path+".tmpl")
		out[path] = template.Must(template.New("base.tmpl").ParseFS(templateFS, files...))
	}
	return out
}

// Deps are the outside inputs of a request. SignedIn is asked only when
// neither ?lang= nor the ubyhost_lang cookie names a language; nil means
// signed out.
type Deps struct {
	Getenv   func(string) string
	SignedIn func(*http.Request) bool
}

const (
	langCookieMaxAge = 60 * 60 * 24 * 180                // host_i18n.LANG_COOKIE_MAX_AGE
	sessionCookie    = "ubyhost_session"                 // auth.SESSION_COOKIE
	edgeCacheControl = "public, max-age=0, s-maxage=300" // main._EDGE_CACHE_CONTROL
)

// Handler serves one of the five legal pages. The mux pattern "GET /legal"
// also matches HEAD; a HEAD gets the headers only.
func Handler(path string, d Deps) http.HandlerFunc {
	tmpl, ok := sets[path]
	if !ok {
		panic("public: no page for " + path)
	}
	return func(w http.ResponseWriter, r *http.Request) {
		cfg := loadConfig(d.Getenv)
		lang := resolveLang(r, d.SignedIn)
		var buf bytes.Buffer
		if err := tmpl.ExecuteTemplate(&buf, "base.tmpl", newPage(r, path, lang, cfg)); err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		h := w.Header()
		h.Set("Content-Type", "text/html; charset=utf-8")
		if cfg.posthogOn() {
			h.Set("Content-Security-Policy", publicCSP(cfg))
		}
		setCookie := false
		if asked := supportedLanguage(r.URL.Query().Get("lang")); asked != "" && hostweb.Cookie(r, langCookieName) != asked {
			http.SetCookie(w, &http.Cookie{
				Name: langCookieName, Value: asked, MaxAge: langCookieMaxAge, Path: "/",
				SameSite: http.SameSiteLaxMode,
				Secure:   strings.HasPrefix(strings.ToLower(cfg.PublicBase), "https://"),
			})
			setCookie = true
		}
		if !setCookie && edgeCacheable(r) {
			h.Set("Cache-Control", edgeCacheControl)
		}
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write(buf.Bytes())
		}
	}
}

// edgeCacheable is main._apply_edge_cache for a 200 GET: no query string and
// no session or language cookie.
func edgeCacheable(r *http.Request) bool {
	if r.URL.RawQuery != "" {
		return false
	}
	for _, name := range []string{sessionCookie, langCookieName} {
		if _, err := r.Cookie(name); err == nil {
			return false
		}
	}
	return true
}
