package ai

// The card routes of App/app/routes/guest_guide.py (brief 1441): one card's
// editor and its save, discard, skip and delete, and "add a card". The data
// rules are in guide_data.go. Photos are brief 1442.

import (
	"net/http"
	"strconv"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// guideMaxPhotos is guide_photos.MAX_PER_ITEM.
const guideMaxPhotos = 6

func init() {
	guideAdd("GET", "/apartments/{id}/guide/{item}", (*guideServer).cardPage)
	guideAdd("POST", "/apartments/{id}/guide/{item}", (*guideServer).cardSave)
	// discard, skip and delete share one pattern: "/guide/{item}/discard" and
	// "/guide/quick/{step}" would otherwise overlap on /guide/quick/discard.
	guideAdd("POST", "/apartments/{id}/guide/{item}/{action}", (*guideServer).cardAction)
	guideAdd("POST", "/apartments/{id}/guide/cards", (*guideServer).cardAdd)
}

// guideValues are the field values the card form shows.
type guideValues struct {
	Title, Location, Steps, WatchOut, VideoURL, Visibility string
}

func guideValuesOf(it guideItem) guideValues {
	return guideValues{it.Title, it.Location, it.Steps, it.WatchOut, it.VideoURL, it.Visibility}
}

// guideCardData is the context of guide_card.tmpl.
type guideCardData struct {
	Apartment *guideApartment
	Item      guideItem
	Values    guideValues
	Error     string
	Photos    []guidePhoto
	MaxPhotos int
	FromLeon  bool
	Custom    bool
	CardTitle string
	DraftFrom string
	Base      string
}

// guideCardTitle is card_title of the template.
func guideCardTitle(lang string, it guideItem) string {
	if it.Kind == "custom" {
		return it.Title
	}
	return guideCatalog.T(lang, "guest_guide.kind."+it.Kind+".title", nil)
}

// card is _card: render guest_guide_card.html.
func (s *guideServer) card(w http.ResponseWriter, q *guideReq, a *guideApartment, item guideItem, values guideValues, errKey string, status int, fromLeon bool) {
	photos, err := s.photos(q.r.Context(), a.ID, item.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	draft := "other"
	if item.Source == "booking" || item.Source == "airbnb" || item.Source == "legacy" {
		draft = item.Source
	}
	title := guideCardTitle(q.lang, item)
	data := guideCardData{Apartment: a, Item: item, Values: values, Error: errKey, Photos: photos, MaxPhotos: guideMaxPhotos,
		FromLeon: fromLeon, Custom: item.Kind == "custom", CardTitle: title, DraftFrom: draft, Base: q.base()}
	page := layout.Page{
		Title:    title + " · " + guideCatalog.T(q.lang, "guest_guide.title", nil) + " · UbyHost",
		BodyKind: "form", V2: true, BackURL: q.base(),
	}
	s.render(w, q, "guide_card", page, status, data)
}

// cardPage is GET /apartments/{id}/guide/{item} (guide_card, guest_guide.py 312-321).
func (s *guideServer) cardPage(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	item, err := s.getItem(r.Context(), a.ID, q.item)
	if err != nil {
		guideFail(w, err)
		return
	}
	if item == nil {
		guideNotFound(w)
		return
	}
	s.card(w, q, a, *item, guideValuesOf(*item), "", http.StatusOK, guideQueryValue(r, "from") == "leon")
}

// leonAfterSave is _leon_after_save: a card opened from the Leon setup wizard returns to the wizard.
func (s *guideServer) leonAfterSave(w http.ResponseWriter, q *guideReq, itemID int64, then string) {
	if then == "next" {
		next, err := s.nextOpen(q.r.Context(), q.apt, itemID)
		if err != nil {
			guideFail(w, err)
			return
		}
		if next != 0 {
			q.back(w, q.base()+"/"+strconv.FormatInt(next, 10)+"?from=leon", hostweb.Flash{}, hostweb.Flash{})
			return
		}
	}
	q.back(w, "/apartments/"+strconv.FormatInt(q.apt, 10)+"/leon/setup/cards", hostweb.Flash{}, hostweb.Flash{})
}

// cardSave is POST /apartments/{id}/guide/{item} (guide_card_save, 333-357).
func (s *guideServer) cardSave(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	ctx := r.Context()
	item, err := s.getItem(ctx, a.ID, q.item)
	if err != nil {
		guideFail(w, err)
		return
	}
	if item == nil {
		guideNotFound(w)
		return
	}
	fields := map[string]string{}
	for _, name := range guideLimitOrder {
		if v, present := guideFormValue(r, name); present {
			fields[name] = v
		}
	}
	if v, present := guideFormValue(r, "visibility"); present {
		fields["visibility"] = v
	} else {
		fields["visibility"] = item.Visibility
	}
	from, _ := guideFormValue(r, "from")
	then, _ := guideFormValue(r, "then")
	if _, err := s.save(ctx, a.ID, item.ID, fields, guideStamp(q.at)); err != nil {
		key := guideErrKey(err)
		if key == "" {
			guideFail(w, err)
			return
		}
		values := guideValuesOf(*item)
		for name, v := range fields {
			switch name {
			case "title":
				values.Title = v
			case "location":
				values.Location = v
			case "steps":
				values.Steps = v
			case "watch_out":
				values.WatchOut = v
			case "video_url":
				values.VideoURL = v
			case "visibility":
				values.Visibility = v
			}
		}
		s.card(w, q, a, *item, values, key, http.StatusUnprocessableEntity, from == "leon")
		return
	}
	if from == "leon" {
		s.leonAfterSave(w, q, item.ID, then)
		return
	}
	if then == "next" {
		next, err := s.nextOpen(ctx, a.ID, item.ID)
		if err != nil {
			guideFail(w, err)
			return
		}
		if next != 0 {
			q.back(w, q.base()+"/"+strconv.FormatInt(next, 10), q.flash("flash.guest_guide.saved", nil), hostweb.Flash{})
			return
		}
	}
	q.back(w, q.base(), q.flash("flash.guest_guide.saved", nil), hostweb.Flash{})
}

// cardAction routes POST /apartments/{id}/guide/{item}/{action}: discard,
// skip and delete. Any other action is the router's 404, before CSRF.
func (s *guideServer) cardAction(w http.ResponseWriter, r *http.Request) {
	switch r.PathValue("action") {
	case "discard":
		s.cardDiscard(w, r)
	case "skip":
		s.cardSkip(w, r)
	case "delete":
		s.cardDelete(w, r)
	default:
		guideNotFound(w)
	}
}

// cardDiscard is POST .../{item}/discard (guide_card_discard, 360-368).
func (s *guideServer) cardDiscard(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	done, err := s.discardDraft(r.Context(), a.ID, q.item, guideStamp(q.at))
	if err != nil {
		guideFail(w, err)
		return
	}
	if !done {
		guideNotFound(w)
		return
	}
	q.back(w, q.base()+"/"+strconv.FormatInt(q.item, 10), q.flash("flash.guest_guide.discarded", nil), hostweb.Flash{})
}

// cardSkip is POST .../{item}/skip (guide_card_skip, 371-384).
func (s *guideServer) cardSkip(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	skip, _ := guideFormValue(r, "skip")
	if err := s.skip(r.Context(), a.ID, q.item, skip == "1", guideStamp(q.at)); err != nil {
		if guideErrKey(err) != "" {
			guideNotFound(w)
			return
		}
		guideFail(w, err)
		return
	}
	if from, _ := guideFormValue(r, "from"); from == "leon" {
		then, _ := guideFormValue(r, "then")
		s.leonAfterSave(w, q, q.item, then)
		return
	}
	q.back(w, q.base(), hostweb.Flash{}, hostweb.Flash{})
}

// cardDelete is POST .../{item}/delete (guide_card_delete, 387-399): custom cards only.
func (s *guideServer) cardDelete(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	ctx := r.Context()
	item, err := s.getItem(ctx, a.ID, q.item)
	if err != nil {
		guideFail(w, err)
		return
	}
	if item == nil || item.Kind != "custom" {
		guideNotFound(w)
		return
	}
	photos, err := s.photos(ctx, a.ID, item.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	for _, p := range photos {
		if _, err := s.deletePhoto(ctx, a.ID, item.ID, p.ID); err != nil {
			guideFail(w, err)
			return
		}
	}
	if _, err := s.deleteCustom(ctx, a.ID, item.ID); err != nil {
		guideFail(w, err)
		return
	}
	q.back(w, q.base(), q.flash("flash.guest_guide.deleted", nil), hostweb.Flash{})
}

// cardAdd is POST /apartments/{id}/guide/cards (guide_add, 99-110).
func (s *guideServer) cardAdd(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	topic, _ := guideFormValue(r, "topic")
	title, _ := guideFormValue(r, "title")
	id, err := s.addCustom(r.Context(), a.ID, topic, title, guideStamp(q.at))
	if err != nil {
		if key := guideErrKey(err); key != "" {
			q.back(w, q.base(), hostweb.Flash{}, q.flash(key, nil))
			return
		}
		guideFail(w, err)
		return
	}
	q.back(w, q.base()+"/"+strconv.FormatInt(id, 10), hostweb.Flash{}, hostweb.Flash{})
}
