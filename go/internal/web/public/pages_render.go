package public

import (
	"bytes"
	"io"
	"io/fs"
	"net/http"
	"strings"
	"text/template"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// PagePaths are the exact paths this file serves; GuidePattern is the guide route.
var PagePaths = []string{"/jak-to-funguje"}

// PricingHandler is set by pages_pricing.go (brief 1622) to legal.pricing.
var PricingHandler func(Deps) http.HandlerFunc

// GuidePattern is the mux pattern of legal.public_guide.
const GuidePattern = "GET /pruvodce/{slug}"

var pageShared = []string{"templates/pages/head_nav.tmpl", "templates/pages/footer.tmpl",
	"templates/pages/posthog.tmpl", "templates/pages/privacy_first.tmpl"}

var pageSets = parsePageSets()

func parsePageSets() map[string]*template.Template {
	out := map[string]*template.Template{}
	for _, name := range []string{"product", "guide", "pricing"} {
		if _, err := fs.Stat(pagesFS, "templates/pages/"+name+".tmpl"); err != nil {
			continue // pricing.tmpl arrives with brief 1622
		}
		files := append(append([]string{}, pageShared...), "templates/pages/"+name+".tmpl")
		out[name] = template.Must(template.New(name+".tmpl").ParseFS(pagesFS, files...))
	}
	return out
}

// pageFinish writes a rendered 200 page the way Handler does for the legal
// pages: content type, the PostHog CSP, the language cookie for a ?lang= link
// and the edge cache header (main._apply_edge_cache). A HEAD gets no body.
func pageFinish(w http.ResponseWriter, r *http.Request, cfg config, body []byte) {
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
		_, _ = w.Write(body)
	}
}

func renderPage(w http.ResponseWriter, r *http.Request, cfg config, set string, p *pg) {
	var buf bytes.Buffer
	if err := pageSets[set].ExecuteTemplate(&buf, set+".tmpl", p); err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	pageFinish(w, r, cfg, buf.Bytes())
}

// headLinks is seo.head_links for an indexable path: the canonical URL takes
// ?lang= only when it is a public language; alternates are en, cs, x-default.
func (p *pg) headLinks(r *http.Request) {
	asked := supportedLanguage(r.URL.Query().Get("lang"))
	if asked != "en" && asked != "cs" {
		asked = ""
	}
	p.canonical = p.cfg.PublicBase + p.Path
	if asked != "" {
		p.canonical += "?lang=" + asked
	}
	for _, code := range []string{"en", "cs"} {
		p.Alternates = append(p.Alternates, link{code, p.URL(p.Path, code)})
	}
	p.Alternates = append(p.Alternates, link{"x-default", p.URL(p.Path, "")})
}

// ProductHandler is legal.product_details (GET /jak-to-funguje).
func ProductHandler(d Deps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cfg := loadConfig(d.Getenv)
		p := newPG("/jak-to-funguje", resolveLang(r, d.SignedIn), cfg)
		p.Active, p.SwitchPath = "how", "/jak-to-funguje"
		p.headLinks(r)
		renderPage(w, r, cfg, "product", p)
	}
}

// GuideHandler is legal.public_guide (GET /pruvodce/{slug}). Python indexes
// GUIDE_TRANSLATIONS by the route language, which raises KeyError (HTTP 500)
// for Vietnamese; Go serves the English guide instead. An unknown slug is
// 404 {"detail":"Not Found"} (the JSON body http_exception_handler writes;
// Python shows its branded error page to a browser).
func GuideHandler(d Deps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cfg := loadConfig(d.Getenv)
		slug := r.PathValue("slug")
		guideLang := routeLang(r)
		if guideLang != "cs" {
			guideLang = "en"
		}
		set := pcat.Guides[guideLang]
		guide, ok := set.Items[slug]
		if !ok {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			if r.Method != http.MethodHead {
				_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
			}
			return
		}
		path := "/pruvodce/" + slug
		p := newPG(path, resolveLang(r, d.SignedIn), cfg)
		p.Slug, p.Guide = slug, guide
		p.Active, p.SwitchPath = "", path
		if slug == "hlaseni-cizincu-ubyport" {
			p.Active = "guides"
		}
		for _, other := range set.Order {
			if other != slug {
				p.Guides = append(p.Guides, guideEntry{other, set.Items[other].Title})
			}
		}
		p.canonical = cfg.PublicBase + path
		if requested := supportedLanguage(r.URL.Query().Get("lang")); requested != "" {
			p.canonical += "?lang=" + requested
		}
		for _, code := range []string{"cs", "en"} {
			p.Alternates = append(p.Alternates, link{code, p.URL(path, code)})
		}
		p.Alternates = append(p.Alternates, link{"x-default", p.URL(path, "")})
		renderPage(w, r, cfg, "guide", p)
	}
}
