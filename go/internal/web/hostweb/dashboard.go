// Package hostweb serves GET / (brief 1751).
package hostweb

import (
	"embed"
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

//go:embed templates/dashboard.tmpl
var dashFS embed.FS

var dashStrings = hw.Load(dashJSON)
var dashTemplates = layout.MustParse(dashStrings, dashFS, "templates/dashboard.tmpl")

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
		page := layout.Page{
			Title:    dashStrings.T(hw.Lang(r), "dashboard.title", nil),
			Nav:      "dashboard",
			BodyKind: "detail",
			V2:       true,
			HowKey:   "dashboard",
		}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, page, dashTemplates, "dashboard", data); err != nil {
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
