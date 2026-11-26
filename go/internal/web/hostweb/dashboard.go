// Package hostweb serves GET / (brief 1751).
package hostweb

import (
	"embed"
	"html/template"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	hw "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/welcomeback"
)

//go:embed i18n.json
var dashJSON []byte

//go:embed templates/*.tmpl
var dashFS embed.FS

var dashStrings = hw.Load(dashJSON)

// dashFuncs are the dashboard's own helpers: what the overview prints about a
// stay (label, guest count, date range, demo and missing-guest state).
var dashFuncs = template.FuncMap{
	"dash_label":          dashLabel,
	"dash_guests":         dashGuests,
	"dash_first":          dashFirst,
	"dash_range":          fmtDateRange,
	"stay_range":          stayRange,
	"dash_not_registered": dashNotRegistered,
	"dash_is_demo":        dashIsDemo,
	"journey_strip":       stays.RenderJourneyStrip,
	"cal_prop_href":       calPropHref,
	"cal_prop_id":         calPropID,
	"bar_meta":            barMeta,
	"bar_display_label":   barDisplayLabel,
	"dash_short_date":     dashShortDate,
}

var dashTemplates = layout.MustParseFuncs(dashStrings, dashFuncs, dashFS, "templates/*.tmpl")

// dashboardPage wraps DashboardData with view state for Briefs 2089-2090.
type dashboardPage struct {
	DashboardData
	Cal              calPageView
	DesktopWindow    string
	DesktopRows      []desktopStayRow
	PropertyRails    []propertyRail
	TotalActiveProps int
}

func dashShortDate(lang, iso string) string {
	t, ok := pyDay(iso)
	if !ok {
		return iso
	}
	return stayRange(lang, t.Format("2006-01-02"), t.Format("2006-01-02"))
}

func calPropHref(apts []apartmentRow, name string) string {
	for _, a := range apts {
		if a.Name == name && a.Active {
			return "/?cal_view=calendar&cal_property=" + fmtInt64(a.ID)
		}
	}
	return "/?cal_view=calendar"
}

func fmtInt64(v int64) string {
	if v == 0 {
		return "0"
	}
	var buf [20]byte
	i := len(buf)
	for v > 0 {
		i--
		buf[i] = byte('0' + v%10)
		v /= 10
	}
	return string(buf[i:])
}

// dashLabel is the stay's name as the list prints it.
func dashLabel(r stays.Reservation) string { return stayLabel(r) }

// dashGuests is progress.expected when set, otherwise the guests on the stay.
func dashGuests(p stays.Progress) int {
	if p.Expected != nil {
		return *p.Expected
	}
	return len(p.Guests)
}

// dashFirst is stay_label[:1] | upper, the avatar letter.
func dashFirst(label string) string {
	for _, r := range label {
		return strings.ToUpper(string(r))
	}
	return ""
}

// dashNotRegistered is progress.not_registered, 0 when unknown.
func dashNotRegistered(p stays.Progress) int {
	if p.NotRegistered == nil {
		return 0
	}
	return *p.NotRegistered
}

// dashIsDemo is demo.is_demo_stay's name/source test.
func dashIsDemo(name, source string) bool {
	return strings.Contains(strings.ToLower(name), "(demo)") || source == "demo"
}

// DashboardHandler serves GET /.
func DashboardHandler(pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), now func() time.Time) http.HandlerFunc {
	deps := public.Deps{Getenv: getenv, SignedIn: func(r *http.Request) bool {
		c, err := r.Cookie(session.CookieName)
		if err != nil || c.Value == "" || pool == nil {
			return false
		}
		h, err := session.Load(r.Context(), pool, c.Value, now(), getenv)
		return err == nil && h != nil
	}}
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := session.Load(r.Context(), pool, hw.Cookie(r, session.CookieName), at, getenv)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if h == nil {
			if onAppHost(r, getenv) {
				auth.RootLoginHandler(pool, getenv, now).ServeHTTP(w, r)
				return
			}
			public.ServeLanding(w, r, deps)
			return
		}
		host, err := hw.Login(w, r, pool, getenv, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if host == nil {
			return
		}
		today := stays.PragueToday(at)
		if err := welcomeback.Check(r.Context(), pool, host.Account.ID, host.Workspace.ID, today); err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		calView := r.URL.Query().Get("cal_view") != "" || strings.HasPrefix(r.URL.RawQuery, "cal_")
		data, err := loadDashboard(r.Context(), pool, getenv, host.Workspace.ID, at, calView, hw.Lang(r))
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if err := applyCalmNeedsYou(r.Context(), pool, host.Workspace.ID, today, &data); err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		page := layout.Page{
			Title:    dashStrings.T(hw.Lang(r), "dashboard.title", nil),
			Nav:      "dashboard",
			BodyKind: "detail",
			V2:       true,
			HowKey:   "dashboard",
		}
		pd := dashboardPage{DashboardData: data}
		if calView {
			page.Nav = "calendar"
			page.Title = dashStrings.T(hw.Lang(r), "nav.calendar", nil)
			pd.Cal = buildCalendarView(data, r.URL.Query().Get("cal_property"), today)
		} else {
			pd.PropertyRails, pd.TotalActiveProps = buildPropertyRails(data.Apartments, data.Rows, today)
			pd.DesktopWindow, pd.DesktopRows = buildDesktopWindow(data.Rows, data.TodayRows, r.URL.Query().Get("window"), today)
		}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, page, dashTemplates, "dashboard", pd); err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		}
	}
}

func onAppHost(r *http.Request, getenv func(string) string) bool {
	appHost := hostname(getenv("UBYHOST_APP_BASE_URL"))
	publicHost := hostname(getenv("UBYHOST_PUBLIC_BASE_URL"))
	reqHost := strings.ToLower(r.Host)
	if i := strings.Index(reqHost, ":"); i >= 0 {
		reqHost = reqHost[:i]
	}
	return appHost != "" && appHost != publicHost && strings.EqualFold(reqHost, appHost)
}

func hostname(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	u, err := url.Parse(raw)
	if err != nil || u.Hostname() == "" {
		if strings.Contains(raw, "://") {
			return ""
		}
		h := raw
		if i := strings.Index(h, "/"); i >= 0 {
			h = h[:i]
		}
		if i := strings.Index(h, ":"); i >= 0 {
			h = h[:i]
		}
		return strings.ToLower(h)
	}
	return strings.ToLower(u.Hostname())
}
