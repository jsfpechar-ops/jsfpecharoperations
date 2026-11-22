package guest

// Brief 2016: page plumbing every /l page shares — the language switcher's
// order (i18n.enabled_languages), the signed-in host check
// (auth.workspace_user) the claim, form and guide gates ask before they hand
// out a stay, and the page context guest.py _shared builds.

import (
	"context"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// langOrder is i18n.enabled_languages: the switcher lists the catalog order
// (en, cs, de, es, fr, uk), not the map's random key order.
func langOrder(urls map[string]string) []string {
	out := make([]string, 0, len(urls))
	for _, code := range guestCatalog {
		if _, ok := urls[code]; ok {
			out = append(out, code)
		}
	}
	return out
}

// guestAccess holds what the host-session checks and the shared page need.
type guestAccess struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// hostUserID is auth.workspace_user: the workspace user id, 0 for a visitor.
func (g guestAccess) hostUserID(ctx context.Context, r *http.Request) int64 {
	if g.pool == nil || r == nil {
		return 0
	}
	cookie := hostweb.Cookie(r, session.CookieName)
	if cookie == "" {
		return 0
	}
	at := time.Now()
	if g.now != nil {
		at = g.now()
	}
	h, err := session.Load(ctx, g.pool, cookie, at, g.getenv)
	if err != nil || h == nil {
		return 0
	}
	return h.Workspace.ID
}

// hostOwns is guest.py _host_owns_apartment: the signed-in host filling the
// guest form for their own property. A guest, another host or an admin is not
// the owner and gets the guest path.
func (g guestAccess) hostOwns(ctx context.Context, r *http.Request, ownerID int64) bool {
	if ownerID == 0 {
		return false
	}
	uid := g.hostUserID(ctx, r)
	return uid != 0 && uid == ownerID
}

// page is guest.py _shared: the context every guest page needs, whatever it is
// showing. token is the link key the page's own links stay on; it is empty on
// the bare 404, which then shows no privacy link and the "in the message that
// contained this link" host hint.
func (g guestAccess) page(ctx context.Context, r *http.Request, token, lang string, apt *Apartment) Page {
	code := GuestLanguage(lang)
	p := Page{
		Lang:          code,
		Token:         token,
		LangURLs:      LangURLs(r, ""),
		GuestEndonyms: GuestEndonyms,
	}
	if apt != nil {
		p.Facility = Facility(apt)
		p.FacilityTone = int(apt.ID % 10)
		host := hostContact(ctx, g.pool, apt)
		p.Host = HostContact{Name: host.Name, Email: host.Email, Phone: host.Phone}
	}
	if token != "" {
		p.PrivacyURL = GuestLink(token, 0, "/privacy") + LangQuery(code, "")
	}
	return p
}

// hostLinkNote is guest.py _host_link_note: the signed-in owner learns why their
// link is empty. Guests keep the neutral text, so no other stay's dates reach
// them, and the note is host copy in the host's own language.
func (g guestAccess) hostLinkNote(ctx context.Context, r *http.Request, apt *Apartment) string {
	if apt == nil || !g.hostOwns(ctx, r, apt.OwnerUserID) {
		return ""
	}
	lang := hostweb.Lang(r)
	var days int64 = 1
	if err := g.pool.QueryRow(ctx, `SELECT GREATEST(COALESCE(permalink_window_days,1),1) FROM apartment WHERE id = $1`, apt.ID).Scan(&days); err != nil {
		days = 1
	}
	var from string
	err := g.pool.QueryRow(ctx,
		`SELECT COALESCE(date_from::text,'') FROM reservation
		 WHERE apartment_id = $1 AND status = 'active' AND archived_at IS NULL
		   AND COALESCE(source,'') != 'demo' AND date_from >= $2
		 ORDER BY date_from LIMIT 1`, apt.ID, PragueToday(g.now).Format("2006-01-02")).Scan(&from)
	if err != nil || from == "" {
		return stringsCatalog.T(lang, "workflow.link.host_note_none", nil)
	}
	start, ok := validation.ParseISODate(from)
	if !ok {
		return stringsCatalog.T(lang, "workflow.link.host_note_none", nil)
	}
	opens := start.AddDate(0, 0, -int(days))
	return stringsCatalog.T(lang, "workflow.link.host_note", map[string]any{
		"stay": start.Format("02.01.2006"),
		"date": opens.Format("02.01.2006"),
	})
}
