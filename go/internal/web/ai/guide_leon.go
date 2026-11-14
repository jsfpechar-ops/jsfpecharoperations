package ai

// The host's Leon (AI) switch pages of App/app/routes/guest_guide.py (brief
// 1446): GET and POST /apartments/{id}/leon (leon_page 125-145, leon_save
// 148-177). The wizard under /apartments/{id}/leon/setup is another file and
// another thread. Switching Leon on stores the terms version the host ticked;
// nothing here calls a model.

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func init() {
	guideAdd("GET", "/apartments/{id}/leon", (*guideServer).leonPage)
	guideAdd("POST", "/apartments/{id}/leon", (*guideServer).leonSave)
}

// guideValueCard is the data of partials/settings_value_card.html.
type guideValueCard struct{ Label, Value, Href, LinkLabel string }

// guideLeonData is the context of guide_leon.tmpl.
type guideLeonData struct {
	Apartment                              *guideApartment
	State                                  string
	Live                                   bool
	Warnings                               []string
	StateCard, VersionCard, AcceptedAtCard guideValueCard
	AcceptedByCard                         guideValueCard
}

// guideLeonUTC is _leon_utc: f"{value[:16].replace('T', ' ')} UTC", "" for none.
func guideLeonUTC(value string) string {
	if value == "" {
		return ""
	}
	return strings.ReplaceAll(guideTruncate(value, 16), "T", " ") + " UTC"
}

// leonPage is GET /apartments/{id}/leon.
func (s *guideServer) leonPage(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	ctx := r.Context()
	offered, err := s.leonOffered(ctx, a.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	if !offered {
		guideNotFound(w)
		return
	}
	progress, err := s.progress(ctx, a.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	state := guideLeonState(a, progress.Live)
	if state == "off" || state == "terms" {
		q.back(w, "/apartments/"+strconv.FormatInt(a.ID, 10)+"/leon/setup", hostweb.Flash{}, hostweb.Flash{})
		return
	}
	var by string
	if a.LeonTermsAcceptedBy != nil {
		err := s.pool.QueryRow(ctx, `SELECT COALESCE(email, '') FROM user_account WHERE id = $1`, *a.LeonTermsAcceptedBy).Scan(&by)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			guideFail(w, err)
			return
		}
	}
	t := func(key string) string { return guideCatalog.T(q.lang, key, nil) }
	data := guideLeonData{
		Apartment: a, State: state, Live: progress.Live,
		Warnings:       []string{"leon_page.warn1", "leon_page.warn2", "leon_page.warn3", "leon_page.warn4", "leon_page.warn5", "leon_page.warn6"},
		StateCard:      guideValueCard{Label: t("leon_page.title"), Value: t("leon_page.card." + state)},
		VersionCard:    guideValueCard{Label: t("leon_page.accepted_version"), Value: a.LeonTermsVersion, Href: "/guide#leon-terms", LinkLabel: t("leon_page.terms_link")},
		AcceptedAtCard: guideValueCard{Label: t("leon_page.accepted_at"), Value: guideLeonUTC(a.LeonTermsAcceptedAt)},
		AcceptedByCard: guideValueCard{Label: t("leon_page.accepted_by"), Value: by},
	}
	page := layout.Page{Title: t("leon_page.title") + " · " + a.InternalName + " · UbyHost", BodyKind: "settings", V2: true}
	s.render(w, q, "guide_leon", page, http.StatusOK, data)
}

// leonSave is POST /apartments/{id}/leon: switch Leon on after the host ticked
// the current terms, or off (always allowed).
func (s *guideServer) leonSave(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(a.ID, 10)
	page := "/apartments/" + idText + "/leon"
	action, _ := guideFormValue(r, "action")
	switch action {
	case "off":
		if err := s.setLeon(ctx, q, false, ""); err != nil {
			guideFail(w, err)
			return
		}
		q.back(w, page, q.flash("flash.guest_guide.leon_off", nil), hostweb.Flash{})
	case "on":
		offered, err := s.leonOffered(ctx, a.ID)
		if err != nil {
			guideFail(w, err)
			return
		}
		if !offered {
			guideNotFound(w)
			return
		}
		next, _ := guideFormValue(r, "next")
		setup := next == "setup"
		if terms, _ := guideFormValue(r, "terms"); terms != "1" {
			to := page
			if setup {
				to = "/apartments/" + idText + "/leon/setup/switch_on"
			}
			q.back(w, to, hostweb.Flash{}, q.flash("flash.error.leon_terms", nil))
			return
		}
		if err := s.setLeon(ctx, q, true, guideStamp(q.at)); err != nil {
			guideFail(w, err)
			return
		}
		to := page
		if setup {
			to = "/apartments/" + idText + "/leon/setup"
		}
		q.back(w, to, q.flash("flash.guest_guide.leon_on", nil), hostweb.Flash{})
	default:
		q.back(w, page, hostweb.Flash{}, hostweb.Flash{})
	}
}

// setLeon writes the switch and its audit row.
func (s *guideServer) setLeon(ctx context.Context, q *guideReq, on bool, at string) error {
	idText := strconv.FormatInt(q.apt, 10)
	if !on {
		if _, err := s.pool.Exec(ctx, `UPDATE apartment SET leon_enabled = 0 WHERE id = $1`, q.apt); err != nil {
			return err
		}
		return s.audit(ctx, q, "leon_switched_off", "apartment="+idText)
	}
	if _, err := s.pool.Exec(ctx, `UPDATE apartment SET leon_enabled = 1, leon_terms_version = $1, leon_terms_accepted_at = $2, leon_terms_accepted_by = $3 WHERE id = $4`,
		guideLeonTermsVersion, at, q.host.Account.ID, q.apt); err != nil {
		return err
	}
	return s.audit(ctx, q, "leon_terms_accepted", "apartment="+idText+" version="+guideLeonTermsVersion)
}
