# 1271: Go public legal pages, part 2 (templates, handler, parity, route)

Status: review
Depends on: 1270 (same branch, its commit first) | Base commit: the 1270 commit | Branch: task/1270-go-public-legal-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 16 calls)

## 1. Objective

Finish the Go port of GET /legal, /terms, /privacy, /dpa and /subprocessors: the shell and page templates, the handler, the golden parity test against the 30 Python pages from 1270, and the route file. The routes exist in Go but stay off: Caddy sends nothing to them until the owner adds the paths to `UBYHOST_GO_PATHS`.

## 2. Context

Read [1270](1270-go-public-legal-pages.md) §2 only (gate, copy, golden pages, language, escaping); do not read its code blocks. Rules: 1, 2, 3, 4, 7 and 10 (screenshots, below), 8.

- `templates/*.tmpl` are `text/template` ports of `App/app/templates/public_legal_base.html`, `_public_header.html`, `_public_footer.html`, `_seo_head.html` (in `base.tmpl`), `_posthog.html`, `_legal_toc.html`, `_cookie_table.html` and the five page templates. The operator panel the four pages repeat is one `operator.tmpl`. `posthog.tmpl` is generated in step 4 from `_posthog.html` lines 6-92 so the script cannot drift.
- Every printed value goes through `T`, `TL`, `E`, `L`, `Effective`, `URL` or `Canonical` (markupsafe-equal escaping) or is one of the fixed fields `Lang`, `Path`, `WrapClass`, `PH*JS`; `TestEveryActionEscapes` fails on any other print.
- `Handler` sets what Python's middleware would set for these pages: `Content-Type: text/html; charset=utf-8`; the PostHog CSP (`main._public_csp`) only while PostHog is on (otherwise `wrap()`'s default CSP stays); the `ubyhost_lang` cookie when `?lang=` differs from the cookie (`templating.render` lines 795-797); `Cache-Control: public, max-age=0, s-maxage=300` when there is no query string and no session or language cookie (`main._apply_edge_cache`). Not ported, on purpose: the anonymous CSRF cookie (these pages have no form).
- A signed-in host with no language choice gets English. The route asks `session.Load` (read-only import) only when there is a session cookie and neither `?lang=` nor the cookie decides, so the pool is never touched while routes are built.
- `register_web_public.go` uses `registerRoutes` (`go/cmd/ubyhost-web/registry.go`); it never registers `GET /`.

Anchors (Phase 0; missing: STOP):

- `go/cmd/ubyhost-web/registry.go`: `func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {`
- `go/internal/session/session.go`: `CookieName = "ubyhost_session"` and `func Load(ctx context.Context, db *pgxpool.Pool, token string, now time.Time, getenv func(string) string) (*Host, error) {`
- `App/app/templates/_posthog.html` line 15: `  var apiKey = {{ analytics_tag.api_key | tojson }};`
- 1270 committed: `go/internal/web/public/testdata/cases.json` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/public/render.go` | new (copied) | templates, `Paths`, `Deps`, `Handler` |
| `go/internal/web/public/templates/base.tmpl`, `header.tmpl`, `footer.tmpl`, `operator.tmpl`, `toc.tmpl`, `cookie_table.tmpl`, `legal.tmpl`, `terms.tmpl`, `privacy.tmpl`, `dpa.tmpl`, `subprocessors.tmpl` | new (copied) | the pages |
| `go/internal/web/public/templates/posthog.tmpl` | new (generated, step 4) | from `_posthog.html` |
| `go/internal/web/public/golden_test.go` | new (copied) | parity, HEAD, escape guard |
| `go/internal/web/public/shots_test.go` | new (copied) | local server for screenshots; skipped in CI |
| `go/cmd/ubyhost-web/register_web_public.go` | new (copied) | the five routes |
| `docs/tasks/1271-go-public-legal-pages-render.md` | edit | `Status:` line only |
| `docs/tasks/1271-report.md` | new | your report |

No other file may change. Screenshots go to `/mnt/project-files/ux-shots/public-legal/` (outside the repo).

## 4. Steps

Work from the repo root `$(git rev-parse --show-toplevel)`.

### Phase 0: check (1 call)

1. Run:
```bash
git log --oneline -1; git status --short | head -3; grep -c 'func registerRoutes(fn func(\*http.ServeMux, \*metrics, \*pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go; grep -c 'CookieName = "ubyhost_session"\|func Load(ctx context.Context, db \*pgxpool.Pool, token string, now time.Time, getenv func(string) string) (\*Host, error) {' go/internal/session/session.go; sed -n 15p App/app/templates/_posthog.html; ls go/internal/web/public/testdata/cases.json
```
Expected: the `1270:` commit, clean tree, `1`, `2`, the `apiKey` line, the path. Else STOP.

### Phase 1: write the files (2 calls)

2. Copy the code blocks of this brief:
```bash
python3 - docs/tasks/1271-go-public-legal-pages-render.md <<'PYEOF'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
for path, body in re.findall(r"^<!-- file: (\S+) -->\n```\w*\n(.*?)\n```$", text, flags=re.S | re.M):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body + "\n", encoding="utf-8")
    print("wrote", path)
PYEOF
```
Expected: 15 `wrote` lines.
3. (Nothing to type here: step 4 makes the last template.)
4. Generate `posthog.tmpl`:
```bash
P=App/app/templates/_posthog.html; { printf '{{define "posthog"}}{{- if .PostHog -}}\n'; sed -n '6,92p' $P | sed -e 's/{{ analytics_tag.api_key | tojson }}/{{.PHKeyJS}}/' -e 's/{{ analytics_tag.api_host | tojson }}/{{.PHHostJS}}/' -e 's/{{ analytics_tag.assets_host | tojson }}/{{.PHAssetsJS}}/'; printf '{{- end -}}{{end}}\n'; } > go/internal/web/public/templates/posthog.tmpl; grep -c '{{' go/internal/web/public/templates/posthog.tmpl
```
Expected: `5`.

### Phase 2: Go tests (3 calls)

5. From `go/`: `gofmt -l internal/web/public cmd/ubyhost-web; go vet ./internal/web/public/ ./cmd/ubyhost-web/ 2>&1 | tail -5`. Expected: no output.
6. From `go/`: `go test ./internal/web/public/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -15`. Expected: two `ok` lines. A `TestGoldenPages/<case>` failure prints the first differing bytes: copy them into the report and STOP (do not edit templates to guess).
7. From `go/`: `go test ./internal/web/public/ -count=1 -v -run 'TestGoldenPages|TestEveryActionEscapes' 2>&1 | grep -c -- '--- PASS'`. Expected: `32`.

### Phase 3: screenshots, rules 7 and 10 (4 calls)

The browser and layout tests have nothing to run while the port is off, so the evidence is screenshots of the Go pages with the real CSS.

8. Start the local server in the background (it serves the five pages and `App/app/static`): from `go/`, `PUBLIC_LEGAL_SHOTS_ADDR=127.0.0.1:8765 go test -run TestServeForScreenshots -count=1 -timeout 0 ./internal/web/public/ > /tmp/shots-server.log 2>&1 &` then `sleep 8; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/terms`. Expected: `200`.
9. Write `/tmp/legal_shots.py` with exactly this content and run it from `App/`: `.venv/bin/python /tmp/legal_shots.py http://127.0.0.1:8765 /mnt/project-files/ux-shots/public-legal 2>&1 | tail -16`. Expected: 15 lines, each ending `ok` (a `horizontal-overflow` line is a finding: report it).
```python
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

base, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    for page_path in ("legal", "terms", "privacy", "dpa", "subprocessors"):
        for width in (390, 768, 1280):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{base}/{page_path}?lang=cs", wait_until="networkidle")
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            page.screenshot(path=str(out / f"{page_path}-{width}.png"), full_page=False)
            print(page_path, width, "horizontal-overflow" if overflow else "ok")
            page.close()
    browser.close()
```
10. Open the five `-390.png` files with Read and write one line per page in the report: what you saw (header, title, first panel; anything cut off or overlapping).
11. Stop the server: `pkill -f TestServeForScreenshots; echo stopped`.

### Phase 4: lint, commit, report (4 calls)

12. From the root: `python3 scripts/context_lint.py 2>&1 | tail -5`. Expected: no error line for 1270 or 1271.
13. Set this brief's `Status: todo` to `Status: review`. Write `docs/tasks/1271-report.md` (§9).
14. `git add go/internal/web/public go/cmd/ubyhost-web/register_web_public.go docs/tasks/1271-go-public-legal-pages-render.md docs/tasks/1271-report.md && git status --short | grep -v '^A ' | head -5`. Expected: no output.
15. Commit:
```bash
git commit -q -F - <<'MSG'
1271: Go public legal pages, templates, handler and route

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7RpUhVUPNtUsK4UDQG
MSG
git log --oneline -2
```
Do not push: the orchestrator pushes and opens the draft PR.

### The files

<!-- file: go/internal/web/public/render.go -->
```go
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
```

<!-- file: go/internal/web/public/templates/base.tmpl -->
```gotemplate
{{- /* public_legal_base.html: the shell of the five legal pages. */ -}}
<!doctype html>
<html lang="{{.Lang}}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f7f5">
  <title>{{template "title" .}}</title>
  <link rel="canonical" href="{{.Canonical}}">
  <link rel="alternate" hreflang="en" href="{{.URL "en"}}">
  <link rel="alternate" hreflang="cs" href="{{.URL "cs"}}">
  <link rel="alternate" hreflang="x-default" href="{{.URL ""}}">
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png?v=20261004a">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png?v=20261004a">
  <link rel="stylesheet" href="/static/tokens.css?v=20261022-0284">
  <link rel="stylesheet" href="/static/landing.css?v=20261109-1063a">
  <link rel="stylesheet" href="/static/app.css?v=20261104-0916">
  <link rel="stylesheet" href="/static/components.css?v=20261002a">
  {{template "posthog" .}}
</head>
<body class="layout-host no-nav">
{{template "header" .}}
<main id="content" class="wrap {{.WrapClass}}">
  {{template "content" .}}
</main>
{{template "footer" .}}
</body>
</html>
```

<!-- file: go/internal/web/public/templates/header.tmpl -->
```gotemplate
{{define "navlinks"}}
      <a href="/jak-to-funguje?lang={{.Lang}}">{{.T "landing.nav.how"}}</a>
      <a href="/cenik?lang={{.Lang}}">{{.T "landing.nav.pricing"}}</a>
      <a href="/pruvodce/hlaseni-cizincu-ubyport?lang={{.Lang}}">{{.T "landing.nav.guides"}}</a>
{{end}}
{{define "header"}}
  <a class="landing-skip" href="#content">{{.T "a11y.skip_to_content"}}</a>
  <header class="landing-header">
    <a class="landing-brand" href="/?lang={{.Lang}}" aria-label="UbyHost">
      <img src="/static/ubyhost-logo.png?v=20261004a" alt="UbyHost">
    </a>
    <nav class="landing-nav" aria-label="{{.T "a11y.main_navigation"}}">{{template "navlinks" .}}</nav>
    <div class="landing-actions">
      <nav class="landing-languages" aria-label="{{.T "lang.switch"}}">
        <a href="{{.Path}}?lang=cs" lang="cs" hreflang="cs" class="{{if eq .Lang "cs"}}active{{end}}"{{if eq .Lang "cs"}} aria-current="true"{{end}}>CZ</a>
        <a href="{{.Path}}?lang=en" lang="en" hreflang="en" class="{{if eq .Lang "en"}}active{{end}}"{{if eq .Lang "en"}} aria-current="true"{{end}}>EN</a>
      </nav>
      <a class="landing-login" href="/login?lang={{.Lang}}" data-analytics-event="login_click">{{.T "landing.nav.login"}}</a>
    </div>
    <details class="landing-menu">
      <summary>{{.T "landing.nav.menu"}}</summary>
      <nav aria-label="{{.T "a11y.main_navigation"}}">{{template "navlinks" .}}</nav>
    </details>
  </header>
{{end}}
```

<!-- file: go/internal/web/public/templates/footer.tmpl -->
```gotemplate
{{define "footer"}}
  <footer class="landing-footer">
    <a class="landing-brand" href="/?lang={{.Lang}}"><img src="/static/ubyhost-logo.png?v=20261004a" alt="UbyHost"></a>
    <nav aria-label="{{.T "legal.footer_nav_label"}}">
      <a href="/jak-to-funguje?lang={{.Lang}}">{{.T "landing.nav.how"}}</a>
      <a href="/cenik?lang={{.Lang}}">{{.T "landing.nav.pricing"}}</a>
      <a href="/pruvodce/hlaseni-cizincu-ubyport?lang={{.Lang}}">{{.T "landing.nav.guides"}}</a>
      <a href="/pruvodce/online-ubytovaci-kniha?lang={{.Lang}}">{{.T "landing.footer.guestbook"}}</a>
      <a href="/legal?lang={{.Lang}}">{{.T "legal.footer_short"}}</a>
      <a href="/terms?lang={{.Lang}}">{{.T "terms.footer_short"}}</a>
      <a href="/privacy?lang={{.Lang}}">{{.T "privacy.footer_short"}}</a>
      <a href="/dpa?lang={{.Lang}}">{{.T "dpa.footer_short"}}</a>
      <a href="/subprocessors?lang={{.Lang}}">{{.T "subprocessors.footer_short"}}</a>
      <a href="/login?lang={{.Lang}}" data-analytics-event="login_click">{{.T "landing.footer.login"}}</a>
    </nav>
    <a href="mailto:support@ubyhost.com" data-analytics-event="contact_click">support@ubyhost.com</a>
  </footer>
{{end}}
```

<!-- file: go/internal/web/public/templates/operator.tmpl -->
```gotemplate
{{define "operator"}}
<div class="panel legal-operator">
  <h2 style="margin-top:0">{{.T (printf "%s.operator_title" .Prefix)}}</h2>
  <dl class="kv">
    <dt>{{.T "legal.operator_name"}}</dt>
    <dd>{{.E .Op.Name}}</dd>
    <dt>IČO</dt>
    <dd class="mono">{{.E .Op.ICO}}</dd>
    {{if .Op.DIC}}
      <dt>DIČ</dt>
      <dd class="mono">{{.E .Op.DIC}}</dd>
    {{end}}
    <dt>{{.T "legal.operator_address"}}</dt>
    <dd>{{.E .Op.Address}}</dd>
    {{if and .Op.Email (ne .Prefix "terms")}}
      <dt>{{.T "legal.operator_contact"}}</dt>
      <dd><a href="mailto:{{.E .Op.Email}}" data-analytics-event="contact_click">{{.E .Op.Email}}</a></dd>
    {{end}}
    <dt>{{.T "legal.operator_registry"}}</dt>
    <dd><a href="{{.E .Op.Registry}}" rel="noopener noreferrer">{{.T "legal.registry_link"}}</a></dd>
  </dl>
</div>
{{end}}
```

<!-- file: go/internal/web/public/templates/toc.tmpl -->
```gotemplate
{{define "tocitems"}}<ol>
  {{- range .Sections}}
  <li><a href="#s{{$.E .}}">{{$.T (printf "%s.s%s_title" $.Prefix .)}}</a></li>
  {{- end}}
</ol>{{end}}
{{define "toc"}}
<div class="legal-toc" id="legal-contents">
  <nav class="legal-toc-wide" aria-label="{{.T "legal.toc"}}">
    <p class="legal-toc-title" aria-hidden="true">{{.T "legal.toc"}}</p>
    {{template "tocitems" .}}
  </nav>
  <details class="legal-toc-narrow">
    <summary>{{.T "legal.toc"}}</summary>
    <nav aria-label="{{.T "legal.toc"}}">{{template "tocitems" .}}</nav>
  </details>
</div>
{{end}}
{{define "sections"}}
{{range .Sections}}
<section class="legal-section" id="s{{$.E .}}">
  <h2>{{$.T (printf "%s.s%s_title" $.Prefix .)}}</h2>
  <div class="terms-section">{{$.TL (printf "%s.s%s_body" $.Prefix .) "name" $.Op.Name "ico" $.Op.ICO}}</div>
  <p class="legal-back"><a href="#legal-contents">{{$.T "legal.back_to_toc"}} <span aria-hidden="true">&uarr;</span></a></p>
</section>
{{end}}
{{end}}
```

<!-- file: go/internal/web/public/templates/cookie_table.tmpl -->
```gotemplate
{{define "cookietable"}}
<p class="small muted">{{.T "privacy.cookies.table_intro"}}</p>
<div class="scroll-x">
  <table class="table-cards">
    <thead>
      <tr>
        <th>{{.T "cookies.table.name"}}</th>
        <th>{{.T "cookies.table.party"}}</th>
        <th>{{.T "cookies.table.purpose"}}</th>
        <th>{{.T "cookies.table.lifetime"}}</th>
      </tr>
    </thead>
    <tbody>
    {{range .Cookies}}
      <tr>
        <td data-label="{{$.T "cookies.table.name"}}"><code>{{$.E .Name}}</code></td>
        <td data-label="{{$.T "cookies.table.party"}}">{{if eq .Party "first"}}{{$.T "cookies.party.first"}}{{else}}{{$.E .Party}}{{end}}</td>
        <td data-label="{{$.T "cookies.table.purpose"}}">{{$.L .Purpose}}</td>
        <td data-label="{{$.T "cookies.table.lifetime"}}">{{$.L .Lifetime}}</td>
      </tr>
    {{end}}
    </tbody>
  </table>
</div>
{{end}}
```

<!-- file: go/internal/web/public/templates/legal.tmpl -->
```gotemplate
{{define "title"}}{{.T "legal.page_title"}}{{end}}
{{define "content"}}
<header class="page-header">
  <div class="page-header-main">
    <h1>{{.T "legal.page_title"}}</h1>
    <p class="lede">{{.T "legal.page_lede"}}</p>
  </div>
</header>
{{template "operator" .}}
<div class="panel">
  <h2 style="margin-top:0">{{.T "legal.roles_title"}}</h2>
  <p class="small muted">{{.T "legal.roles_body"}}</p>
</div>
<div class="panel">
  <h2 style="margin-top:0">{{.T "legal.software_title"}}</h2>
  <p class="small muted">{{.T "legal.software_body"}}</p>
</div>
<div class="panel">
  <h2 style="margin-top:0">{{.T "legal.security_title"}}</h2>
  <p class="small muted">{{.T "legal.security_body"}}</p>
</div>
<div class="panel">
  <h2 style="margin-top:0">{{.T "legal.dpa_title"}}</h2>
  <p class="small muted">{{.TL "legal.dpa_body"}}</p>
  <p class="small" style="margin-bottom:0"><a href="/dpa">{{.T "dpa.footer_link"}} </a></p>
</div>
<div class="panel quiet">
  <h2 style="margin-top:0">{{.T "legal.disclaimer_title"}}</h2>
  <p class="small muted" style="margin-bottom:0">{{.T "legal.disclaimer_body"}}</p>
</div>
<p class="small muted">
  <a href="/terms">{{.T "legal.cross_terms"}}</a>
  &middot;
  <a href="/privacy">{{.T "legal.cross_privacy"}}</a>
  &middot;
  <a href="/dpa">{{.T "legal.cross_dpa"}}</a>
  &middot;
  <a href="/subprocessors">{{.T "subprocessors.footer_link"}}</a>
  &middot;
  <a href="/?lang={{.Lang}}">{{.T "legal.back_home"}}</a>
</p>
{{end}}
```

<!-- file: go/internal/web/public/templates/terms.tmpl -->
```gotemplate
{{define "title"}}{{.T "terms.page_title"}}{{end}}
{{define "content"}}
<header class="page-header">
  <div class="page-header-main">
    <h1>{{.T "terms.page_title"}}</h1>
    <p class="lede">{{.T "terms.page_lede"}}</p>
  </div>
</header>
<p class="small muted">{{.Effective "terms"}}</p>
{{template "toc" .}}
{{template "operator" .}}
{{template "sections" .}}
<div class="panel quiet">
  <h2 style="margin-top:0">{{.T "terms.review_title"}}</h2>
  <p class="small muted" style="margin-bottom:0">{{.T "terms.review_body"}}</p>
</div>
<p class="small muted">
  <a href="/legal">{{.T "terms.cross_legal"}}</a>
  &middot;
  <a href="/privacy">{{.T "terms.cross_privacy"}}</a>
  &middot;
  <a href="/dpa">{{.T "terms.cross_dpa"}}</a>
  &middot;
  <a href="/subprocessors">{{.T "subprocessors.footer_link"}}</a>
  &middot;
  <a href="/?lang={{.Lang}}">{{.T "legal.back_home"}}</a>
</p>
{{end}}
```

<!-- file: go/internal/web/public/templates/dpa.tmpl -->
```gotemplate
{{define "title"}}{{.T "dpa.page_title"}}{{end}}
{{define "content"}}
<header class="page-header">
  <div class="page-header-main">
    <h1>{{.T "dpa.page_title"}}</h1>
    <p class="lede">{{.T "dpa.page_lede" "name" .Op.Name}}</p>
  </div>
</header>
<p class="small muted">{{.Effective "dpa"}}</p>
{{template "toc" .}}
{{template "operator" .}}
<p class="small muted">{{.TL "dpa.incorporation_note"}}</p>
{{template "sections" .}}
<div class="panel quiet">
  <h2 style="margin-top:0">{{.T "dpa.review_title"}}</h2>
  <p class="small muted" style="margin-bottom:0">{{.T "dpa.review_body"}}</p>
</div>
<p class="small muted">
  <a href="/legal">{{.T "dpa.cross_legal"}}</a>
  &middot;
  <a href="/terms">{{.T "dpa.cross_terms"}}</a>
  &middot;
  <a href="/privacy">{{.T "dpa.cross_privacy"}}</a>
  &middot;
  <a href="/subprocessors">{{.T "subprocessors.footer_link"}}</a>
  &middot;
  <a href="/?lang={{.Lang}}">{{.T "legal.back_home"}}</a>
</p>
{{end}}
```

<!-- file: go/internal/web/public/templates/privacy.tmpl -->
```gotemplate
{{define "title"}}{{.T "privacy.page_title"}}{{end}}
{{define "content"}}
<header class="page-header">
  <div class="page-header-main">
    <h1>{{.T "privacy.page_title"}}</h1>
    <p class="lede">{{.T "privacy.page_lede" "name" .Op.Name}}</p>
  </div>
</header>
<p class="lede">{{.T "privacy_first.line"}}</p>
<p class="small muted">{{.Effective "privacy"}}</p>
{{template "toc" .}}
{{template "operator" .}}
<p class="small muted">{{.T "privacy.guest_note"}}</p>
{{range .Sections}}
<section class="legal-section" id="s{{$.E .}}">
  <h2>{{$.T (printf "privacy.s%s_title" .)}}</h2>
  <div class="terms-section">{{$.TL (printf "privacy.s%s_body" .) "name" $.Op.Name "ico" $.Op.ICO}}</div>
  {{if eq . "03"}}
    <h3>{{$.T "privacy.roles_title"}}</h3>
    <div class="terms-section">{{$.TL "privacy.roles_body" "name" $.Controller.Name "ico" $.Controller.ICO "address" $.Controller.Address}}</div>
  {{end}}
  {{if eq . "07"}}
    {{template "cookietable" $}}
    {{if $.PostHog}}
      <h3 id="analytics">{{$.T "privacy.analytics_title"}}</h3>
      <p>{{$.T "privacy.analytics_body"}}</p>
      <h3>{{$.T "privacy.product_analytics_title"}}</h3>
      <p>{{$.T "privacy.product_analytics_body"}}</p>
      <div class="panel quiet" id="analytics-optout" aria-live="polite">
        <p>{{$.T "privacy.optout_lede"}}</p>
        <p data-optout-when="on" style="margin-bottom:0"><a href="#analytics-optout" role="button" data-optout-action="disable">{{$.T "privacy.optout_disable"}}</a></p>
        <p data-optout-when="off" style="margin-bottom:0" hidden>{{$.T "privacy.optout_off_note"}} <a href="#analytics-optout" role="button" data-optout-action="enable">{{$.T "privacy.optout_enable"}}</a></p>
      </div>
      <script src="/static/analytics-optout.js?v=20261010a" defer></script>
      <p>{{$.T "privacy.analytics_dnt"}}</p>
      <ul class="small muted">
      {{range $.Cookieless}}
        <li><strong>{{$.E .Name}}</strong> ({{$.E .Party}}): {{$.L .Note}}</li>
      {{end}}
      </ul>
    {{end}}
    {{if $.SignupAdsNotice}}
    <h3 id="signup">{{$.T "privacy.signup_title"}}</h3>
    <div class="terms-section">{{$.T "privacy.signup_body"}}</div>
    <h3 id="signup-ads">{{$.T "privacy.signup_ads_title"}}</h3>
    <div class="terms-section">{{$.TL "privacy.signup_ads_body"}}</div>
    {{if $.SignupMetaNotice}}
    <h3 id="signup-meta">{{$.T "privacy.signup_meta_title"}}</h3>
    <div class="terms-section">{{$.TL "privacy.signup_meta_body"}}</div>
    {{end}}
    <h3 id="signup-recipients">{{$.T "privacy.signup_recipients_title"}}</h3>
    <div class="terms-section">{{$.TL "privacy.signup_recipients_body"}}{{if $.SignupMetaNotice}} {{$.T "privacy.signup_recipients_meta"}}{{end}}</div>
    {{end}}
  {{end}}
  {{if eq . "11"}}
    <h3>{{$.T "privacy.own_retention_title"}}</h3>
    <p>{{$.T "privacy.own_retention_body"}}</p>
  {{end}}
  <p class="legal-back"><a href="#legal-contents">{{$.T "legal.back_to_toc"}} <span aria-hidden="true">&uarr;</span></a></p>
</section>
{{end}}
<div class="panel quiet">
  <h2 style="margin-top:0">{{.T "privacy.review_title"}}</h2>
  <p class="small muted" style="margin-bottom:0">{{.T "privacy.review_body"}}</p>
</div>
<p class="small muted">
  <a href="/legal">{{.T "privacy.cross_legal"}}</a>
  &middot;
  <a href="/terms">{{.T "privacy.cross_terms"}}</a>
  &middot;
  <a href="/dpa">{{.T "privacy.cross_dpa"}}</a>
  &middot;
  <a href="/subprocessors">{{.T "subprocessors.footer_link"}}</a>
  &middot;
  <a href="/?lang={{.Lang}}">{{.T "legal.back_home"}}</a>
</p>
{{end}}
```

<!-- file: go/internal/web/public/templates/subprocessors.tmpl -->
```gotemplate
{{define "title"}}{{.T "subprocessors.page_title"}}{{end}}
{{define "content"}}
<header class="page-header">
  <div class="page-header-main">
    <h1>{{.T "subprocessors.page_title"}}</h1>
    <p class="lede">{{.T "subprocessors.page_lede"}}</p>
  </div>
</header>
<p class="small muted">{{.T "subprocessors.effective"}}</p>
<div class="panel">
  <h2 style="margin-top:0">{{.T "subprocessors.controller_note_title"}}</h2>
  <p class="small muted">{{.T "subprocessors.controller_note"}}</p>
</div>
<div class="panel">
  <h2 style="margin-top:0">{{.T "subprocessors.scope_title"}}</h2>
  <p class="small muted">{{.T "subprocessors.scope_body"}}</p>
  <div class="scroll-x">
    <table class="table-cards">
      <thead>
        <tr>
          <th>{{.T "subprocessors.table_provider"}}</th>
          <th>{{.T "subprocessors.table_purpose"}}</th>
          <th>{{.T "subprocessors.table_data"}}</th>
          <th>{{.T "subprocessors.table_location"}}</th>
          <th>{{.T "subprocessors.table_safeguard"}}</th>
        </tr>
      </thead>
      <tbody>
      {{range .SubprocessorIDs}}
        <tr>
          <td data-label="{{$.T "subprocessors.table_provider"}}"><strong>{{$.T (printf "subprocessors.%s_provider" .)}}</strong></td>
          <td data-label="{{$.T "subprocessors.table_purpose"}}">{{$.T (printf "subprocessors.%s_purpose" .)}}</td>
          <td data-label="{{$.T "subprocessors.table_data"}}">{{$.T (printf "subprocessors.%s_data" .)}}</td>
          <td data-label="{{$.T "subprocessors.table_location"}}">{{$.T (printf "subprocessors.%s_location" .)}}</td>
          <td data-label="{{$.T "subprocessors.table_safeguard"}}">{{$.T (printf "subprocessors.%s_safeguard" .)}}</td>
        </tr>
      {{end}}
      </tbody>
    </table>
  </div>
</div>
<div class="panel" id="recipients">
  <h2 style="margin-top:0">{{.T "subprocessors.recipients_title"}}</h2>
  <ul class="small muted">
  {{range .RecipientIDs}}
    <li>{{$.T (printf "subprocessors.recipient_%s" .)}}</li>
  {{end}}
  </ul>
</div>
<div class="panel">
  <h2 style="margin-top:0">{{.T "subprocessors.change_title"}}</h2>
  <p class="small muted">{{.T "subprocessors.change_body"}}</p>
</div>
<div class="panel quiet">
  <h2 style="margin-top:0">{{.T "subprocessors.accuracy_title"}}</h2>
  <p class="small muted" style="margin-bottom:0">{{.T "subprocessors.accuracy_body"}}</p>
</div>
<p class="small muted">
  <a href="/legal">{{.T "legal.footer_short"}}</a>
  &middot; <a href="/terms">{{.T "terms.footer_short"}}</a>
  &middot; <a href="/privacy">{{.T "privacy.footer_short"}}</a>
  &middot; <a href="/dpa">{{.T "dpa.footer_short"}}</a>
  &middot; <a href="/?lang={{.Lang}}">{{.T "legal.back_home"}}</a>
</p>
{{end}}
```

<!-- file: go/internal/web/public/golden_test.go -->
```go
package public

import (
	"encoding/json"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"text/template/parse"
)

// goldenCase is one entry of testdata/cases.json (App/scripts/public_legal_golden.py).
type goldenCase struct {
	Name     string            `json:"name"`
	Path     string            `json:"path"`
	Query    string            `json:"query"`
	Cookies  map[string]string `json:"cookies"`
	Env      map[string]string `json:"env"`
	Expected struct {
		Status      int            `json:"status"`
		ContentType string         `json:"content_type"`
		CacheCtl    string         `json:"cache_control"`
		CSP         string         `json:"csp"`
		SetCookies  []goldenCookie `json:"set_cookies"`
	} `json:"expected"`
}

type goldenCookie struct {
	Name     string `json:"name"`
	Value    string `json:"value"`
	Path     string `json:"path"`
	MaxAge   string `json:"max_age"`
	SameSite string `json:"samesite"`
	Secure   bool   `json:"secure"`
	HTTPOnly bool   `json:"httponly"`
}

var space = regexp.MustCompile(`[ \t\n\r\f\v]+`)

// normalize is public_legal_golden.normalize: ASCII whitespace runs become
// one space, "> <" becomes "><", ends trimmed.
func normalize(s string) string {
	return strings.TrimSpace(strings.ReplaceAll(space.ReplaceAllString(s, " "), "> <", "><"))
}

// defaultHeaders stands in for main.go's wrap(), which sets these before the handler.
func serve(t *testing.T, c goldenCase) *httptest.ResponseRecorder {
	t.Helper()
	url := c.Path
	if c.Query != "" {
		url += "?" + c.Query
	}
	req := httptest.NewRequest(http.MethodGet, url, nil)
	for k, v := range c.Cookies {
		req.AddCookie(&http.Cookie{Name: k, Value: v})
	}
	rec := httptest.NewRecorder()
	rec.Header().Set("Cache-Control", "no-store, private")
	rec.Header().Set("Content-Security-Policy", wrapCSP)
	getenv := func(k string) string { return c.Env[k] }
	Handler(c.Path, Deps{Getenv: getenv})(rec, req)
	return rec
}

// wrapCSP is the Content-Security-Policy main.go's hardenHeaders sets.
const wrapCSP = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com"

func TestGoldenPages(t *testing.T) {
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 30 {
		t.Fatalf("only %d golden cases", len(cases))
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			rec := serve(t, c)
			want, err := os.ReadFile(filepath.Join("testdata", c.Name+".html"))
			if err != nil {
				t.Fatal(err)
			}
			got := normalize(rec.Body.String()) + "\n"
			if got != string(want) {
				t.Errorf("html differs at byte %d:\n got: %s\nwant: %s", firstDiff(got, string(want)),
					around(got, firstDiff(got, string(want))), around(string(want), firstDiff(got, string(want))))
			}
			e := c.Expected
			if rec.Code != e.Status {
				t.Errorf("status %d, want %d", rec.Code, e.Status)
			}
			h := rec.Header()
			if h.Get("Content-Type") != e.ContentType || h.Get("Cache-Control") != e.CacheCtl || h.Get("Content-Security-Policy") != e.CSP {
				t.Errorf("headers %q %q %q, want %q %q %q", h.Get("Content-Type"), h.Get("Cache-Control"),
					h.Get("Content-Security-Policy"), e.ContentType, e.CacheCtl, e.CSP)
			}
			var cookies []goldenCookie
			for _, line := range h.Values("Set-Cookie") {
				ck, err := http.ParseSetCookie(line)
				if err != nil {
					t.Fatal(err)
				}
				ss := map[http.SameSite]string{http.SameSiteLaxMode: "lax", http.SameSiteStrictMode: "strict"}[ck.SameSite]
				cookies = append(cookies, goldenCookie{ck.Name, ck.Value, ck.Path, itoa(ck.MaxAge), ss, ck.Secure, ck.HttpOnly})
			}
			gotC, _ := json.Marshal(cookies)
			wantC, _ := json.Marshal(e.SetCookies)
			if len(cookies) == 0 && len(e.SetCookies) == 0 {
				return
			}
			if string(gotC) != string(wantC) {
				t.Errorf("set-cookie %s, want %s", gotC, wantC)
			}
		})
	}
}

func itoa(n int) string {
	b, _ := json.Marshal(n)
	return string(b)
}

func firstDiff(a, b string) int {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return i
		}
	}
	return min(len(a), len(b))
}

func around(s string, i int) string {
	lo, hi := max(0, i-80), min(len(s), i+80)
	return s[lo:hi]
}

func TestHeadHasNoBody(t *testing.T) {
	req := httptest.NewRequest(http.MethodHead, "/legal", nil)
	rec := httptest.NewRecorder()
	Handler("/legal", Deps{Getenv: func(string) string { return "" }})(rec, req)
	if rec.Code != http.StatusOK || rec.Body.Len() != 0 {
		t.Fatalf("HEAD: %d with %d bytes", rec.Code, rec.Body.Len())
	}
}

// allowedPrints are the only things a template may print: the escaping
// methods, and fields that hold no outside text (Lang is "en" or "cs", Path
// is one of Paths, WrapClass is "narrow", the PH*JS fields are tojson output).
var allowedPrints = map[string]bool{
	"T": true, "TL": true, "E": true, "L": true, "Effective": true, "URL": true, "Canonical": true,
	"Lang": true, "Path": true, "WrapClass": true, "PHKeyJS": true, "PHHostJS": true, "PHAssetsJS": true,
}

func TestEveryActionEscapes(t *testing.T) {
	files, _ := fs.Glob(templateFS, "templates/*.tmpl")
	for _, file := range files {
		src, _ := fs.ReadFile(templateFS, file)
		trees, err := parse.Parse(file, string(src), "{{", "}}", map[string]any{"printf": true, "eq": true, "ne": true, "and": true})
		if err != nil {
			t.Fatal(err)
		}
		for _, tree := range trees {
			walk(t, file, tree.Root)
		}
	}
}

func walk(t *testing.T, file string, n parse.Node) {
	switch n := n.(type) {
	case *parse.ListNode:
		if n == nil {
			return
		}
		for _, c := range n.Nodes {
			walk(t, file, c)
		}
	case *parse.ActionNode:
		if len(n.Pipe.Decl) > 0 {
			return
		}
		cmd := n.Pipe.Cmds[len(n.Pipe.Cmds)-1]
		name := ""
		switch a := cmd.Args[0].(type) {
		case *parse.FieldNode:
			name = a.Ident[len(a.Ident)-1]
		case *parse.VariableNode:
			if len(a.Ident) > 1 {
				name = a.Ident[len(a.Ident)-1]
			}
		}
		if !allowedPrints[name] {
			t.Errorf("%s: %s prints without escaping", file, n)
		}
	case *parse.IfNode:
		walk(t, file, n.List)
		walk(t, file, n.ElseList)
	case *parse.RangeNode:
		walk(t, file, n.List)
		walk(t, file, n.ElseList)
	case *parse.WithNode:
		walk(t, file, n.List)
		walk(t, file, n.ElseList)
	}
}
```

<!-- file: go/internal/web/public/shots_test.go -->
```go
package public

import (
	"net/http"
	"os"
	"testing"
)

// TestServeForScreenshots serves the five pages and App/app/static on
// PUBLIC_LEGAL_SHOTS_ADDR until the process is stopped, for the rule 7/10
// screenshots (brief 1270 phase 5). Skipped when the variable is unset.
func TestServeForScreenshots(t *testing.T) {
	addr := os.Getenv("PUBLIC_LEGAL_SHOTS_ADDR")
	if addr == "" {
		t.Skip("PUBLIC_LEGAL_SHOTS_ADDR not set")
	}
	env := map[string]string{
		"UBYHOST_PUBLIC_BASE_URL": "http://" + addr, "UBYHOST_OPERATOR_NAME": "Demo Operator s.r.o.",
		"UBYHOST_OPERATOR_ICO": "12345678", "UBYHOST_OPERATOR_ADDRESS": "Václavské náměstí 1, 110 00 Praha 1",
		"UBYHOST_OPERATOR_REGISTRY_URL": "https://or.justice.cz/ias/ui/rejstrik",
	}
	deps := Deps{Getenv: func(k string) string { return env[k] }}
	mux := http.NewServeMux()
	for _, path := range Paths {
		mux.Handle("GET "+path, Handler(path, deps))
	}
	mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.Dir("../../../../App/app/static"))))
	t.Fatal(http.ListenAndServe(addr, mux))
}
```

<!-- file: go/cmd/ubyhost-web/register_web_public.go -->
```go
package main

// Brief 1270: the public legal pages (go/internal/web/public). Caddy sends a
// path here only when it is listed in UBYHOST_GO_PATHS; until then Python
// serves them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		deps := public.Deps{Getenv: os.Getenv, SignedIn: func(r *http.Request) bool {
			// templating.render: a signed-in host without a language choice
			// gets English. Asked only at request time, never while building.
			c, err := r.Cookie(session.CookieName)
			if err != nil || c.Value == "" || pool == nil {
				return false
			}
			h, err := session.Load(r.Context(), pool, c.Value, time.Now(), os.Getenv)
			return err == nil && h != nil
		}}
		for _, path := range public.Paths {
			mux.Handle("GET "+path, m.wrap(path, public.Handler(path, deps)))
		}
	})
}
```

## 5. Do not touch

Everything in 1270 §5, plus every 1270 file (`public.go`, `page.go`, `unit_test.go`, `catalog.json`, `testdata/`, the golden script and its test), `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, and `go/internal/hostweb/` (another thread builds `hostweb/layout` in draft PR #985: do not use or touch it). Never register `GET /`.

## 6. Commands

Steps 5-12 with their expected output. Tests: `go test ./internal/web/public/ ./cmd/ubyhost-web/` only. Never the full suite.

## 7. Acceptance

- [ ] `git diff --stat HEAD~1` lists only §3 paths.
- [ ] Step 6: two `ok`; step 7: `32`.
- [ ] 15 PNGs in `/mnt/project-files/ux-shots/public-legal/`, all `ok`; one line per page in the report.
- [ ] Step 12: no 1270/1271 error.

## 8. Stop and ask

Stop, and write the report as `blocked`, if: an anchor is missing; the copy prints other than 15 `wrote` lines; a golden case fails (report the diff lines, change nothing); a test fails twice; a file outside §3 changes; 25 tool calls or about 50k tokens; you would need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1271-report.md`, 600 tokens at most: files changed, each command of steps 5-12 with its last 3 lines, the five page lines from step 10, §7 ticked, deviations, questions, and these lines for the coordinator (copy them):

- ENVIRONMENT.md, `UBYHOST_GO_PATHS` row: "the public legal pages can move with `/legal /terms /privacy /dpa /subprocessors` (brief 1271)".
- test-map.md, new row: "Go public legal pages (`go/internal/web/public`) | `go test ./internal/web/public/` and `tests/test_go_public_legal.py`; after a legal copy change run `scripts/public_legal_golden.py` and commit".
- known-issues.md: "Go legal pages do not set the anonymous CSRF cookie (no form on them); a signed-in host is detected with `session.Load`, without Python's no-login staging shortcut."

## Risk list (for the reviewer)

`go/internal/web/public/render.go` (`Handler` headers and cookie, `edgeCacheable`), `templates/privacy.tmpl` and `templates/base.tmpl`, `golden_test.go` (`normalize` equals the Python one), `go/cmd/ubyhost-web/register_web_public.go` (pool used only per request).

## Owner steps

After the PR is green and merged (merge with `scripts/merge-pr-on-green.sh`), the pages still come from Python. To switch them to Go later:

1. On the server, open the `.env` next to `docker-compose.yml` and add the five paths to the existing `UBYHOST_GO_PATHS` value, inside its double quotes: `/legal /terms /privacy /dpa /subprocessors`.
2. Check the Caddy config:
```bash
deploy/lightsail/scripts/caddy-validate.sh
```
3. Restart Caddy:
```bash
docker compose up -d caddy
```
4. Open `https://<your domain>/terms?lang=en` and `/privacy`: the pages look as before.
5. Rollback: remove the five paths from `UBYHOST_GO_PATHS`, then repeat steps 2 and 3.
