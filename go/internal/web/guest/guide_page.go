package guest

// Brief 2016: guest/guide.html — the "Your guide" page behind the stay door and
// the QR door (App/app/templates/guest/guide.html, routes/guest_guide_view.py).

import (
	"context"
	"net/http"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

// renderGuidePage renders guest/guide.html with the shared guest base.
func (h *GuideHandlers) renderGuidePage(w http.ResponseWriter, r *http.Request, lang string, apt *GuideApartment, res *GuideReservation, level, door, qrToken, backURL, leonURL string) {
	access := guestAccess{pool: h.pool, getenv: h.getenv, now: h.now}
	var aptRow *Apartment
	if row, ok := loadApartmentByID(r.Context(), h.pool, apt.ID); ok {
		aptRow = row
	}
	token := qrToken
	if door == "qr" {
		// A QR page carries no stay link: the privacy notice link is the only one
		// it keeps, and the host card shows the name only (owner, 2026-10-24).
		token = ""
	}
	page := access.page(r.Context(), r, token, lang, aptRow)
	if door == "qr" {
		page.PrivacyURL = ""
		page.Host = HostContact{Name: page.Host.Name}
	}
	items, err := h.store.Items(r.Context(), apt.ID)
	if err != nil {
		access.unavailable(w, r, lang, "bad_link", http.StatusNotFound, "", 0, hardenedHeaders)
		return
	}
	live := ai.LeonProgressOf(items).Live
	if !live || !h.guideLeonOn(r.Context(), apt.ID) {
		leonURL = ""
	}
	view := guidePageView{
		Page:     page,
		Door:     door,
		Level:    level,
		NotReady: !live,
		BackURL:  backURL,
		LeonURL:  leonURL,
		LeonHost: ai.LeonHostFirstName(page.Host.Name),
	}
	if live {
		cards, err := h.store.GuestCards(r.Context(), apt.ID, level)
		if err != nil {
			access.unavailable(w, r, lang, "bad_link", http.StatusNotFound, "", 0, hardenedHeaders)
			return
		}
		view.Groups = groupCards(cards, lang)
	}
	access.render(w, r, guideSet, view, http.StatusOK, hardenedHeaders, true)
	_ = res
}

// guidePageView is guest/guide.html.
type guidePageView struct {
	Page
	Door        string
	Level       string
	NotReady    bool
	Translating bool
	BackURL     string
	LeonURL     string
	LeonHost    string
	Groups      []guideGroup
}

// guideLeonOn is the Leon chat gate of guest_guide_view._page: the feature is
// on and the property has switched Leon on. Any error hides the chat.
func (h *GuideHandlers) guideLeonOn(ctx context.Context, aptID int64) bool {
	if !anthropic.ConfigFromEnv(h.store.HavelStore.Env).Enabled("leon") {
		return false
	}
	var a ai.LeonApartment
	err := h.pool.QueryRow(ctx, `SELECT id, owner_user_id, COALESCE(internal_name,''), leon_enabled <> 0, COALESCE(leon_terms_version,'')
		FROM apartment WHERE id = $1`, aptID).Scan(&a.ID, &a.OwnerID, &a.Name, &a.Enabled, &a.TermsVersion)
	if err != nil {
		return false
	}
	on, err := h.store.SwitchedOn(ctx, a)
	return err == nil && on
}

// T is the page translator.
func (v guidePageView) T(key string, kv ...any) string { return v.Page.T(key, kv...) }

// GetLang lets render set the guest language cookie.
func (v guidePageView) GetLang() string { return v.Lang }

type guideGroup struct {
	Title string
	Cards []guideCardView
}

// guideCardView is one written card: the host's own words, or its translation.
type guideCardView struct {
	ID       int64
	Kind     string
	Title    string
	Facts    string
	Location string
	Steps    []string
	WatchOut string
	VideoURL string
	Photos   []string
}

// groupCards builds one group per topic in guest_guide.TOPICS order, only for
// topics that have cards (guest_guide_view._groups). Titles follow the page language.
func groupCards(cards []ai.LeonCard, lang string) []guideGroup {
	if len(cards) == 0 {
		return nil
	}
	byTopic := map[string][]guideCardView{}
	for _, c := range cards {
		var steps []string
		for _, line := range strings.Split(c.Steps, "\n") {
			if trimmed := strings.TrimSpace(line); trimmed != "" {
				steps = append(steps, trimmed)
			}
		}
		byTopic[c.Topic] = append(byTopic[c.Topic], guideCardView{
			ID:       c.ID,
			Kind:     c.Kind,
			Title:    ai.LeonCardTitleIn(c, lang),
			Facts:    strings.Join(c.Facts, " "),
			Location: c.Location,
			Steps:    steps,
			WatchOut: c.WatchOut,
			VideoURL: c.VideoURL,
		})
	}
	var groups []guideGroup
	for _, topic := range ai.GuideTopics() {
		if views := byTopic[topic]; len(views) > 0 {
			groups = append(groups, guideGroup{Title: ai.GuideTopicTitle(topic, lang), Cards: views})
		}
	}
	return groups
}
