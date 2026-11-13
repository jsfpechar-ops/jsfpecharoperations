# 1361: Go customer admin pages part 1 of 2: customer list page, parity golden, query nits

Status: review
Depends on: 1363, 1380 (both on this branch) | Base commit: 4e3dc5e | Branch: go-customer-admin-pages (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (admin pages; no filing, no guest data)

## 1. Objective

Port `GET /admin/customers` (`customer_list` in `App/app/routes/admin_customers.py`, template `admin_customers.html`) to Go, rendered with the host layout `go/internal/hostweb/layout`, and prove it shows the same text, links and form fields as Python. Also fix two review nits of the package: checked int conversions in `query.go` instead of bare `.(int64)` assertions, and a test that the audit `at` value matches `db.utcnow`.

## 2. Context

- Split: 1361 (this: list page, shared page code, golden) then 1364 (detail page `GET /admin/customers/{user_id}`), one executor session each, same branch, one draft PR (#975). `GET /admin` (admin home) is a later brief 1365: it needs ports of `billing_analytics.operator_queue`/`portfolio`, `admin_ops.overview` (six health queries) and `incidents.open_review_alerts`, too big for these two.
- Every new file is given in full. Create it byte for byte from its block in §4 (everything between the `~~~~` fence lines, ending with one newline) and check its sha256. Different: compare with the block once, fix, check again; still different: STOP (§8). Existing files change only through the `git apply` patch in step 4. Generated files are written only by their script, never by hand.
- Layout API (read-only, brief 1380): `layout.MustParse(catalog, fs, "templates/*.tmpl")` once; per request `layout.Render(w, r, layout.Env{Pool, Getenv, Now}, host, layout.Page{...}, pages, "admin_customers", view)`. The template defines `admin_customers` (body) and the slots `.head`, `.title` (h1), `.tabs`, `.secondary`, `.toolbar`. Go templates cannot build lists, so `pages.go` builds the tab, option, stat, column and row lists that Jinja builds inline, translating with the page's own catalog in the signed-in language `hostweb.Lang(r)` (what the layout uses for a signed-in host). `ui_section_tabs()` is not ported in the layout: `adminTabs` is `_template_section_tabs(request, "admin", ...)` passed to `ui_tabs`.
- Strings: the page catalog lives in `go/internal/web/customers/templates/` (`i18n_keys.txt` + generated `i18n.json`), so the existing `go/internal/web/customers/i18n.json` (checked by `TestCatalogMatchesPython`) stays as it is. `App/scripts/go_host_i18n.py` finds it through its `**/i18n_keys.txt` glob; `App/tests/test_go_host_i18n.py` keeps it current.
- "today" is the date in `config.TIMEZONE` (Europe/Prague), as in `deadlines`, `posthog` and `layout`. Links are built like Python `urlencode({**values, **extra})` (`url.QueryEscape` = `quote_plus`).
- Parity (plan `docs/plans/go-full-move.md` §3 Lane W: content, not bytes): `App/scripts/go_customers_pages_golden.py` seeds SQLite with the seed of `App/scripts/admin_customers_golden.py` (imported, not changed), signs in as the admin, freezes the route clock at 2026-11-13 12:00 UTC and renders 9 list cases (en/cs/vi, billing on/off, filters, cursors, empty). It stores `visible_lines()` of `div.ui-page` (shell, toasts and alerts excluded): each text run, and each tag with one of id, href, action, method, name, value, type, selected, checked, required, for, aria-current (CSRF values masked). `pages_test.go` seeds Postgres from the existing golden JSON, renders the Go page with the same inputs and compares with the same normaliser (`visibleLines`, kept in step by hand; `TestVisibleLines` pins it).
- Guard: the package's `requireAdmin`. Forms keep posting to their Python paths (`/admin/users`, the GET filter form to `/admin/customers`). The area stays off: no Caddy, env, `UBYHOST_GO_PATHS` or `docs/ENVIRONMENT.md` change. Rules: 4 (no new dependency: stdlib + pgx), 5 (SQL Postgres-portable; no new SQL here), 8 (never push to `main`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/templates/i18n_keys.txt` | create | the page keys |
| `go/internal/web/customers/templates/i18n.json` | create (generated) | by `go_host_i18n.py` |
| `go/internal/web/customers/templates/admin_customers.tmpl` | create | Go twin of `admin_customers.html` |
| `go/internal/web/customers/pages.go` | create | catalog, Prague day, tabs, `listHref`, `ListHandler` |
| `go/internal/web/customers/query.go` | edit (patch) | `asInt64`; no bare type assertions |
| `go/cmd/ubyhost-web/register_web_customers.go` | edit (patch) | registers `GET /admin/customers` |
| `App/scripts/go_customers_pages_golden.py` | create | page golden writer, `--check` |
| `go/internal/web/customers/testdata/customers_pages_golden.json` | create (generated) | by the script above |
| `App/tests/test_go_customers_pages_golden.py` | create | stale check |
| `go/internal/web/customers/pages_test.go` | create | normaliser, parity, guard and stamp tests |
| `docs/tasks/1361-go-customer-admin-pages.md` | edit | `Status:` line only |
| `docs/tasks/1361-report.md` | create | your report |

No other file may change.

## 4. Steps

Commit after each step with the message `1361 step k`. Run every command from the repo root unless it says otherwise.

### Step 1: start Postgres (no commit)

```bash
PGBIN=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1360 && chown postgres /var/tmp/pg1360
[ -f /var/tmp/pg1360/data/PG_VERSION ] || su postgres -c "$PGBIN/initdb -D /var/tmp/pg1360/data -A trust -U postgres" | tail -3
$PGBIN/pg_isready -h 127.0.0.1 -p 55436 || { rm -f /var/tmp/pg1360/data/postmaster.pid /var/tmp/pg1360/.s.PGSQL.55436 /var/tmp/pg1360/.s.PGSQL.55436.lock; su postgres -c "$PGBIN/pg_ctl -D /var/tmp/pg1360/data -l /var/tmp/pg1360/log -o '-p 55436 -k /var/tmp/pg1360 -c listen_addresses=127.0.0.1' -w start" 2>&1 | tail -3; }
$PGBIN/pg_isready -h 127.0.0.1 -p 55436
```

Expected last line: `127.0.0.1:55436 - accepting connections`.

### Step 2: page strings

Create `go/internal/web/customers/templates/i18n_keys.txt`:

~~~~text
# Host strings the customer admin pages (pages.go, templates/*.tmpl) read, one key per line.
# Generated catalog: python3 App/scripts/go_host_i18n.py (brief 1361).
admin.tab.money
admin.tab.system
admin.tab.today
common.actions
common.open
customers.all
customers.apply
customers.as_of
customers.billing_off
customers.customer
customers.empty
customers.ending
customers.meta
customers.month
customers.newer
customers.not_ordered
customers.not_recorded
customers.older
customers.overview
customers.payments
customers.period
customers.plan
customers.properties
customers.reset
customers.search
customers.state
customers.state.legacy
customers.state.unverified
customers.state.disabled
customers.state.trial_pending
customers.state.trialing
customers.state.active
customers.state.overdue
customers.state.canceling
customers.state.paused
customers.title
customers.year
users.create.lede
users.create.name
users.create.submit
users.create.title
users.email.create_hint
users.email.label
users.email.missing_banner
~~~~

Check: `sha256sum go/internal/web/customers/templates/i18n_keys.txt 2>&1 | tail -30` must print `b5498dea32e54f854edce94ab38b1588ac69200ad297c10915fe8ae84a1cdaed`.

Then from `App/`: `.venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -30` prints one line `wrote .../go/internal/web/customers/templates/i18n.json` (venv missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt`).
Check: `sha256sum go/internal/web/customers/templates/i18n.json 2>&1 | tail -30` must print `d070622638d7c64d6fb62e408f39008c8e84b569911a371a8be83070cd64a1ca`. Commit `1361 step 2`.

### Step 3: template and handler

Create `go/internal/web/customers/templates/admin_customers.tmpl`:

~~~~gotemplate
{{- /* Go twin of App/app/templates/admin_customers.html (brief 1361). pages.go builds
     the lists (tabs, options, stats, columns, rows) that Jinja builds inline. */ -}}
{{define "admin_customers.head"}}<link rel="stylesheet" href="/static/admin2.css?v=20261106-0893q"><link rel="stylesheet" href="/static/admin2-operator-0974.css?v=20261105-0974a">{{end}}
{{define "admin_customers.title"}}{{tip_label (t "customers.title") "admin-customers-help" (t "customers.meta") (kv "tag" "span")}}{{end}}
{{define "admin_customers.tabs"}}{{ui_tabs .Tabs}}{{end}}
{{define "admin_customers.secondary"}}{{ui_button (t "customers.payments") "secondary" (kv "href" "/admin/fakturace")}}{{end}}
{{define "admin_customers.toolbar"}}
<form method="get" action="/admin/customers" class="ui-section">
  <div class="ui-pair">
    {{ui_field "customer-search" (t "customers.search") (kv "name" "q" "value" .Q "type" "search" "attrs" (safe `maxlength="120" enterkeyhint="search"`))}}
    {{ui_select "customer-state" (t "customers.state") .StateOptions (kv "selected" .State "name" "state")}}
  </div>
  <div class="ui-pair">
    {{ui_select "customer-plan" (t "customers.plan") .PlanOptions (kv "selected" .Plan "name" "plan")}}
    <div class="ui-form-actions">{{ui_button (t "customers.apply") "primary" (kv "type" "submit")}}</div>
  </div>
</form>
{{end}}
{{define "admin_customers"}}
{{if .MissingEmail}}
<div class="ui-section" role="status" id="users-missing-email">
  <p class="ui-sub"><strong>{{t "users.email.missing_banner" "count" .MissingEmail}}</strong></p>
</div>
{{end}}
{{if not .BillingOn}}{{ui_banner "neutral" (t "customers.billing_off")}}{{end}}
<div class="customers-metrics">{{ui_stats .Stats (t "customers.overview")}}</div>
<p class="ui-sub">{{t "customers.as_of" "date" .Today}}</p>
{{if .Rows}}
{{ui_table_begin .Columns (t "customers.title")}}
{{range .Rows}}
<tr class="ui-row" data-customer-id="{{.ID}}">
  <td class="ui-cell-first" data-card="primary"><a data-turbo="false" href="/admin/customers/{{.ID}}">{{.Name}}</a></td>
  <td class="ui-cell-r" data-card="meta">{{.Props}}</td>
  <td data-card="secondary">{{.Plan}}{{if .Email}}<span class="ui-sub">{{.Email}}</span>{{end}}</td>
  <td data-card="badge">{{ui_badge .BadgeKind .StateLabel}}</td>
  <td data-card="meta">{{.Period}}</td>
  <td class="ui-cell-acts" data-card="actions">{{ui_button (t "common.open") "secondary" (kv "href" (printf "/admin/customers/%d" .ID) "size" "compact")}}</td>
</tr>
{{end}}
{{ui_table_end}}
{{else}}{{ui_empty (t "customers.empty") ""}}{{end}}
<nav class="ui-form-actions" aria-label="{{t "customers.title"}}">
{{if .NewerURL}}{{ui_button (t "customers.newer") "secondary" (kv "href" .NewerURL)}}{{end}}
{{if .OlderURL}}{{ui_button (t "customers.older") "secondary" (kv "href" .OlderURL)}}{{end}}
{{if or .NewerURL .OlderURL}}{{ui_button (t "customers.reset") "quiet" (kv "href" .ResetURL)}}{{end}}
</nav>

<section class="ui-section" id="create-host">
  <h2>{{tip_label (t "users.create.title") "create-host-help" (t "users.create.lede") (kv "tag" "span")}}</h2>
  <form method="post" action="/admin/users">
    <div class="ui-field">
      <label for="display_name">{{t "users.create.name"}}</label>
      <input type="text" id="display_name" name="display_name" autocomplete="off">
    </div>
    <div class="ui-field">
      <label for="email">{{t "users.email.label"}}</label>
      <input type="email" id="email" name="email" required maxlength="254" autocomplete="off"
             autocapitalize="none" spellcheck="false">
      <div class="ui-help">{{t "users.email.create_hint"}}</div>
    </div>
    <div class="ui-form-actions"><button class="ui-btn ui-btn-primary" type="submit">{{t "users.create.submit"}}</button></div>
  </form>
</section>
{{end}}
~~~~

Check: `sha256sum go/internal/web/customers/templates/admin_customers.tmpl 2>&1 | tail -30` must print `7566ec3efdf50bf2769fce107753e0755f2c136ce382e001f0e706086e283fdb`.

Create `go/internal/web/customers/pages.go`:

~~~~go
package customers

// The customer admin GET pages, rendered with the Go host layout: the port of
// customer_list in App/app/routes/admin_customers.py with its template
// admin_customers.html. Briefs 1361 (list) and 1364 (detail). Only the
// aktivovat POST is served by Go; every other form posts to Python.

import (
	"embed"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // Prague must exist on a bare container

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/i18n.json
var pagesJSON []byte

//go:embed templates/*.tmpl
var templateFS embed.FS

// pageCatalog holds the strings the pages read, generated from
// templates/i18n_keys.txt by App/scripts/go_host_i18n.py.
var pageCatalog = hostweb.Load(pagesJSON)

var pages = layout.MustParse(pageCatalog, templateFS, "templates/*.tmpl")

// prague is config.TIMEZONE: "today" on the pages is the date there.
var prague = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("customers: Prague zone missing: " + err.Error())
	}
	return loc
}()

// pragueDay is datetime.now(ZoneInfo(config.TIMEZONE)).date(), as a UTC midnight.
func pragueDay(at time.Time) time.Time {
	y, m, d := at.In(prague).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// tr is t() for lists the handler builds: a signed-in host's language is
// hostweb.Lang, as the layout resolves it.
type tr string

func (lang tr) t(key string, pairs ...any) string {
	var p map[string]any
	if len(pairs) > 0 {
		p = map[string]any{}
		for i := 0; i+1 < len(pairs); i += 2 {
			p[fmt.Sprint(pairs[i])] = pairs[i+1]
		}
	}
	return pageCatalog.T(string(lang), key, p)
}

// adminTabs is ui_section_tabs() on an /admin page: templating
// _template_section_tabs(request, "admin", current).
func adminTabs(lang tr, current string) [][]any {
	items := [][3]string{
		{"today", "/admin", "admin.tab.today"},
		{"customers", "/admin/customers", "customers.title"},
		{"money", "/admin/fakturace", "admin.tab.money"},
		{"system", "/admin/operations", "admin.tab.system"},
	}
	out := make([][]any, len(items))
	for i, it := range items {
		out[i] = []any{it[1], lang.t(it[2]), it[0] == current}
	}
	return out
}

// billingOn is billing.enabled() (config.BILLING_ENABLED).
func billingOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// lastQuery is a FastAPI str query parameter: the last value, "" when missing.
func lastQuery(r *http.Request, key string) string {
	vals := r.URL.Query()[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}

// listHref is customer_list's href(**extra): PAGE + "?" +
// urlencode({**values, **extra}); extra keys q, state and plan keep their place.
func listHref(v Filters, extra ...string) string {
	pairs := [][2]string{{"q", v.Q}, {"state", v.State}, {"plan", v.Plan}}
	for i := 0; i+1 < len(extra); i += 2 {
		found := false
		for j := range pairs {
			if pairs[j][0] == extra[i] {
				pairs[j][1], found = extra[i+1], true
			}
		}
		if !found {
			pairs = append(pairs, [2]string{extra[i], extra[i+1]})
		}
	}
	parts := make([]string, len(pairs))
	for i, p := range pairs {
		parts[i] = url.QueryEscape(p[0]) + "=" + url.QueryEscape(p[1])
	}
	return page + "?" + strings.Join(parts, "&")
}

// text is a column value as the template prints it with "or ”": nil is "".
func text(row map[string]any, key string) string {
	switch v := row[key].(type) {
	case nil:
		return ""
	case string:
		return v
	default:
		return fmt.Sprint(v)
	}
}

// planName is the plan cell: 'UbyHost Max', 'UbyHost' or customers.not_ordered.
func planName(lang tr, plan string) string {
	switch plan {
	case "max":
		return "UbyHost Max"
	case "standard":
		return "UbyHost"
	}
	return lang.t("customers.not_ordered")
}

// period is t('customers.' ~ billing_interval) or customers.not_recorded.
func period(lang tr, interval string) string {
	if interval == "" {
		return lang.t("customers.not_recorded")
	}
	return lang.t("customers." + interval)
}

type listRow struct {
	ID                                                      int64
	Name, Props, Plan, Email, BadgeKind, StateLabel, Period string
}

type listView struct {
	Q, State, Plan               string
	Tabs, StateOptions           [][]any
	PlanOptions, Stats           [][]any
	Columns                      [][]any
	Rows                         []listRow
	MissingEmail                 int64
	BillingOn                    bool
	Today                        string
	OlderURL, NewerURL, ResetURL string
}

// ListHandler serves GET /admin/customers (customer_list).
func ListHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		ctx := r.Context()
		day := pragueDay(at)
		v := NewFilters(lastQuery(r, "q"), lastQuery(r, "state"), lastQuery(r, "plan"))
		res, err := Customers(ctx, pool, v, Cursor(lastQuery(r, "after")), Cursor(lastQuery(r, "before")), day)
		if err != nil {
			serverError(w, err)
			return
		}
		summary, err := Summary(ctx, pool, day)
		if err != nil {
			serverError(w, err)
			return
		}
		missing, err := MissingEmailCount(ctx, pool)
		if err != nil {
			serverError(w, err)
			return
		}
		lang := tr(hostweb.Lang(r))
		view := listView{
			Q: v.Q, State: v.State, Plan: v.Plan,
			Tabs:         adminTabs(lang, "customers"),
			StateOptions: [][]any{{"", lang.t("customers.all")}, {"ending", lang.t("customers.ending")}},
			PlanOptions:  [][]any{{"", lang.t("customers.all")}, {"standard", "UbyHost"}, {"max", "UbyHost Max"}},
			Columns: [][]any{{lang.t("customers.customer"), ""}, {lang.t("customers.properties"), "r"},
				{lang.t("customers.plan"), ""}, {lang.t("customers.state"), ""},
				{lang.t("customers.period"), ""}, {lang.t("common.actions"), ""}},
			MissingEmail: missing,
			BillingOn:    billingOn(getenv),
			Today:        day.Format("2006-01-02"),
			ResetURL:     listHref(v),
		}
		for _, s := range States {
			view.StateOptions = append(view.StateOptions, []any{s, lang.t("customers.state." + s)})
		}
		for _, s := range []string{"legacy", "unverified", "trialing", "ending", "active", "overdue"} {
			label := lang.t("customers.state." + s)
			if s == "ending" {
				label = lang.t("customers.ending")
			}
			view.Stats = append(view.Stats, []any{listHref(v, "state", s, "q", "", "plan", ""), summary[s], label})
		}
		for _, c := range res.Customers {
			id, err := asInt64(c["id"], "id")
			if err != nil {
				serverError(w, err)
				return
			}
			props, err := asInt64(c["active_properties"], "active_properties")
			if err != nil {
				serverError(w, err)
				return
			}
			state := text(c, "customer_state")
			row := listRow{ID: id, Name: text(c, "display_name"), Props: strconv.FormatInt(props, 10),
				Plan: planName(lang, text(c, "plan")), Email: text(c, "email"), BadgeKind: "neutral",
				StateLabel: lang.t("customers.state." + state), Period: period(lang, text(c, "billing_interval"))}
			if row.Name == "" {
				row.Name = text(c, "username")
			}
			if state == "overdue" || state == "unverified" {
				row.BadgeKind = "action"
			}
			view.Rows = append(view.Rows, row)
		}
		if n := len(view.Rows); n > 0 {
			if res.Older {
				view.OlderURL = listHref(v, "after", strconv.FormatInt(view.Rows[n-1].ID, 10))
			}
			if res.Newer {
				view.NewerURL = listHref(v, "before", strconv.FormatInt(view.Rows[0].ID, 10))
			}
		}
		p := layout.Page{Title: lang.t("customers.title"), Nav: "users", BodyKind: "list", V2: true, AdminWorkspace: true}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, p, pages, "admin_customers", view); err != nil {
			serverError(w, err)
		}
	}
}
~~~~

Check: `sha256sum go/internal/web/customers/pages.go 2>&1 | tail -30` must print `8ca114b0efbed20834bca69bd65a24d70bf2a4b1971882447c94251ae6566f30`.

Run from `go/`: `/usr/local/go/bin/go build ./internal/web/... 2>&1 | tail -30` (no output). Commit `1361 step 3`.

### Step 4: query nits and route (patch)

From the repo root, write the patch below to `/tmp/1361.patch` exactly (keep the tabs and the leading space of each context line), then run `git apply --check /tmp/1361.patch && git apply /tmp/1361.patch && git status --short 2>&1 | tail -30`. If `--check` fails: STOP (§8).

~~~~diff
diff --git a/go/cmd/ubyhost-web/register_web_customers.go b/go/cmd/ubyhost-web/register_web_customers.go
index f955d16..4729f7b 100644
--- a/go/cmd/ubyhost-web/register_web_customers.go
+++ b/go/cmd/ubyhost-web/register_web_customers.go
@@ -1,8 +1,8 @@
 package main
 
-// Web thread "customer admin" owns this file. Only the routes that need no
-// host layout are registered; the customer list and detail pages come later.
-// The port stays off until a path is routed to Go.
+// Web thread "customer admin" owns this file: the customer list page (brief
+// 1361), the funnel redirect and the account toggle. The port stays off until
+// a path is routed to Go.
 
 import (
 	"net/http"
@@ -16,6 +16,7 @@ import (
 
 func init() {
 	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
+		mux.Handle("GET /admin/customers", m.wrap("/admin/customers", customers.ListHandler(pool, os.Getenv, time.Now)))
 		mux.Handle("GET /admin/funnel", m.wrap("/admin/funnel", customers.FunnelHandler(pool, os.Getenv, time.Now)))
 		mux.Handle("POST /admin/customers/{user_id}/aktivovat", m.wrap("/admin/customers/{user_id}/aktivovat", customers.ToggleActiveHandler(pool, os.Getenv, time.Now)))
 	})
diff --git a/go/internal/web/customers/query.go b/go/internal/web/customers/query.go
index c2047d0..dd17271 100644
--- a/go/internal/web/customers/query.go
+++ b/go/internal/web/customers/query.go
@@ -9,6 +9,7 @@ package customers
 import (
 	"context"
 	"errors"
+	"fmt"
 	"strconv"
 	"strings"
 	"time"
@@ -180,6 +181,15 @@ func rowMaps(rows pgx.Rows) ([]map[string]any, error) {
 	return out, rows.Err()
 }
 
+// asInt64 reads a bigint column value. Any other type is an error, not a panic.
+func asInt64(v any, column string) (int64, error) {
+	n, ok := v.(int64)
+	if !ok {
+		return 0, fmt.Errorf("customers: column %s is %T, want int64", column, v)
+	}
+	return n, nil
+}
+
 func queryMaps(ctx context.Context, pool *pgxpool.Pool, sql string, args ...any) ([]map[string]any, error) {
 	rows, err := pool.Query(ctx, sql, args...)
 	if err != nil {
@@ -221,7 +231,9 @@ func Customers(ctx context.Context, pool *pgxpool.Pool, v Filters, after, before
 	if len(rows) > 0 {
 		ids := make([]int64, len(rows))
 		for i, r := range rows {
-			ids[i] = r["id"].(int64)
+			if ids[i], err = asInt64(r["id"], "id"); err != nil {
+				return Page{}, err
+			}
 		}
 		counted, err := queryMaps(ctx, pool,
 			"SELECT owner_user_id, COUNT(*) AS n FROM apartment "+
@@ -231,10 +243,16 @@ func Customers(ctx context.Context, pool *pgxpool.Pool, v Filters, after, before
 		}
 		counts := map[int64]int64{}
 		for _, c := range counted {
-			counts[c["owner_user_id"].(int64)] = c["n"].(int64)
+			owner, err := asInt64(c["owner_user_id"], "owner_user_id")
+			if err != nil {
+				return Page{}, err
+			}
+			if counts[owner], err = asInt64(c["n"], "n"); err != nil {
+				return Page{}, err
+			}
 		}
-		for _, r := range rows {
-			r["active_properties"] = counts[r["id"].(int64)]
+		for i, r := range rows {
+			r["active_properties"] = counts[ids[i]]
 		}
 	}
 	has := len(rows) > 0
@@ -254,7 +272,13 @@ func Summary(ctx context.Context, pool *pgxpool.Pool, today time.Time) (map[stri
 	}
 	counts := map[string]int64{}
 	for _, r := range rows {
-		counts[r["customer_state"].(string)] = r["n"].(int64)
+		state, ok := r["customer_state"].(string)
+		if !ok {
+			return nil, fmt.Errorf("customers: column customer_state is %T, want string", r["customer_state"])
+		}
+		if counts[state], err = asInt64(r["n"], "n"); err != nil {
+			return nil, err
+		}
 	}
 	clause, args := where(NewFilters("", "ending", ""), today)
 	var n int64
~~~~

Check: `sha256sum go/internal/web/customers/query.go 2>&1 | tail -30` must print `ef2a2dd3709121412be7aa3efa1620672c879bfc0397dacf63c924a80acc7697`.
Check: `sha256sum go/cmd/ubyhost-web/register_web_customers.go 2>&1 | tail -30` must print `f567c86b153bcb2684218b15cbc2df444bb7874bc7c0cee3fc21deea085a147f`.

Run from `go/`: `/usr/local/go/bin/go vet ./internal/web/... ./cmd/... 2>&1 | tail -30` (no output). Commit `1361 step 4`.

### Step 5: Python golden

Create `App/scripts/go_customers_pages_golden.py`:

~~~~python
"""Write go/internal/web/customers/testdata/customers_pages_golden.json from the real Python pages.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_customers_pages_golden.py          write the file
    .venv/bin/python scripts/go_customers_pages_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the seed of admin_customers_golden.py
(the Go tests seed PostgreSQL from that script's JSON), signs in as the admin
through TestClient with the route clock frozen at NOW, and renders each page
case. A case keeps visible_lines() of the page: the visible text and the key
attributes of the page area (div.ui-page), not the bytes. pages_test.go renders
the Go pages and compares with the same normaliser. The "utcnow" section is
db.utcnow() at a fixed instant, for the audit "at" format.
App/tests/test_go_customers_pages_golden.py fails when this file is stale.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "customers" / "testdata" / "customers_pages_golden.json"

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
STAMP_AT = datetime(2026, 11, 13, 12, 0, 7, 654321, tzinfo=timezone.utc)

# name, language, billing on, path. Seed: 45 hosts (ids 2-16, 101-130), page size 25.
CASES = [
    ("list first page", "en", True, "/admin/customers"),
    ("list in Czech, billing off", "cs", False, "/admin/customers"),
    ("list older page", "en", True, "/admin/customers?after=110"),
    ("list newer page", "en", True, "/admin/customers?before=105"),
    ("list ending", "en", True, "/admin/customers?state=ending"),
    ("list search special characters", "en", True, "/admin/customers?q=anna_100%25&plan=standard"),
    ("list max active in Vietnamese", "vi", True, "/admin/customers?plan=max&state=active&q=Bulk"),
    ("list empty, non-ASCII search", "en", True, "/admin/customers?q=%C5%BDlu%C5%A5+%26+co"),
    ("list bad cursor, repeated q", "en", True, "/admin/customers?after=abc&q=x&q=+Nov+"),
]

# visible_lines: keep in step with visibleLines in go/internal/web/customers/pages_test.go.
DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "selected", "checked",
        "required", "for", "aria-current"}


def visible_lines(page: str) -> list[str]:
    """The page area as lines: each text run, and each tag that has a KEPT attribute."""
    start = page.find('<div class="ui-page"')
    if start < 0:
        return []
    page = page[start:]
    end = page.find('<div class="page-skeleton"')
    if end >= 0:
        page = page[:end]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    skip = False  # inside the header back link: Python shows an icon, Go a label (gap)
    for tok in TOKEN.findall(page):
        if not tok.startswith("<"):
            text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
            if text and not skip:
                out.append(text)
            continue
        m = TAG.match(tok)
        if not m:
            continue
        name = m.group(2).lower()
        if m.group(1) == "/":
            if name == "a":
                skip = False
            continue
        attrs = {}
        for a in ATTR.finditer(tok[m.end():]):
            key = a.group(1).lower()
            has_value = "=" in a.group(0)
            value = html.unescape((a.group(2) or "") + (a.group(3) or "") + (a.group(4) or ""))
            attrs[key] = (has_value, value)
        if "ui-ph-back" in attrs.get("class", (False, ""))[1].split():
            skip = True
        if attrs.get("name", (False, ""))[1] == "_csrf":
            attrs["value"] = (True, "*")
        parts = [k + ("=" + v if has else "") for k, (has, v) in sorted(attrs.items()) if k in KEPT]
        if parts:
            out.append("<" + name + " " + " ".join(parts) + ">")
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


class _FrozenStamp(datetime):
    @classmethod
    def now(cls, tz=None):
        return STAMP_AT if tz is None else STAMP_AT.astimezone(tz)


def render() -> str:
    from fastapi.testclient import TestClient

    import admin_customers_golden as base
    from app import acceptance, config, db, login_link
    from app.main import app
    from app.routes import admin_customers as routes

    db.init_db()
    versions = acceptance.current_versions()
    for table in base._seed():
        for row in table["rows"]:
            if table["table"] == "legal_acceptance":
                row["version"] = versions[row["document"]]
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row.values()))

    def csrf(client) -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    def admin_client(lang):
        client = TestClient(app)
        client.cookies.set("ubyhost_lang", lang)
        account = db.query_one("SELECT * FROM user_account WHERE username = ?", ("admin",))
        response = client.post("/login/link", data={"t": login_link.issue(account), "_csrf": csrf(client)},
                               follow_redirects=False)
        assert response.status_code == 303 and "/login" not in response.headers["location"]
        return client

    clients = {lang: admin_client(lang) for lang in ("en", "cs", "vi")}
    routes.datetime = _Frozen
    cases = []
    for name, lang, billing_on, path in CASES:
        config.BILLING_ENABLED = billing_on
        response = clients[lang].get(path, follow_redirects=False)
        cases.append({"name": name, "lang": lang, "billing": billing_on, "path": path,
                      "status": response.status_code, "lines": visible_lines(response.text)})
    real = db.datetime
    db.datetime = _FrozenStamp
    try:
        stamp = db.utcnow()
    finally:
        db.datetime = real
    golden = {"utcnow": {"at": STAMP_AT.isoformat(), "stamp": stamp}, "cases": cases}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_customers_pages_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "customers_pages_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
~~~~

Check: `sha256sum App/scripts/go_customers_pages_golden.py 2>&1 | tail -30` must print `740061f302743793ab5520f03b90cdb5f3c05539b1bfaf55b03ee35858a9c5e4`.

Create `App/tests/test_go_customers_pages_golden.py`:

~~~~python
"""go/internal/web/customers/pages_test.go reads go/internal/web/customers/testdata/customers_pages_golden.json.

The generator runs in a child process with no UBYHOST_* variables, so it uses
its own throwaway SQLite database and never the test session's database.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "customers" / "testdata" / "customers_pages_golden.json"


def test_go_customers_pages_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_customers_pages_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(golden["cases"]) >= 9
    assert all(len(case["lines"]) > 50 for case in golden["cases"] if case["status"] == 200)
~~~~

Check: `sha256sum App/tests/test_go_customers_pages_golden.py 2>&1 | tail -30` must print `2db4d1dd08005a05ef24264966bfa4f1c4cfe86d3e84dbdb0eee8fbd80ca1b91`.

From `App/`: `env -u UBYHOST_TEST_DATABASE_URL .venv/bin/python scripts/go_customers_pages_golden.py 2>&1 | tail -1` prints `wrote .../customers_pages_golden.json`. Run it a second time; then `git status --short 2>&1 | tail -30` shows the JSON as one untracked file and nothing modified by the second run.
Check: `sha256sum go/internal/web/customers/testdata/customers_pages_golden.json 2>&1 | tail -30` must print `33b2b9d02f05365fe51824bd3324019543e330c981ac6f44075ad20eb28c7f2a`. Commit `1361 step 5`.

### Step 6: Go tests

Create `go/internal/web/customers/pages_test.go`:

~~~~go
package customers

import (
	"encoding/json"
	"html"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"
)

// pagesGolden is what App/scripts/go_customers_pages_golden.py wrote from the
// real Python pages.
type pagesGolden struct {
	UTCNow struct {
		At    string `json:"at"`
		Stamp string `json:"stamp"`
	} `json:"utcnow"`
	Cases []struct {
		Name    string   `json:"name"`
		Lang    string   `json:"lang"`
		Billing bool     `json:"billing"`
		Path    string   `json:"path"`
		Status  int      `json:"status"`
		Lines   []string `json:"lines"`
	} `json:"cases"`
}

func loadPagesGolden(t *testing.T) pagesGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/customers_pages_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g pagesGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 9 {
		t.Fatal("pages golden file is too small")
	}
	return g
}

// visibleLines is visible_lines in App/scripts/go_customers_pages_golden.py;
// keep the two in step.
var (
	dropRes = []*regexp.Regexp{regexp.MustCompile(`(?s)<!--.*?-->`), regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`), regexp.MustCompile(`(?is)<svg\b.*?</svg>`)}
	tokenRe = regexp.MustCompile(`<[^>]*>|[^<]+`)
	tagRe   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	attrRe  = regexp.MustCompile(`([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?`)
	spaceRe = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	kept    = map[string]bool{"id": true, "href": true, "action": true, "method": true, "name": true, "value": true,
		"type": true, "selected": true, "checked": true, "required": true, "for": true, "aria-current": true}
)

type attrVal struct {
	has   bool
	value string
}

func visibleLines(page string) []string {
	start := strings.Index(page, `<div class="ui-page"`)
	if start < 0 {
		return []string{}
	}
	page = page[start:]
	if end := strings.Index(page, `<div class="page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	for _, re := range dropRes {
		page = re.ReplaceAllString(page, "")
	}
	out := []string{}
	skip := false
	for _, tok := range tokenRe.FindAllString(page, -1) {
		if !strings.HasPrefix(tok, "<") {
			text := strings.Trim(spaceRe.ReplaceAllString(html.UnescapeString(tok), " "), " ")
			if text != "" && !skip {
				out = append(out, text)
			}
			continue
		}
		m := tagRe.FindStringSubmatchIndex(tok)
		if m == nil {
			continue
		}
		name := strings.ToLower(tok[m[4]:m[5]])
		if tok[m[2]:m[3]] == "/" {
			if name == "a" {
				skip = false
			}
			continue
		}
		attrs := map[string]attrVal{}
		for _, a := range attrRe.FindAllStringSubmatch(tok[m[1]:], -1) {
			attrs[strings.ToLower(a[1])] = attrVal{strings.Contains(a[0], "="), html.UnescapeString(a[2] + a[3] + a[4])}
		}
		for _, c := range strings.Fields(attrs["class"].value) {
			if c == "ui-ph-back" {
				skip = true
			}
		}
		if attrs["name"].value == "_csrf" {
			attrs["value"] = attrVal{true, "*"}
		}
		keys := make([]string, 0, len(attrs))
		for k := range attrs {
			if kept[k] {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		parts := make([]string, len(keys))
		for i, k := range keys {
			parts[i] = k
			if attrs[k].has {
				parts[i] += "=" + attrs[k].value
			}
		}
		if len(parts) > 0 {
			out = append(out, "<"+name+" "+strings.Join(parts, " ")+">")
		}
	}
	return out
}

func TestVisibleLines(t *testing.T) {
	page := `<p>x</p><div class="ui-page"><!-- c --><a class="ui-ph-back x" href="/b?a=1&amp;b=2"><span>Back</span></a>` +
		`<h1>T&#39;s  <b>bold</b></h1><input type="hidden" name="_csrf" value="tok"><input required name=q>` +
		`<svg><path d="M0"/></svg><select data-x="1"><option selected value="">All</option></select></div>` +
		`<div class="page-skeleton">skip</div>`
	want := []string{"<a href=/b?a=1&b=2>", "T's", "bold", "<input name=_csrf type=hidden value=*>",
		"<input name=q required>", "<option selected value=>", "All"}
	if got := visibleLines(page); strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Fatalf("got %q", got)
	}
}

// pagesMux routes the GET pages the way register_web_customers.go does.
func pagesMux(t *testing.T, g goldenFile, billing bool) *http.ServeMux {
	t.Helper()
	pool := dbPool(t)
	seed(t, pool, g)
	base := testGetenv(g.Versions)
	getenv := func(k string) string {
		if k == "UBYHOST_BILLING_ENABLED" {
			if billing {
				return "1"
			}
			return "0"
		}
		return base(k)
	}
	now := func() time.Time { return testNow }
	mux := http.NewServeMux()
	mux.Handle("GET /admin/customers", ListHandler(pool, getenv, now))
	return mux
}

// TestPagesMatchPython renders each golden case with the Go handler and
// compares the visible lines with the ones Python rendered.
func TestPagesMatchPython(t *testing.T) {
	g := loadGolden(t)
	pg := loadPagesGolden(t)
	muxes := map[bool]*http.ServeMux{true: pagesMux(t, g, true), false: pagesMux(t, g, false)}
	for _, c := range pg.Cases {
		rec := serve(t, muxes[c.Billing], call{method: "GET", path: c.Path, lang: c.Lang,
			payload: map[string]any{"uid": 1, "sv": 1}})
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, Python %d", c.Name, rec.Code, c.Status)
			continue
		}
		got := visibleLines(rec.Body.String())
		for i := 0; i < len(got) || i < len(c.Lines); i++ {
			var g, w string
			if i < len(got) {
				g = got[i]
			}
			if i < len(c.Lines) {
				w = c.Lines[i]
			}
			if g != w {
				t.Errorf("%s: line %d is %q, Python %q", c.Name, i, g, w)
				break
			}
		}
	}
}

// TestPagesNeedAdmin: a signed-out visitor goes to the login page and a host
// gets the 403 text, as _require_admin answers.
func TestPagesNeedAdmin(t *testing.T) {
	g := loadGolden(t)
	mux := pagesMux(t, g, true)
	rec := serve(t, mux, call{method: "GET", path: "/admin/customers", lang: "en"})
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Fatalf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = serve(t, mux, call{method: "GET", path: "/admin/customers", lang: "en",
		payload: map[string]any{"uid": 7, "sv": 1}})
	if rec.Code != http.StatusForbidden || rec.Body.String() != "Administrators only." {
		t.Fatalf("host: %d %q", rec.Code, rec.Body.String())
	}
}

// TestStampMatchesUTCNow: the audit "at" value has db.utcnow's format.
func TestStampMatchesUTCNow(t *testing.T) {
	pg := loadPagesGolden(t)
	at, err := time.Parse(time.RFC3339Nano, pg.UTCNow.At)
	if err != nil {
		t.Fatal(err)
	}
	if got := stamp(at.In(prague)); got != pg.UTCNow.Stamp {
		t.Fatalf("stamp %q, db.utcnow %q", got, pg.UTCNow.Stamp)
	}
}
~~~~

Check: `sha256sum go/internal/web/customers/pages_test.go 2>&1 | tail -30` must print `5a8f5f63b38f367f387b493921627c3150895d58cfae33e8a4faa03757cc4b7a`.

Run §6. Commit `1361 step 6`.

### Step 7: report

Write the report (§9), set `Status: review`, commit `1361 step 7`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/` (incl. `layout/`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/billing/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `go/internal/web/customers/i18n.json`, `go/internal/web/customers/handlers*.go`, `go/internal/web/customers/query_test.go`, `go/internal/web/customers/testdata/admin_customers_golden.json`, `App/scripts/admin_customers_golden.py`, `App/tests/test_admin_customers_golden.py`, `App/tests/conftest.py`, every file under `App/app/`.
- `docs/context/*`, `docs/ENVIRONMENT.md`, Caddy, compose and `.env` files: no change. Never print the session secret or cookies. No push, merge or deploy.

## 6. Commands

1. Postgres: step 1 block.
2. Go, from the repo root:

```bash
cd go && export PATH=$PATH:/usr/local/go/bin
test -z "$(gofmt -l ./internal/web ./cmd)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ -count=1 -v 2>&1 | grep -E -c 'SKIP'
```

Expected: `ok` for both packages; the last command prints `0`.

3. From `App/`: `.venv/bin/python -m pytest tests/test_go_customers_pages_golden.py tests/test_go_host_i18n.py tests/test_admin_customers_golden.py -q --tb=short 2>&1 | tail -30` (`4 passed`).
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` ends `context lint: OK`.

No browser or screenshot test: see the risk list (UX gate).

## 7. Acceptance

- [ ] Every file in §3 has the sha256 given in §4.
- [ ] `TestPagesMatchPython`, `TestVisibleLines`, `TestPagesNeedAdmin`, `TestStampMatchesUTCNow` and all older `customers` and `cmd/ubyhost-web` tests pass; `grep -c SKIP` prints `0`.
- [ ] The golden script run twice leaves the JSON unchanged; §6 commands 3 and 4 as expected.
- [ ] `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_customers.go` prints `3`.
- [ ] `git diff --stat <start commit>` lists only the §3 paths.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 differs twice for the same file, or `git apply --check` fails;
- a generated file (`i18n.json`, the golden JSON) has a different sha256 than §4 says (main moved: the orchestrator regenerates);
- a test fails twice;
- Postgres does not start, or a DB test skips;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1361-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat <start commit>`; `<start commit>` is `git rev-parse HEAD` before step 1, write it down).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/customers/pages.go`: lists and strings mirror `admin_customers.html`; `pragueDay`; `listHref` key order and escaping; last value of a repeated query parameter (FastAPI).
- `go/internal/web/customers/query.go`: `asInt64` replaces the five bare assertions (ids, counts, state); behaviour unchanged.
- `go/internal/web/customers/pages_test.go` and `App/scripts/go_customers_pages_golden.py`: the two normalisers must stay identical.
- `go/cmd/ubyhost-web/register_web_customers.go`: one new pattern, no pool use while building.
- Hrefs: until brief 1381 adds a `safeHref` filter, no user-controlled URL may go into a layout macro `href`. Here every href is a fixed path, a `listHref` of urlencoded filter values, or a path with an integer id.
- UX gate (rules 7 and 10) cannot run yet: `test_layout_lint_browser.py` and the geometry tests drive the Python app (TestClient and a uvicorn server) and cannot load a Go-rendered page; no Go page is routed. No screenshots in this brief. The orchestrator runs the gate on the Go pages once a Go-backed browser fixture exists (before any `UBYHOST_GO_PATHS` switch).
- Go pages must not go live before 1381 (host alerts with filing warnings, billing banner are not in the layout yet).
- Parity gaps: none found in the 9 list cases. Not compared: the page shell (covered by the 1380 golden), class names, `data-*` and `aria-label` attributes, icons (svg dropped).

## Owner steps

None for this brief. The orchestrator opens the draft PR after 1364.
