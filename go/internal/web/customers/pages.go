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
