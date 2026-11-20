package guest

import (
	"fmt"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

// renderGuidePage renders guest/guide.html (brief 1720 supplies the full shell).
func (h *GuideHandlers) renderGuidePage(w http.ResponseWriter, r *http.Request, lang string, apt *GuideApartment, res *GuideReservation, level, door, qrToken, backURL, leonURL string) {
	items, err := h.store.Items(r.Context(), apt.ID)
	if err != nil {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusNotFound, "", hardenedHeaders)
		return
	}
	live := ai.LeonProgressOf(items).Live
	page := guidePageData{Door: door, Level: level, NotReady: !live, BackURL: backURL, LeonURL: leonURL, Lang: lang}
	if live {
		cards, err := h.store.GuestCards(r.Context(), apt.ID)
		if err != nil {
			WriteUnavailable(w, r, lang, "bad_link", http.StatusNotFound, "", hardenedHeaders)
			return
		}
		page.Groups = groupCards(cards, lang)
	}
	h.writeGuideHTML(w, r, page)
	_ = res
	_ = qrToken
}

type guidePageData struct {
	Door, Level, BackURL, LeonURL, Lang string
	NotReady                            bool
	Groups                              []guideGroup
}

type guideGroup struct {
	Title string
	Cards []guideCardView
}

type guideCardView struct {
	ID    int64
	Title string
	Kind  string
}

func (h *GuideHandlers) writeGuideHTML(w http.ResponseWriter, r *http.Request, page guidePageData) {
	hd := w.Header()
	hd.Set("Content-Type", "text/html; charset=utf-8")
	for k, v := range hardenedHeaders {
		hd.Set(k, v)
	}
	w.WriteHeader(http.StatusOK)
	if r.Method == http.MethodHead {
		return
	}
	body := fmt.Sprintf("<!DOCTYPE html><html lang=%q><body data-guide-door=%q data-guide-level=%q", page.Lang, page.Door, page.Level)
	if page.NotReady {
		body += ` data-guide-not-ready="1"`
	}
	for _, g := range page.Groups {
		for _, c := range g.Cards {
			body += fmt.Sprintf(` data-guide-card="%d"`, c.ID)
		}
	}
	body += "></body></html>"
	_, _ = w.Write([]byte(body))
}

func groupCards(cards []ai.LeonCard, lang string) []guideGroup {
	if len(cards) == 0 {
		return nil
	}
	views := make([]guideCardView, 0, len(cards))
	for _, c := range cards {
		views = append(views, guideCardView{ID: c.ID, Title: c.Title, Kind: c.Kind})
	}
	return []guideGroup{{Title: "Guide", Cards: views}}
}
