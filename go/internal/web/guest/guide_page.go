package guest

// Brief 2016: guest/guide.html — the "Your guide" page behind the stay door and
// the QR door (App/app/templates/guest/guide.html, routes/guest_guide_view.py).

import (
	"net/http"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

// renderGuidePage renders guest/guide.html with the shared guest base.
func (h *GuideHandlers) renderGuidePage(w http.ResponseWriter, r *http.Request, lang string, apt *GuideApartment, res *GuideReservation, level, door, qrToken, backURL, leonURL string) {
	access := guestAccess{pool: h.pool, getenv: h.getenv, now: h.now}
	var aptRow *Apartment
	if row, _, _, ok := ResolveKey(r.Context(), h.pool, displayLink(qrToken)); ok {
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
	view := guidePageView{
		Page:     page,
		Door:     door,
		Level:    level,
		NotReady: !live,
		BackURL:  backURL,
		LeonURL:  leonURL,
	}
	if live {
		cards, err := h.store.GuestCards(r.Context(), apt.ID)
		if err != nil {
			access.unavailable(w, r, lang, "bad_link", http.StatusNotFound, "", 0, hardenedHeaders)
			return
		}
		view.Groups = groupCards(cards, level, token)
	}
	access.render(w, r, guideSet, view, http.StatusOK, hardenedHeaders, true)
	_ = res
}

// displayLink is the link key a guide route puts back into its own links.
func displayLink(token string) string { return token }

// guidePageView is guest/guide.html.
type guidePageView struct {
	Page
	Door        string
	Level       string
	NotReady    bool
	Translating bool
	BackURL     string
	LeonURL     string
	Groups      []guideGroup
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

// groupCards builds the card groups guest_guide.TOPICS orders.
func groupCards(cards []ai.LeonCard, level, token string) []guideGroup {
	if len(cards) == 0 {
		return nil
	}
	views := make([]guideCardView, 0, len(cards))
	for _, c := range cards {
		var steps []string
		for _, line := range strings.Split(c.Steps, "\n") {
			if trimmed := strings.TrimSpace(line); trimmed != "" {
				steps = append(steps, trimmed)
			}
		}
		views = append(views, guideCardView{
			ID:       c.ID,
			Kind:     c.Kind,
			Title:    ai.LeonCardTitle(c),
			Facts:    strings.Join(c.Facts, " "),
			Location: c.Location,
			Steps:    steps,
			WatchOut: c.WatchOut,
			VideoURL: c.VideoURL,
		})
	}
	// The topic kicker is host copy (guest_guide.topic.*); it is left out until
	// the topic is carried on the card, so no guest sees a wrong heading.
	return []guideGroup{{Cards: views}}
}
