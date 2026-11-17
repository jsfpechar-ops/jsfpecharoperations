// Package settings serves the Settings pages (brief 1704b): GET /settings, the
// index of the six groups, and GET /settings/{account,data,technical,help},
// the Go twin of routes/admin.py _settings_page and templates/settings.html.
// The groups security and phone are brief 1704c (security.go, phone.go).
// Nothing routes here until the owner adds the paths to UBYHOST_GO_PATHS
// (brief 1705).
package settings

import (
	"context"
	"embed"
	"log"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed templates/*.tmpl
var templateFiles embed.FS

//go:embed i18n.json
var catalogJSON []byte

// catalog is the page catalog, written from host_i18n.py by
// App/scripts/go_host_i18n.py from i18n_keys.txt.
var catalog = hostweb.Load(catalogJSON)

// pages is parsed once; the layout clones it per request. settings.tmpl is the
// shell and the groups account, data, technical and help; group_security.tmpl
// and group_phone.tmpl define the two groups of brief 1704c.
var pages = layout.MustParseFuncs(catalog, nil, templateFiles, "templates/*.tmpl")

// Groups is SETTINGS_GROUPS in Python's order.
var Groups = []string{"account", "security", "phone", "data", "technical", "help"}

// supportAuditActions is SUPPORT_AUDIT_ACTIONS: what "Support sessions" lists
// besides every row written while an admin acted for the host.
var supportAuditActions = []string{"impersonation_started", "impersonation_stopped", "guest_identity_revealed"}

// deps is what a group loader reads.
type deps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
}

// pageData is the settings.html context. Group is "" for the index. Each
// loader fills the one field of its group; the template reads only that one.
type pageData struct {
	Group     string
	Account   *accountData
	Data      *dataData
	Technical *technicalData
	Help      *helpData
	Security  *SecurityData // security.go (brief 1704c; 1764 adds DeviceKind there)
	Phone     *PhoneData    // phone.go (brief 1704c)
}

// loader fills the part of pageData that one group shows. It reads only rows
// of the workspace (h.Workspace.ID) or of the signed-in account.
type loader func(ctx context.Context, d deps, h *session.Host, r *http.Request, at time.Time, p *pageData) error

// loaders maps a group key to its loader. The index ("") needs none.
var loaders = map[string]loader{
	"account":   loadAccount,
	"data":      loadData,
	"technical": loadTechnical,
	"help":      loadHelp,
	"security":  loadSecurity,
	"phone":     loadPhone,
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("settings route failed: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// Handler serves GET /settings (group "") and GET /settings/<group>
// (routes/admin.py _settings_page): require_login, then settings.html in the
// host layout (nav settings, body kind settings, v2, the page draws its own
// header). A group without a loader answers 404.
func Handler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, group string) http.HandlerFunc {
	load, known := loaders[group]
	if group == "" {
		known = true
	}
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		w.Header().Set("Cache-Control", "no-store, private")
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if h == nil {
			return
		}
		if !known {
			http.NotFound(w, r)
			return
		}
		data := &pageData{Group: group}
		if load != nil {
			if err := load(r.Context(), deps{pool, getenv}, h, r, at, data); err != nil {
				serverError(w, err)
				return
			}
		}
		page := layout.Page{
			Title:      catalog.T(hostweb.Lang(r), "nav.settings", nil),
			Nav:        "settings",
			BodyKind:   "settings",
			V2:         true,
			BodyAlerts: true,
		}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, page, pages, "settings", data); err != nil {
			serverError(w, err)
		}
	}
}
