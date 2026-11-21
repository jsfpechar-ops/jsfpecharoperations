package guest

// Brief 1723: guest_form_new, guest_form_edit, guest_remove_confirm, guest_remove,
// guest_form_relang (App/app/routes/guest.py 2081–2362). Shell helpers: OpenLink,
// GuestLanguage, GuestLink, LangQuery, WithLang, WritePage (brief 1720a).

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	formSubmitSent     = "sent"
	formPagesHardening = "no-store"
)

//go:embed templates/form_content.tmpl templates/remove_content.tmpl
var formPagesFS embed.FS

var formPagesFormSet = func() *template.Template {
	base := template.Must(template.New("guest.base").Funcs(tplFuncs).ParseFS(templateFS, "templates/base.tmpl", "templates/host_fragment.tmpl"))
	return template.Must(base.ParseFS(formPagesFS, "templates/form_content.tmpl"))
}()

var formPagesRemoveSet = func() *template.Template {
	base := template.Must(template.New("guest.base").Funcs(tplFuncs).ParseFS(templateFS, "templates/base.tmpl", "templates/host_fragment.tmpl"))
	return template.Must(base.ParseFS(formPagesFS, "templates/remove_content.tmpl"))
}()

// RegisterFormPages wires the five guest form routes (dormant until UBYHOST_GO_PATHS).
func formRequestLanguage(r *http.Request) string {
	if v := r.URL.Query().Get("lang"); v != "" {
		return GuestLanguage(v)
	}
	if c, err := r.Cookie(LangCookie); err == nil {
		return GuestLanguage(c.Value)
	}
	return GuestLanguage(AcceptLanguage(r.Header.Get("Accept-Language")))
}

func RegisterFormPages(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := formPageDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /l/{token}/{reservation_id}/new", wrap("guest_form_new", formPageHandler(d, "new")))
	mux.Handle("GET /l/{token}/{reservation_id}/edit/{guest_id}", wrap("guest_form_edit", formPageHandler(d, "edit")))
	mux.Handle("GET /l/{token}/{reservation_id}/remove/{guest_id}", wrap("guest_remove_confirm", removeConfirmHandler(d)))
	mux.Handle("POST /l/{token}/{reservation_id}/remove/{guest_id}", wrap("guest_remove", WithPOSTCSRF(getenv, now, removePostHandler(d))))
	mux.Handle("POST /l/{token}/{reservation_id}/relang", wrap("guest_form_relang", WithPOSTCSRF(getenv, now, relangHandler(d))))
}

type formPageDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

func (d formPageDeps) shell() shellDeps {
	return shellDeps{pool: d.pool, getenv: d.getenv, now: d.now}
}

type formResRow struct {
	id             int64
	apartmentID    int64
	ownerUserID    int64
	dateFrom       string
	dateTo         string
	declaredGuests *int64
	overrideGuests *int64
	reducedGuests  *int64
}

type formGuestRow struct {
	id           int64
	submitState  string
	restrictedAt string
	stayFrom     string
	stayTo       string
	firstName    string
	surname      string
	signaturePNG string
	nationality  string
}

type formCountryOption struct {
	Code  string
	Label string
}

type formCountryGroup struct {
	Key     string
	Options []formCountryOption
}

type formPurposeOption struct {
	Code  string
	Label string
}

type formView struct {
	Page
	WrapClass                string
	ReservationID            int64
	GuestID                  int64
	PersonName               string
	BackURL                  string
	DatesLink                string
	HideBack                 bool
	DupWarnings              []dupWarning
	PersonNumber             int
	ExpectedPeople           int
	StayFromLabel            string
	StayToLabel              string
	NightsLabel              string
	StayFromValue            string
	StayToValue              string
	SaveActionLabel          string
	LangRelangURL            string
	DraftURL                 string
	DraftFields              string
	DraftOwned               string
	DraftRestored            bool
	StartStep                int
	LoadSignatureJS          bool
	Values                   map[string]string
	GuestFields              map[string]string
	Issues                   []validation.Issue
	CountryGroups            []formCountryGroup
	Purposes                 []formPurposeOption
	SelectedPurpose          string
	Inpass                   string
	AskPartySize             bool
	JustSaved                bool
	OCRAvailable             bool
	RequirePassport          bool
	HasExistingPassportPhoto bool
	RuianSuggestURL          string
	Under15                  bool
	AdultSigner              bool
	PendingChildren          []formChildEntry
	PendingChildrenNames     string
	SelectedSignForRole      string
	ChildSigners             []formChildEntry
	SelectedSigner           int64
	SelectedChildRole        string
	SignatureValue           string
	ResidenceCopiedFrom      string
	FeeNotice                bool
	FeeEstimate              bool
	FeePanel                 bool
	NoticeVersion            string
}

type dupWarning struct {
	Name string
	What string
}

func formPageHandler(d formPageDeps, mode string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := handleFormPage(r.Context(), d, w, r, mode); err != nil {
			log.Printf("guest form page: %v", err)
			http.Error(w, "server error", http.StatusInternalServerError)
		}
	}
}

func handleFormPage(ctx context.Context, d formPageDeps, w http.ResponseWriter, r *http.Request, mode string) error {
	if d.pool == nil {
		return errors.New("nil pool")
	}
	token := r.PathValue("token")
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return nil
	}
	lang := formRequestLanguage(r)
	apt, link, early := OpenLink(r, d.pool, token, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return nil
	}
	if formPagesAlertControllerMissing(apt) {
		formWriteUnavailable(w, r, lang, "controller_missing", http.StatusServiceUnavailable, link, nil)
		return nil
	}
	if requirePin(w, r, d.shell(), link, lang, apt) {
		return nil
	}
	res, ok := formPagesReservation(ctx, d.pool, apt, resID, r)
	if !ok {
		formWriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, nil)
		return nil
	}
	if formPagesRequireClaim(w, r, res, link, lang) {
		return nil
	}
	var guest *formGuestRow
	if mode == "edit" {
		gid, err := strconv.ParseInt(r.PathValue("guest_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return nil
		}
		owned := formPagesOwnedIDs(r, d.getenv)
		if !owned[gid] {
			formWriteUnavailable(w, r, lang, "not_yours", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
			return nil
		}
		guest, err = loadFormGuest(ctx, d.pool, gid, resID, d.getenv, d.now)
		if err != nil {
			return err
		}
		if guest == nil {
			formWriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, nil)
			return nil
		}
		if guest.submitState == formSubmitSent {
			formWriteUnavailable(w, r, lang, "already_filed", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
			return nil
		}
		if formPagesGuestLocked(guest, res) {
			formWriteUnavailable(w, r, lang, "form_locked", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
			return nil
		}
	}
	if mode == "new" {
		prog := formPagesProgress(ctx, d.pool, res)
		if prog.remaining != nil && *prog.remaining <= 0 {
			loc := GuestLink(link, resID, LangQuery(lang, ""))
			w.Header().Set("Cache-Control", formPagesHardening)
			http.Redirect(w, r, loc, http.StatusSeeOther)
			WithLang(w, d.getenv, lang)
			return nil
		}
	}
	view, err := buildFormView(ctx, d, r, apt, link, res, guest, lang, mode)
	if err != nil {
		return err
	}
	view.LoadSignatureJS = true
	view.WrapClass = "g-checkin-page"
	writeFormPage(w, r, view)
	WithLang(w, d.getenv, lang)
	return nil
}

func removeConfirmHandler(d formPageDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := handleRemoveConfirm(r.Context(), d, w, r); err != nil {
			log.Printf("guest remove confirm: %v", err)
			http.Error(w, "server error", http.StatusInternalServerError)
		}
	}
}

func handleRemoveConfirm(ctx context.Context, d formPageDeps, w http.ResponseWriter, r *http.Request) error {
	apt, link, res, guest, early, err := removalGuard(ctx, d, r, false)
	if err != nil {
		return err
	}
	if early != nil {
		early(w, r)
		return nil
	}
	lang := formRequestLanguage(r)
	name := strings.TrimSpace(guest.firstName + " " + guest.surname)
	view := formView{
		Page: Page{
			Lang:          lang,
			Token:         link,
			Facility:      Facility(apt),
			FacilityTone:  int(apt.ID % 10),
			LangURLs:      LangURLs(r, ""),
			CSRFToken:     formPagesCSRF(r),
			GuestEndonyms: GuestEndonyms,
			Host:          formPagesHost(ctx, d.pool, apt.ID),
		},
		ReservationID: res.id,
		GuestID:       guest.id,
		PersonName:    name,
		BackURL:       GuestLink(link, res.id, LangQuery(lang, "")),
	}
	writeRemovePage(w, r, view)
	WithLang(w, d.getenv, lang)
	return nil
}

func removePostHandler(d formPageDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := handleRemovePost(r.Context(), d, w, r); err != nil {
			log.Printf("guest remove: %v", err)
			http.Error(w, "server error", http.StatusInternalServerError)
		}
	}
}

func handleRemovePost(ctx context.Context, d formPageDeps, w http.ResponseWriter, r *http.Request) error {
	if err := r.ParseForm(); err != nil {
		return err
	}
	apt, link, res, guest, early, err := removalGuard(ctx, d, r, true)
	if err != nil {
		return err
	}
	if early != nil {
		early(w, r)
		return nil
	}
	lang := formRequestLanguage(r)
	guestID := guest.id
	resID := res.id
	cutoff := float64(d.now().Unix()) - float64(ubyport.SubmissionClaimTTL)
	tag, err := d.pool.Exec(ctx, `DELETE FROM guest WHERE id = $1 AND reservation_id = $2
		AND COALESCE(submit_state,'') <> $3 AND restricted_at IS NULL
		AND NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = $1 AND claimed_at >= $4)`,
		guestID, resID, formSubmitSent, cutoff)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		formWriteUnavailable(w, r, lang, "already_filed", http.StatusForbidden, link, nil)
		return nil
	}
	_, _ = d.pool.Exec(ctx, `UPDATE guest SET signed_for_guest_id = NULL, signed_for_role = NULL,
		signed_for_at = NULL, signed_for_wording = NULL WHERE signed_for_guest_id = $1 AND reservation_id = $2`,
		guestID, resID)
	if err := formPagesDeletePhoto(ctx, d.pool, guestID); err != nil {
		return err
	}
	_, _ = d.pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1,$2,$3,$4,$5)`,
		d.now().UTC(), "guest", "guest_removed_by_guest", fmt.Sprintf("guest=%d reservation=%d", guestID, resID), apt.ID)
	_ = formPagesSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, apt.ID, resID)
	owned := formPagesOwnedIDs(r, d.getenv)
	delete(owned, guestID)
	ids := make([]int64, 0, len(owned))
	for id := range owned {
		ids = append(ids, id)
	}
	formPagesSetOwnedCookie(w, d.getenv, ids)
	loc := GuestLink(link, resID, LangQuery(lang, "&removed=1"))
	w.Header().Set("Cache-Control", formPagesHardening)
	http.Redirect(w, r, loc, http.StatusSeeOther)
	WithLang(w, d.getenv, lang)
	return nil
}

func relangHandler(d formPageDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := handleRelang(r.Context(), d, w, r); err != nil {
			log.Printf("guest relang: %v", err)
			http.Error(w, "server error", http.StatusInternalServerError)
		}
	}
}

func handleRelang(ctx context.Context, d formPageDeps, w http.ResponseWriter, r *http.Request) error {
	if err := r.ParseForm(); err != nil {
		return err
	}
	token := r.PathValue("token")
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return nil
	}
	lang := formRequestLanguage(r)
	apt, link, early := OpenLink(r, d.pool, token, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return nil
	}
	if requirePin(w, r, d.shell(), link, lang, apt) {
		return nil
	}
	res, ok := formPagesReservation(ctx, d.pool, apt, resID, r)
	if !ok {
		formWriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, nil)
		return nil
	}
	if formPagesThrottlePost(w, r, d, link, "guest_relang", lang) {
		return nil
	}
	if formPagesRequireClaim(w, r, res, link, lang) {
		return nil
	}
	form := postFormFields(r)
	var guest *formGuestRow
	if raw := strings.TrimSpace(form["guest_id"]); raw != "" {
		if gid, err := strconv.ParseInt(raw, 10, 64); err == nil {
			owned := formPagesOwnedIDs(r, d.getenv)
			if owned[gid] {
				guest, err = loadFormGuest(ctx, d.pool, gid, resID, d.getenv, d.now)
				if err != nil {
					return err
				}
			}
		}
	}
	if guest != nil {
		if guest.submitState == formSubmitSent {
			formWriteUnavailable(w, r, lang, "already_filed", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
			return nil
		}
		if guest.restrictedAt != "" || formPagesGuestLocked(guest, res) {
			formWriteUnavailable(w, r, lang, "form_locked", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
			return nil
		}
	}
	raw := validation.GuestFormRaw(form, formPagesDefaultPurpose(apt))
	_ = validation.NormaliseGuest(raw, legalTodayForm(d.now))
	stayFrom, stayTo := lockedFormStayDates(res, guest)
	vals := map[string]string{
		"stay_from": stayFrom, "stay_to": stayTo,
		"party_size": strings.TrimSpace(form["party_size"]),
		"signature":  "", "legal_ack": "",
	}
	for _, f := range []string{"surname", "first_name", "doc_number", "visa_number", "res_street", "res_city"} {
		vals[f] = raw[f]
	}
	mode := "new"
	if guest != nil {
		mode = "edit"
	}
	view, err := buildFormView(ctx, d, r, apt, link, res, guest, lang, mode)
	if err != nil {
		return err
	}
	view.Values = vals
	view.StartStep = formPagesStartStep(form["_step"])
	view.LoadSignatureJS = true
	view.WrapClass = "g-checkin-page"
	writeFormPage(w, r, view)
	WithLang(w, d.getenv, lang)
	return nil
}

func removalGuard(ctx context.Context, d formPageDeps, r *http.Request, post bool) (*Apartment, string, formResRow, *formGuestRow, func(http.ResponseWriter, *http.Request), error) {
	lang := formRequestLanguage(r)
	token := r.PathValue("token")
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		return nil, "", formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) { http.NotFound(w, r) }, nil
	}
	guestID, err := strconv.ParseInt(r.PathValue("guest_id"), 10, 64)
	if err != nil {
		return nil, "", formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) { http.NotFound(w, r) }, nil
	}
	apt, link, early := OpenLink(r, d.pool, token, lang)
	if early != nil {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) { early.ServeHTTP(w, r) }, nil
	}
	if requirePin(httptest.NewRecorder(), r, d.shell(), link, lang, apt) {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			requirePin(w, r, d.shell(), link, lang, apt)
		}, nil
	}
	res, ok := formPagesReservation(ctx, d.pool, apt, resID, r)
	if !ok {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			formWriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, nil)
		}, nil
	}
	if post && guestPostLimited(ctx, d.pool, d.getenv, r, link, "guest_remove", d.now()) {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			formWriteUnavailable(w, r, lang, "rate_limited", http.StatusTooManyRequests, link, nil)
		}, nil
	}
	if formPagesRequireClaim(httptest.NewRecorder(), r, res, link, lang) {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, _ *http.Request) {}, nil
	}
	owned := formPagesOwnedIDs(r, d.getenv)
	if !owned[guestID] {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			formWriteUnavailable(w, r, lang, "not_yours", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
		}, nil
	}
	guest, err := loadFormGuest(ctx, d.pool, guestID, resID, d.getenv, d.now)
	if err != nil {
		return nil, "", formResRow{}, nil, nil, err
	}
	if guest == nil {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			formWriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, nil)
		}, nil
	}
	if guest.submitState == formSubmitSent {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			formWriteUnavailable(w, r, lang, "already_filed", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
		}, nil
	}
	if guest.restrictedAt != "" {
		return nil, link, formResRow{}, nil, func(w http.ResponseWriter, r *http.Request) {
			formWriteUnavailable(w, r, lang, "form_locked", http.StatusForbidden, link, map[string]string{"reservation_id": strconv.FormatInt(resID, 10)})
		}, nil
	}
	return apt, link, res, guest, nil, nil
}

type formProgress struct {
	filled    int
	expected  *int
	remaining *int
}

func formPagesProgress(ctx context.Context, pool *pgxpool.Pool, res formResRow) formProgress {
	live, _ := liveFormGuests(ctx, pool, res.id)
	exp := headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests)
	var rem *int
	if exp != nil {
		v := int(*exp) - live
		rem = &v
	}
	var ei *int
	if exp != nil {
		i := int(*exp)
		ei = &i
	}
	return formProgress{filled: live, expected: ei, remaining: rem}
}

func liveFormGuests(ctx context.Context, pool *pgxpool.Pool, resID int64) (int, error) {
	var n int
	err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, resID).Scan(&n)
	return n, err
}

func buildFormView(ctx context.Context, d formPageDeps, r *http.Request, apt *Apartment, link string, res formResRow, guest *formGuestRow, lang, mode string) (formView, error) {
	prog := formPagesProgress(ctx, d.pool, res)
	formPath := GuestLink(link, res.id, "/new")
	editing := false
	if guest != nil {
		formPath = GuestLink(link, res.id, "/edit/"+strconv.FormatInt(guest.id, 10))
		editing = true
	}
	back := formPagesBackURL(link, apt, res.id, lang, editing)
	saveKey := "guest_save_details"
	if guest != nil {
		saveKey = "guest_save_changes"
	} else if prog.expected != nil {
		if prog.remaining != nil && *prog.remaining <= 1 {
			saveKey = "submit_registration"
		} else if prog.remaining != nil {
			saveKey = "save_continue_next"
		}
	}
	stayFrom, stayTo := lockedFormStayDates(res, guest)
	privacy := GuestLink(link, 0, "/privacy"+LangQuery(lang, "&return_to="+url.QueryEscape(formPath+LangQuery(lang, ""))))
	view := formView{
		Page: Page{
			Lang:          lang,
			Token:         link,
			Facility:      Facility(apt),
			FacilityTone:  int(apt.ID % 10),
			LangURLs:      LangURLs(r, formPath),
			LangRelangURL: GuestLink(link, res.id, "/relang"),
			PrivacyURL:    privacy,
			CSRFToken:     formPagesCSRF(r),
			Host:          formPagesHost(ctx, d.pool, apt.ID),
			GuestEndonyms: GuestEndonyms,
		},
		ReservationID: res.id,
		BackURL:       back,
		DatesLink:     formPagesDatesLink(back, editing, formPagesCanPick(apt)),
		HideBack:      formPagesCanPick(apt) && !editing,
		PersonNumber:  prog.filled + 1,
		StayFromLabel: formPagesDateLabel(stayFrom, lang),
		StayToLabel:   formPagesDateLabel(stayTo, lang),
		NightsLabel:   formPagesNights(stayFrom, stayTo, lang),
		StayFromValue: stayFrom,
		StayToValue:   stayTo,

		StartStep: 0,
	}
	if guest != nil {
		view.GuestID = guest.id
	}
	if prog.expected != nil {
		view.ExpectedPeople = *prog.expected
	}
	p := Page{Lang: lang}
	view.SaveActionLabel = p.T(saveKey)
	if mode == "new" {
		dups, _ := formPagesDupWarnings(ctx, d.pool, res.id, formPagesOwnedIDs(r, d.getenv), lang)
		view.DupWarnings = dups
	}
	view.Values = map[string]string{"stay_from": stayFrom, "stay_to": stayTo}
	view.Inpass = "INPASS"
	view.NoticeVersion = formNoticeVersion(d.getenv)
	view.AskPartySize = prog.expected == nil && guest == nil
	view.RequirePassport = strings.EqualFold(strings.TrimSpace(apt.PassportPhotoPolicy), "required_foreign")
	groups, err := formCountryGroups(ctx, d.pool, lang)
	if err != nil {
		return view, err
	}
	view.CountryGroups = groups
	purposes, err := formPurposeOptions(ctx, d.pool, lang)
	if err != nil {
		return view, err
	}
	view.Purposes = purposes
	view.SelectedPurpose = formPagesDefaultPurpose(apt)
	if guest != nil {
		view.GuestFields = formGuestFieldMap(guest)
		view.SignatureValue = guest.signaturePNG
	}
	formPagesFillU15(ctx, d, &view, res, guest, r)
	view.SaveActionLabel = view.T(saveKey)
	return view, nil
}

func writeFormPage(w http.ResponseWriter, r *http.Request, v formView) {
	v.Page.GuestEndonyms = GuestEndonyms
	if v.SaveActionLabel == "" {
		v.SaveActionLabel = v.T("guest_save_details")
	}
	var buf strings.Builder
	if err := formPagesFormSet.ExecuteTemplate(&buf, "guest.base", v); err != nil {
		log.Printf("form page render: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	h.Set("Cache-Control", formPagesHardening)
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = io.Copy(w, strings.NewReader(buf.String()))
	}
}

func writeRemovePage(w http.ResponseWriter, r *http.Request, v formView) {
	v.Page.GuestEndonyms = GuestEndonyms
	var buf strings.Builder
	if err := formPagesRemoveSet.ExecuteTemplate(&buf, "guest.base", v); err != nil {
		log.Printf("remove page render: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	h.Set("Cache-Control", formPagesHardening)
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = io.Copy(w, strings.NewReader(buf.String()))
	}
}

func loadFormGuest(ctx context.Context, pool *pgxpool.Pool, id, resID int64, getenv func(string) string, now func() time.Time) (*formGuestRow, error) {
	var g formGuestRow
	var birthEnc, docEnc, visaEnc, streetEnc, cityEnc, sigEnc string
	err := pool.QueryRow(ctx, `SELECT id, COALESCE(submit_state,''), COALESCE(restricted_at::text,''),
		COALESCE(stay_from,''), COALESCE(stay_to,''), COALESCE(first_name,''), COALESCE(surname,''),
		COALESCE(signature_png,''), COALESCE(signature_png_enc,''), COALESCE(nationality,''),
		COALESCE(birth_date_enc,''), COALESCE(doc_number_enc,''), COALESCE(visa_number_enc,''),
		COALESCE(res_street_enc,''), COALESCE(res_city_enc,'')
		FROM guest WHERE id = $1 AND reservation_id = $2 AND archived_at IS NULL`, id, resID).
		Scan(&g.id, &g.submitState, &g.restrictedAt, &g.stayFrom, &g.stayTo, &g.firstName, &g.surname,
			&g.signaturePNG, &sigEnc, &g.nationality, &birthEnc, &docEnc, &visaEnc, &streetEnc, &cityEnc)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	_ = birthEnc
	_ = docEnc
	_ = visaEnc
	_ = streetEnc
	_ = cityEnc
	plain, err := decryptGuestField(getenv, now, sigEnc, g.signaturePNG)
	if err != nil {
		return nil, err
	}
	g.signaturePNG = plain
	return &g, nil
}

func lockedFormStayDates(res formResRow, guest *formGuestRow) (string, string) {
	if guest != nil && guest.stayFrom != "" && guest.stayTo != "" {
		return guest.stayFrom, guest.stayTo
	}
	return res.dateFrom, res.dateTo
}

func postFormFields(r *http.Request) map[string]string {
	out := map[string]string{}
	for k, v := range r.PostForm {
		if len(v) > 0 {
			out[k] = v[0]
		}
	}
	return out
}

// Portal hooks (briefs 1720b–1722 replace stubs with shared helpers).

func formPagesAlertControllerMissing(apt *Apartment) bool { return false }

func formPagesThrottlePost(w http.ResponseWriter, r *http.Request, d formPageDeps, token, kind, lang string) bool {
	if guestPostLimited(r.Context(), d.pool, d.getenv, r, token, kind, d.now()) {
		formWriteUnavailable(w, r, lang, "rate_limited", http.StatusTooManyRequests, token, nil)
		return true
	}
	return false
}

func formPagesReservation(ctx context.Context, pool *pgxpool.Pool, apt *Apartment, resID int64, r *http.Request) (formResRow, bool) {
	var row formResRow
	err := pool.QueryRow(ctx, `SELECT r.id, r.apartment_id, a.owner_user_id, r.date_from::text, r.date_to::text,
		r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND r.apartment_id = $2 AND r.status = 'active' AND r.archived_at IS NULL
		  AND COALESCE(r.source,'') <> 'demo' AND a.permalink_token = $3`,
		resID, apt.ID, apt.PermalinkToken).Scan(&row.id, &row.apartmentID, &row.ownerUserID, &row.dateFrom, &row.dateTo,
		&row.declaredGuests, &row.overrideGuests, &row.reducedGuests)
	if err != nil {
		return formResRow{}, false
	}
	return row, true
}

func formPagesRequireClaim(w http.ResponseWriter, r *http.Request, res formResRow, token, lang string) bool {
	return false
}

func formPagesOwnedIDs(r *http.Request, getenv func(string) string) map[int64]bool {
	out := map[int64]bool{}
	for _, id := range ownedGuestIDs(r, getenv) {
		out[id] = true
	}
	return out
}

func formPagesGuestLocked(g *formGuestRow, res formResRow) bool { return false }

func formPagesBackURL(token string, apt *Apartment, resID int64, lang string, editing bool) string {
	if editing {
		return GuestLink(token, resID, LangQuery(lang, ""))
	}
	return GuestLink(token, 0, LangQuery(lang, ""))
}

func formPagesDatesLink(back string, editing, canPick bool) string {
	if editing || !canPick {
		return ""
	}
	return back
}

func formPagesCanPick(apt *Apartment) bool { return false }

func formPagesDefaultPurpose(apt *Apartment) string {
	if apt != nil && strings.TrimSpace(apt.DefaultPurpose) != "" {
		return apt.DefaultPurpose
	}
	return "99"
}

func formPagesCSRF(r *http.Request) string { return formPagesCSRFToken() }

func formPagesCSRFToken() string { return "*" }

func formPagesHost(ctx context.Context, pool *pgxpool.Pool, aptID int64) HostContact {
	return HostContact{}
}

func formPagesStartStep(raw string) int {
	raw = strings.TrimSpace(raw)
	if raw == "" || len(raw) > 2 {
		return 0
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n < 0 {
		return 0
	}
	return n
}

func formPagesDateLabel(iso, lang string) string { return iso }

func formPagesNights(from, to, lang string) string { return "" }

func formPagesDupWarnings(ctx context.Context, pool *pgxpool.Pool, resID int64, owned map[int64]bool, lang string) ([]dupWarning, error) {
	return nil, nil
}

func formPagesDeletePhoto(ctx context.Context, pool *pgxpool.Pool, guestID int64) error { return nil }

func formPagesSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, aptID, resID int64) error {
	return nil
}

func legalTodayForm(now func() time.Time) time.Time {
	at := now()
	return time.Date(at.Year(), at.Month(), at.Day(), 0, 0, 0, 0, time.UTC)
}

func formPagesSetOwnedCookie(w http.ResponseWriter, getenv func(string) string, ids []int64) {
	rememberOwnedGuestIDs(w, getenv, ids)
}

// formWriteUnavailable is brief 1720a unavailable page with extra reservation_id hint.
func formWriteUnavailable(w http.ResponseWriter, r *http.Request, lang, code string, status int, token string, extra map[string]string) {
	p := Page{
		Lang:          GuestLanguage(lang),
		Token:         token,
		LangURLs:      LangURLs(r, ""),
		GuestEndonyms: GuestEndonyms,
		FlashError:    Page{Lang: lang}.T(code),
	}
	if extra != nil {
		if id := extra["reservation_id"]; id != "" {
			p.FlashError = Page{Lang: lang}.T(code, "reservation_id", id)
		}
	}
	WritePage(w, r, status, p, map[string]string{"Cache-Control": formPagesHardening})
}
