package guest

// Brief 2016: the pages the guest link hub shows before a form — the claim ask,
// the confirm step and the "nothing to fill in" page — with the same blocks,
// wording and order as App/app/templates/guest/{claim,confirm,unavailable}.html.

import (
	"bytes"
	"context"
	"html/template"
	"log"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// pageSet parses the guest base shell plus one page template: each page defines
// its own "content" block, so they cannot share a template set.
func pageSet(names ...string) *template.Template {
	files := append([]string{"templates/base.tmpl", "templates/host_fragment.tmpl", "templates/why_fragment.tmpl"}, names...)
	return template.Must(template.New("guest.base").Funcs(tplFuncs).ParseFS(templateFS, files...))
}

var (
	claimSet    = pageSet("templates/claim.tmpl")
	confirmSet  = pageSet("templates/confirm.tmpl")
	unavailSet  = pageSet("templates/unavailable.tmpl")
	guideSet    = pageSet("templates/guide.tmpl")
	staySet     = pageSet("templates/stay.tmpl", "templates/fee_pay.tmpl")
	assignedSet = pageSet("templates/assigned.tmpl")
)

// unavailableTitles is guest.py _unavailable's titles table.
var unavailableTitles = map[string][2]string{
	"no_stays":      {"no_stays", "no_stays_help"},
	"bad_link":      {"bad_link_title", "bad_link_help"},
	"stay_gone":     {"stay_gone_title", "stay_gone_help"},
	"form_expired":  {"form_expired_title", "form_expired_help"},
	"rate_limited":  {"rate_limited_title", "rate_limited_help"},
	"not_yours":     {"not_yours_title", "not_yours_help"},
	"already_filed": {"already_filed_title", "already_filed_help"},
	"form_locked":   {"form_locked_title", "form_locked_help"},
	"server_error":  {"server_error_title", "server_error_help"},
}

// noRestartReasons is guest.py _NO_RESTART_REASONS: the stay cannot be changed
// from the guest's side, so sending them back to the picker only loops.
var noRestartReasons = map[string]bool{"form_locked": true, "already_filed": true, "not_yours": true}

// unavailableView is guest/unavailable.html on top of the shared Page.
type unavailableView struct {
	Page
	TitleKey         string
	BodyKey          string
	RestartURL       string
	StayURL          string
	HostMessageURL   string
	HostNote         string
	OfferMessageHost bool
}

func (u unavailableView) T(key string, kv ...any) string { return u.Page.T(key, kv...) }

// unavailable is guest.py _unavailable. resID is only passed by the form guards,
// so the "back to your stay" button appears exactly where Python shows it.
func (g guestAccess) unavailable(w http.ResponseWriter, r *http.Request, lang, reason string, status int, token string, resID int64, extra map[string]string) {
	g.unavailableNote(w, r, lang, reason, status, token, resID, "", extra)
}

// unavailableNote is _unavailable with the host-only note the picker prints.
func (g guestAccess) unavailableNote(w http.ResponseWriter, r *http.Request, lang, reason string, status int, token string, resID int64, hostNote string, extra map[string]string) {
	keys, ok := unavailableTitles[reason]
	if !ok {
		keys = unavailableTitles["bad_link"]
	}
	code := GuestLanguage(lang)
	var apt *Apartment
	if token != "" {
		if resolved, _, _, found := ResolveKey(r.Context(), g.pool, token); found {
			apt = resolved
		}
	}
	var page Page
	if token != "" {
		page = g.page(r.Context(), r, token, code, apt)
	} else {
		page = Page{Lang: code, LangURLs: LangURLs(r, ""), GuestEndonyms: GuestEndonyms}
	}
	view := unavailableView{Page: page, TitleKey: keys[0], BodyKey: keys[1], HostNote: hostNote}
	if token != "" && !noRestartReasons[reason] {
		view.RestartURL = GuestLink(token, 0, "") + LangQuery(code, "")
	}
	if token != "" && resID != 0 && noRestartReasons[reason] {
		view.StayURL = GuestLink(token, resID, "") + LangQuery(code, "")
	}
	view.OfferMessageHost = reason == "already_filed" || reason == "form_locked" || reason == "not_yours"
	view.HostMessageURL = hostMessageURL(apt, hostContact(r.Context(), g.pool, apt))
	g.render(w, r, unavailSet, view, status, extra, false)
}

// renderPage writes one guest page with the guest language cookie.
func (g guestAccess) renderPage(w http.ResponseWriter, r *http.Request, set *template.Template, view any, extra map[string]string) {
	g.render(w, r, set, view, http.StatusOK, extra, true)
}

func (g guestAccess) render(w http.ResponseWriter, r *http.Request, set *template.Template, view any, status int, extra map[string]string, setLang bool) {
	if setLang {
		if lang, ok := view.(interface{ GetLang() string }); ok {
			WithLang(w, g.getenv, lang.GetLang())
		}
	}
	var buf bytes.Buffer
	if err := set.ExecuteTemplate(&buf, "guest.base", view); err != nil {
		log.Printf("guest page: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	for k, v := range extra {
		h.Set(k, v)
	}
	w.WriteHeader(status)
	if r.Method != http.MethodHead {
		_, _ = buf.WriteTo(w)
	}
}

// claimView is guest/claim.html.
type claimView struct {
	Page
	StayFrom, StayTo string
	CanPickOther     bool
	BackURL          string
	ClaimSent        bool
	ClaimErrorText   string
	ClaimEmailMasked string
	DeclaredGuests   int64
	CSRFToken        string
	ActionURL        string
	RequireTurnstile bool
	TurnstileSiteKey string
}

func (v claimView) T(key string, kv ...any) string { return v.Page.T(key, kv...) }

// GetLang lets render set the guest language cookie.
func (v claimView) GetLang() string { return v.Lang }

// claimErrorText is claim.html's error line: only the listed codes have their
// own text, anything else is the party-size message.
func claimErrorText(lang, code string) string {
	if code == "" {
		return ""
	}
	switch code {
	case "bad_email", "bad_party", "held", "already_claimed", "rate", "cooldown", "recipient_rate", "bot":
		return stringsCatalog.T(lang, "claim_error_"+code, nil)
	}
	return stringsCatalog.T(lang, "error_party_size", nil)
}

// confirmView is guest/confirm.html.
type confirmView struct {
	Page
	StayFrom, StayTo string
	ClaimError       bool
	CSRFToken        string
	ActionURL        string
}

func (v confirmView) T(key string, kv ...any) string { return v.Page.T(key, kv...) }

// GetLang lets render set the guest language cookie.
func (v confirmView) GetLang() string { return v.Lang }

// canPickOtherStays is guest.py _can_pick_other_stays.
func canPickOtherStays(ctx context.Context, pool *pgxpool.Pool, apt *Apartment, now func() time.Time) bool {
	if apt == nil {
		return false
	}
	papt, ok := loadPickApartment(ctx, pool, apt.ID)
	if !ok {
		return false
	}
	rows, err := visibleReservations(ctx, pool, papt, now())
	if err != nil {
		return false
	}
	return len(rows) > 0
}
