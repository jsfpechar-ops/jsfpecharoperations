package guest

// Brief 1720c: GET /l/{token} — pick_stay parity (visible window, PIN guard, device rows).

import (
	"bytes"
	"html/template"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

type pickRow struct {
	Reservation   pickReservation
	Yours         bool
	ArrivingToday bool
	Ongoing       bool
	LaneIndex     int
}

// PickView is guest/pick.html on top of Page.
type PickView struct {
	Page
	PropertyName string
	Apartment    pickApartment
	Rows         []pickRow
}

func (p PickView) T(key string, kv ...any) string { return p.Page.T(key, kv...) }

var pickTplFuncs = template.FuncMap{
	"date_cz": func(v string) string {
		if t, ok := validation.ParseISODate(v); ok {
			return t.Format("02.01.2006")
		}
		return v
	},
	"nights_label": pickNightsLabel,
}

func pickNightsLabel(lang, from, to string) string {
	a, ok1 := validation.ParseISODate(from)
	b, ok2 := validation.ParseISODate(to)
	if !ok1 || !ok2 || !b.After(a) {
		return ""
	}
	n := int(b.Sub(a).Hours() / 24)
	key := "nights_many"
	switch lang {
	case "cs":
		switch {
		case n == 1:
			key = "night_one"
		case n >= 2 && n <= 4:
			key = "nights_few"
		}
	default:
		if n == 1 {
			key = "night_one"
		}
	}
	return stringsCatalog.T(lang, key, map[string]any{"n": n, "count": n})
}

var pickSet = func() *template.Template {
	t := template.Must(template.New("guest.base").Funcs(mergeTplFuncs(tplFuncs, pickTplFuncs)).ParseFS(templateFS,
		"templates/base.tmpl", "templates/host_fragment.tmpl", "templates/pick.tmpl", "templates/why_fragment.tmpl"))
	return t
}()

var unavailableSet = func() *template.Template {
	t := template.Must(template.New("guest.base").Funcs(tplFuncs).ParseFS(templateFS,
		"templates/base.tmpl", "templates/host_fragment.tmpl", "templates/unavailable.tmpl"))
	return t
}()

func mergeTplFuncs(a, b template.FuncMap) template.FuncMap {
	out := template.FuncMap{}
	for k, v := range a {
		out[k] = v
	}
	for k, v := range b {
		out[k] = v
	}
	return out
}

type unavailableView struct {
	Page
	TitleKey   string
	BodyKey    string
	RestartURL string
	HostNote   string
}

func (u unavailableView) T(key string, kv ...any) string { return u.Page.T(key, kv...) }

func writePickPage(w http.ResponseWriter, r *http.Request, status int, p PickView, extra map[string]string, getenv func(string) string, lang string) {
	WithLang(w, getenv, lang)
	var buf strings.Builder
	if err := pickSet.ExecuteTemplate(&buf, "guest.base", p); err != nil {
		log.Printf("guest pick page: %v", err)
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
		_, _ = io.WriteString(w, buf.String())
	}
}

func writeUnavailable(w http.ResponseWriter, r *http.Request, status int, u unavailableView, getenv func(string) string, lang string) {
	WithLang(w, getenv, lang)
	var buf bytes.Buffer
	if err := unavailableSet.ExecuteTemplate(&buf, "guest.base", u); err != nil {
		log.Printf("guest unavailable: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	if r.Method != http.MethodHead {
		_, _ = buf.WriteTo(w)
	}
}

func (d shellDeps) pickStay(w http.ResponseWriter, r *http.Request) {
	lang := Language(r)
	key := r.PathValue("token")
	now := d.now()
	apt, link, early := OpenLink(r, d.pool, key, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return
	}
	if apt == nil {
		http.NotFound(w, r)
		return
	}
	papt, ok := loadPickApartment(r.Context(), d.pool, apt.ID)
	if !ok {
		http.NotFound(w, r)
		return
	}
	alertControllerMissing(r.Context(), d.pool, papt)
	if requirePin(w, r, d, link, lang, apt) {
		return
	}
	reservations, err := visibleReservations(r.Context(), d.pool, papt, now)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	visible := map[int64]struct{}{}
	for _, res := range reservations {
		visible[res.ID] = struct{}{}
	}
	for _, claimedID := range claimedReservationIDs(r, d.getenv) {
		if _, ok := visible[claimedID]; ok {
			continue
		}
		extra, err := reservationForGuestExtra(r.Context(), d.pool, papt, claimedID, now)
		if err != nil || extra == nil {
			continue
		}
		reservations = append(reservations, *extra)
		visible[extra.ID] = struct{}{}
	}
	if len(reservations) == 0 {
		u := unavailableView{
			Page: Page{
				Lang: GuestLanguage(lang), Token: link, LangURLs: LangURLs(r, ""),
				PrivacyURL:    GuestLink(link, 0, "/privacy") + LangQuery(GuestLanguage(lang), ""),
				GuestEndonyms: GuestEndonyms,
				Facility:      Facility(apt), FacilityTone: int(apt.ID % 10),
			},
			TitleKey:   "no_stays",
			BodyKey:    "no_stays_help",
			RestartURL: GuestLink(link, 0, "") + LangQuery(GuestLanguage(lang), ""),
		}
		writeUnavailable(w, r, http.StatusOK, u, d.getenv, u.Lang)
		return
	}
	ownedList := ownedGuestIDs(r, d.getenv)
	owned := map[int64]struct{}{}
	for _, id := range ownedList {
		owned[id] = struct{}{}
	}
	today := pragueTodayPick(now)
	var rows []pickRow
	for i, res := range reservations {
		start, _ := validation.ParseISODate(res.DateFrom)
		end, _ := validation.ParseISODate(res.DateTo)
		rows = append(rows, pickRow{
			Reservation:   res,
			Yours:         stayHasOwnedGuest(r.Context(), d.pool, res.ID, owned),
			ArrivingToday: !start.IsZero() && start.Equal(today),
			Ongoing:       !start.IsZero() && !end.IsZero() && !start.After(today) && end.After(today),
			LaneIndex:     i,
		})
	}
	view := PickView{
		Page: Page{
			Lang: GuestLanguage(lang), Token: link, LangURLs: LangURLs(r, ""),
			PrivacyURL: GuestLink(link, 0, "/privacy") + LangQuery(GuestLanguage(lang), ""),
			Facility:   Facility(apt), FacilityTone: int(apt.ID % 10),
			GuestEndonyms: GuestEndonyms,
		},
		PropertyName: DisplayName(apt),
		Apartment:    papt,
		Rows:         rows,
	}
	writePickPage(w, r, http.StatusOK, view, map[string]string{"Cache-Control": "no-store"}, d.getenv, view.Lang)
}
