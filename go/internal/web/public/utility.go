package public

import (
	"context"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth/authpage"
)

const (
	pwaIconKey    = "20261021-0203"
	privateCache  = "no-store, private"
	manifestCache = "public, max-age=86400"
	swCache       = "no-cache"
)

// manifestJSON matches json.dumps(_MANIFEST) from App/app/main.py (brief 0219).
const manifestJSON = `{"id": "/", "name": "UbyHost", "short_name": "UbyHost", "description": "Guest registration and police reports for short-term rentals.", "lang": "en", "start_url": "/login", "scope": "/", "display": "standalone", "background_color": "#f7f7f5", "theme_color": "#f7f7f5", "icons": [{"src": "/static/icons/icon-192.png?v=` + pwaIconKey + `", "sizes": "192x192", "type": "image/png", "purpose": "any"}, {"src": "/static/icons/icon-512.png?v=` + pwaIconKey + `", "sizes": "512x512", "type": "image/png", "purpose": "any"}, {"src": "/static/icons/icon-maskable-512.png?v=` + pwaIconKey + `", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}`

var offlineStrings = map[string]map[string]string{
	"en": {
		"title": "You are offline",
		"body":  "UbyHost needs an internet connection. Check Wi-Fi or mobile data, then try again.",
		"retry": "Try again",
	},
	"cs": {
		"title": "Jste offline",
		"body":  "UbyHost potřebuje připojení k internetu. Zkontrolujte Wi-Fi nebo mobilní data a zkuste to znovu.",
		"retry": "Zkusit znovu",
	},
	"vi": {
		"title": "Bạn đang ngoại tuyến",
		"body":  "UbyHost cần kết nối Internet. Hãy kiểm tra Wi-Fi hoặc dữ liệu di động, rồi thử lại.",
		"retry": "Thử lại",
	},
}

// DepsUtility holds env lookup and optional database for sitemap property pages.
type DepsUtility struct {
	Getenv func(string) string
	Pool   *pgxpool.Pool
	Now    func() time.Time
}

// Register mounts main.py utility routes (brief 1750).
func RegisterUtility(mux *http.ServeMux, d DepsUtility, wrap func(string, http.HandlerFunc) http.Handler) {
	mux.Handle("GET /robots.txt", wrap("/robots.txt", robotsHandler(d)))
	mux.Handle("GET /.well-known/tdmrep.json", wrap("/.well-known/tdmrep.json", tdmrepHandler(d)))
	mux.Handle("GET /manifest.webmanifest", wrap("/manifest.webmanifest", manifestHandler(d)))
	mux.Handle("GET /sw.js", wrap("/sw.js", swHandler(d)))
	mux.Handle("GET /offline", wrap("/offline", offlineHandler(d)))
	mux.Handle("GET /sitemap.xml", wrap("/sitemap.xml", sitemapHandler(d)))
	mux.Handle("POST /language", wrap("/language", languageHandler(d)))
	mux.Handle("GET /favicon.ico", wrap("/favicon.ico", faviconHandler(d)))
}

func robotsHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("Content-Type", "text/plain; charset=utf-8")
		h.Set("Cache-Control", edgeCacheControl)
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write([]byte(RobotsTXT(d.Getenv)))
		}
	}
}

func tdmrepHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("Content-Type", "application/json")
		h.Set("Cache-Control", privateCache)
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write([]byte(TDMRepJSON))
		}
	}
}

func manifestHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("Content-Type", "application/manifest+json")
		h.Set("Cache-Control", manifestCache)
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write([]byte(manifestJSON))
		}
	}
}

func swHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		body, err := readServiceWorker(d.Getenv)
		if err != nil {
			http.Error(w, "Not Found", http.StatusNotFound)
			return
		}
		h := w.Header()
		h.Set("Content-Type", "text/javascript; charset=utf-8")
		h.Set("Cache-Control", swCache)
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write(body)
		}
	}
}

func offlineHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		lang := resolveOfflineLang(r)
		if asked := supportedLanguage(r.URL.Query().Get("lang")); asked != "" && hostweb.Cookie(r, langCookieName) != asked {
			http.SetCookie(w, authpage.LanguageCookie(asked, d.Getenv))
		}
		strs := offlineStrings[lang]
		if strs == nil {
			strs = offlineStrings["en"]
		}
		body := renderOfflineHTML(lang, strs)
		h := w.Header()
		h.Set("Content-Type", "text/html; charset=utf-8")
		h.Set("Cache-Control", privateCache)
		h.Set("Content-Language", lang)
		h.Set("X-Robots-Tag", "noindex")
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write(body)
		}
	}
}

func resolveOfflineLang(r *http.Request) string {
	if lang := supportedLanguage(r.URL.Query().Get("lang")); lang != "" {
		return lang
	}
	if lang := supportedLanguage(hostweb.Cookie(r, langCookieName)); lang != "" {
		return lang
	}
	return "cs"
}

func renderOfflineHTML(lang string, s map[string]string) []byte {
	// Normalized HTML from offline.html (no template comments in output).
	html := strings.Join([]string{
		"<!doctype html>",
		"<html lang=\"" + lang + "\">",
		"<head>",
		"  <meta charset=\"utf-8\">",
		"  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">",
		"  <meta name=\"theme-color\" content=\"#f7f7f5\">",
		"  <meta name=\"robots\" content=\"noindex\">",
		"  <title>" + s["title"] + " · UbyHost</title>",
		"  ",
		"  <style>",
		"    html { background: #f7f7f5; color: #20201e; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; }",
		"    body { margin: 0; min-height: 100vh; display: grid; place-items: center; box-sizing: border-box; padding: max(24px, env(safe-area-inset-top)) 24px max(24px, env(safe-area-inset-bottom)); }",
		"    main { max-width: 26rem; text-align: center; }",
		"    h1 { font-size: 1.375rem; line-height: 1.3; margin: 0 0 12px; }",
		"    p { margin: 0 0 24px; line-height: 1.5; color: #50504c; }",
		"    a { display: inline-block; min-height: 44px; box-sizing: border-box; padding: 11px 20px; border-radius: 8px; background: #ad4942; color: #ffffff; font-weight: 600; text-decoration: none; }",
		"    a:focus-visible { outline: 3px solid #20201e; outline-offset: 2px; }",
		"  </style>",
		"</head>",
		"<body>",
		"  <main>",
		"    <h1>" + s["title"] + "</h1>",
		"    <p>" + s["body"] + "</p>",
		"    ",
		"    <a href=\"\">" + s["retry"] + "</a>",
		"  </main>",
		"</body>",
		"</html>",
	}, "\n")
	return []byte(html)
}

func sitemapHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		rows := loadPublishedPages(r.Context(), d.Pool)
		h := w.Header()
		h.Set("Content-Type", "application/xml")
		h.Set("Cache-Control", edgeCacheControl)
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write([]byte(SitemapXML(d.Getenv, rows)))
		}
	}
}

func loadPublishedPages(ctx context.Context, pool *pgxpool.Pool) []publishedRow {
	if pool == nil {
		return nil
	}
	const q = `SELECT ps.slug, pp.published_at
		FROM property_slug ps
		JOIN property_page pp ON pp.apartment_id = ps.apartment_id
		WHERE ps.published = 1 AND COALESCE(pp.hide_from_search, 0) = 0
		ORDER BY ps.slug`
	qr, err := pool.Query(ctx, q)
	if err != nil {
		return nil
	}
	defer qr.Close()
	var out []publishedRow
	for qr.Next() {
		var slug string
		var publishedAt *string
		if err := qr.Scan(&slug, &publishedAt); err != nil {
			continue
		}
		out = append(out, publishedRow{Slug: slug, PublishedAt: publishedAt})
	}
	return out
}

func languageHandler(d DepsUtility) http.HandlerFunc {
	now := d.Now
	if now == nil {
		now = time.Now
	}
	return func(w http.ResponseWriter, r *http.Request) {
		if !hostweb.CSRF(w, r, d.Getenv, now()) {
			return
		}
		if err := r.ParseForm(); err != nil {
			http.Error(w, "Bad Request", http.StatusBadRequest)
			return
		}
		lang := normaliseLanguage(r.FormValue("lang"))
		target := ai.HavelSafeLocalPath(r.FormValue("next"), "/")
		http.SetCookie(w, authpage.LanguageCookie(lang, d.Getenv))
		h := w.Header()
		h.Set("Cache-Control", privateCache)
		http.Redirect(w, r, target, http.StatusSeeOther)
	}
}

func faviconHandler(d DepsUtility) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("Cache-Control", privateCache)
		http.Redirect(w, r, "/static/favicon.png", http.StatusTemporaryRedirect)
	}
}

func readServiceWorker(getenv func(string) string) ([]byte, error) {
	if root := strings.TrimSpace(getenv("UBYHOST_APP_ROOT")); root != "" {
		p := filepath.Join(root, "static", "sw.js")
		if b, err := os.ReadFile(p); err == nil {
			return b, nil
		}
	}
	for _, rel := range []string{
		"../../../App/app/static/sw.js",
		"../../../../App/app/static/sw.js",
		"App/app/static/sw.js",
	} {
		if b, err := os.ReadFile(rel); err == nil {
			return b, nil
		}
	}
	return nil, os.ErrNotExist
}

// normaliseLanguage is host_i18n.normalise_language.
func normaliseLanguage(v string) string {
	lang := strings.ToLower(strings.TrimSpace(v))
	if len(lang) > 2 {
		lang = lang[:2]
	}
	if lang == "en" || lang == "cs" || lang == "vi" {
		return lang
	}
	return hostweb.DefaultLanguage
}
