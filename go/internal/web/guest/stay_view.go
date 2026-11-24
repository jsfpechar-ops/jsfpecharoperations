package guest

import (
	"context"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"net/http"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

// stayView is guest/stay.html (the claimed stay hub). The fee panel
// (_fee_pay.html) is not ported: follow-up brief, only when UBYHOST_STAY_FEE_GUEST_PAY is on.
type stayView struct {
	Page
	GuideLive        bool
	DupWarnings      []dupWarning
	StayFrom, StayTo string
	CanPickOther     bool
	BackURL          string
	PartyError       bool
	JustRemoved      bool
	JustSaved        bool
	JustReported     bool
	HasExpected      bool
	Expected         int
	Filled           int
	HasRemaining     bool
	DoorCode         *doorCodeCard
	Remaining        int
	Percent          int
	CanRaiseParty    bool
	MailEnabled      bool
	ClaimEmailMasked string
	HostMessageURL   string
	Base, LangQ      string
	PartyURL         string
	AnotherURL       string
	NewURL           string
	People           []stayPerson
	Mine, Others     []stayPerson
}

func (v stayView) GetLang() string { return v.Lang }

type stayPersonSummary struct {
	Nationality, BirthDate, DocNumber, Purpose, Residence string
}

// stayPerson is guest.py _person_row.
type stayPerson struct {
	Index                        int
	ID                           int64
	Mine, Complete, Locked, Sent bool
	Removable                    bool
	Name                         string
	Summary                      *stayPersonSummary
}

// stayPeople is guest.py _person_row for each guest of the stay, plus the
// count of people filled (complete or filed).
func (d stayClaimDeps) stayPeople(ctx context.Context, r *http.Request, stay *scStay, lang string) ([]stayPerson, int, error) {
	rows, err := d.pool.Query(ctx, `SELECT id, COALESCE(first_name,''), COALESCE(surname,''), COALESCE(birth_date::text,''),
		COALESCE(nationality,''), COALESCE(doc_number,''), COALESCE(visa_number,''), COALESCE(res_street,''),
		COALESCE(res_city,''), COALESCE(res_country,''), COALESCE(purpose,''), COALESCE(submit_state,''),
		COALESCE(restricted_at::text,''), COALESCE(signature_png,'')
		FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY is_lead DESC, id`, stay.id)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	owned := formPagesOwnedIDs(r, d.getenv)
	today := d.now()
	var out []stayPerson
	filled := 0
	for rows.Next() {
		var id int64
		var first, surname, birth, nat, doc, visa, street, city, country, purpose, submit, restricted, sig string
		if err := rows.Scan(&id, &first, &surname, &birth, &nat, &doc, &visa, &street, &city, &country, &purpose, &submit, &restricted, &sig); err != nil {
			return nil, 0, err
		}
		complete := validation.GuestIsComplete(validation.GuestRow{
			Surname: surname, FirstName: first, BirthDate: birth, Nationality: nat, DocNumber: doc,
			VisaNumber: visa, ResStreet: street, ResCity: city, ResCountry: country, Purpose: purpose,
			SignaturePNG: sig,
		}, stay.dateFrom, stay.dateTo, today)
		sent := submit == formSubmitSent
		mine := owned[id]
		p := stayPerson{
			Index: len(out) + 1, ID: id, Mine: mine, Complete: complete, Sent: sent,
			Locked:    sent || restricted != "",
			Removable: mine && !sent && restricted == "",
		}
		if mine {
			p.Name = strings.TrimSpace(first + " " + surname)
			docOut := doc
			if docOut == "INPASS" {
				docOut = ""
			}
			p.Summary = &stayPersonSummary{
				Nationality: ubyport.CountryName(nat, lang),
				BirthDate:   validation.DisplayBirthDate(birth, today),
				DocNumber:   docOut,
				Purpose:     validationi18n.PurposeLabel(purpose, lang),
				Residence:   joinNonEmpty(", ", street, city, country),
			}
		}
		if complete || sent {
			filled++
		}
		out = append(out, p)
	}
	return out, filled, rows.Err()
}

// stayGuestSelect lists the columns stayPeople reads: plain and encrypted pairs, as reporting.guest_dict does.
const stayGuestSelect = `id, COALESCE(first_name,''), COALESCE(surname,''), COALESCE(nationality,''),
	COALESCE(birth_date::text,''), COALESCE(birth_date_enc,''), COALESCE(doc_number,''), COALESCE(doc_number_enc,''),
	COALESCE(visa_number,''), COALESCE(visa_number_enc,''), COALESCE(res_street,''), COALESCE(res_street_enc,''),
	COALESCE(res_city,''), COALESCE(res_city_enc,''), COALESCE(res_country,''), COALESCE(purpose,''),
	COALESCE(note,''), COALESCE(stay_from::text,''), COALESCE(stay_to::text,''), COALESCE(submit_state,''),
	COALESCE(restricted_at::text,''), COALESCE(signature_png,''), COALESCE(signature_png_enc,'')`

// stayGuestCols is one row of stayGuestSelect, still encrypted where the column is.
type stayGuestCols struct {
	ID                                       int64
	First, Surname, Nat                      string
	BirthP, BirthE, DocP, DocE, VisaP, VisaE string
	StreetP, StreetE, CityP, CityE           string
	Country, Purpose                         string
	Note, StayFrom, StayTo                   string
	Submit, Restricted                       string
	SigP, SigE                               string
}

func (c *stayGuestCols) scanArgs() []any {
	return []any{&c.ID, &c.First, &c.Surname, &c.Nat, &c.BirthP, &c.BirthE, &c.DocP, &c.DocE, &c.VisaP, &c.VisaE,
		&c.StreetP, &c.StreetE, &c.CityP, &c.CityE, &c.Country, &c.Purpose, &c.Note, &c.StayFrom, &c.StayTo,
		&c.Submit, &c.Restricted, &c.SigP, &c.SigE}
}

// validationRow decrypts the encrypted columns (plain wins when there is no token) into the row GuestIsComplete reads.
func (c stayGuestCols) validationRow(getenv func(string) string, now func() time.Time) (validation.GuestRow, error) {
	row := validation.GuestRow{Surname: c.Surname, FirstName: c.First, Nationality: c.Nat, ResCountry: c.Country,
		Purpose: c.Purpose, Note: c.Note, StayFrom: c.StayFrom, StayTo: c.StayTo}
	for _, p := range []struct {
		token, plain string
		dst          *string
	}{{c.BirthE, c.BirthP, &row.BirthDate}, {c.DocE, c.DocP, &row.DocNumber}, {c.VisaE, c.VisaP, &row.VisaNumber},
		{c.StreetE, c.StreetP, &row.ResStreet}, {c.CityE, c.CityP, &row.ResCity}, {c.SigE, c.SigP, &row.SignaturePNG}} {
		v, err := decryptGuestField(getenv, now, p.token, p.plain)
		if err != nil {
			return row, err
		}
		*p.dst = v
	}
	return row, nil
}

func joinNonEmpty(sep string, parts ...string) string {
	var keep []string
	for _, p := range parts {
		if p != "" {
			keep = append(keep, p)
		}
	}
	return strings.Join(keep, sep)
}

// renderStayPage writes guest/stay.html for a claimed stay (stay_overview).
func (d stayClaimDeps) renderStayPage(w http.ResponseWriter, r *http.Request, token, lang string, apt *Apartment, stay *scStay, row scClaim, mailEnabled bool, door *doorcodes.Shown) {
	ctx := r.Context()
	page := d.access().page(ctx, r, token, lang, apt)
	people, filled, err := d.stayPeople(ctx, r, stay, lang)
	if err != nil {
		scError(w, err)
		return
	}
	csrf, err := mintGuestPageCSRF(w, r, d.getenv, d.now())
	if err != nil {
		scError(w, err)
		return
	}
	page.CSRFToken = csrf
	base := guestPath(token, stay.id)
	langQ := langQuery(lang)
	guideLive := d.guideLive(ctx, apt)
	dups, _ := formPagesDupWarnings(ctx, d.pool, stay.id, formPagesOwnedIDs(r, d.getenv), lang)
	view := stayView{
		GuideLive:        guideLive,
		DupWarnings:      dups,
		Page:             page,
		StayFrom:         stay.dateFrom,
		StayTo:           stay.dateTo,
		CanPickOther:     canPickOtherStays(ctx, d.pool, apt, d.now),
		BackURL:          GuestLink(token, 0, "") + LangQuery(lang, ""),
		ClaimEmailMasked: row.emailMasked,
		MailEnabled:      mailEnabled,
		CanRaiseParty:    stay.override == nil,
		Base:             base,
		LangQ:            langQ,
		PartyURL:         base + "/party" + langQ,
		AnotherURL:       base + "/another" + langQ,
		NewURL:           base + "/new" + langQ,
		People:           people,
	}
	q := r.URL.Query()
	view.PartyError = q.Get("party_error") == "1"
	view.JustRemoved = q.Get("removed") == "1"
	view.JustSaved = q.Get("saved") == "1"
	anySent := false
	for _, p := range people {
		if p.Mine {
			view.Mine = append(view.Mine, p)
			anySent = anySent || p.Sent
		} else {
			view.Others = append(view.Others, p)
		}
	}
	view.JustReported = view.JustSaved && anySent
	view.DoorCode = doorCodeCardFrom(door)
	if exp := headcount.Expected(stay.override, stay.declared, stay.leadReduced); exp != nil {
		view.HasExpected = true
		view.Expected = int(*exp)
		view.Filled = filled
		view.HasRemaining = true
		view.Remaining = view.Expected - filled
		if view.Expected > 0 {
			view.Percent = (200*filled + view.Expected) / (2 * view.Expected)
		}
	}
	if apt != nil {
		view.HostMessageURL = hostMessageURL(apt, hostContact(ctx, d.pool, apt))
	}
	d.access().renderPage(w, r, staySet, view, map[string]string{"Cache-Control": "no-store"})
}

// assignedView is guest/assigned.html.
type assignedView struct {
	Page
	StayFrom, StayTo string
	City             string
	CanPickOther     bool
	BackURL          string
	NotMineURL       string
	ClaimErrorText   string
	EmailMasked      string
	DeclaredGuests   int64
	ActionURL        string
	RequireTurnstile bool
	TurnstileSiteKey string
	ClaimLastSent    string
}

func (v assignedView) GetLang() string { return v.Lang }

// renderAssignedPage writes guest/assigned.html (stay_overview, mail on, device not holding the claim).
func (d stayClaimDeps) renderAssignedPage(w http.ResponseWriter, r *http.Request, token, lang string, apt *Apartment, stay *scStay, row scClaim) {
	ctx := r.Context()
	page := d.access().page(ctx, r, token, lang, apt)
	csrf, err := mintGuestPageCSRF(w, r, d.getenv, d.now())
	if err != nil {
		scError(w, err)
		return
	}
	page.CSRFToken = csrf
	declared := int64(1)
	if row.declaredGuests != nil && *row.declaredGuests > 0 {
		declared = *row.declaredGuests
	}
	view := assignedView{
		ClaimLastSent:    d.claimLastSent(ctx, stay.id),
		Page:             page,
		StayFrom:         stay.dateFrom,
		StayTo:           stay.dateTo,
		CanPickOther:     canPickOtherStays(ctx, d.pool, apt, d.now),
		BackURL:          GuestLink(token, 0, "") + LangQuery(lang, ""),
		NotMineURL:       GuestLink(token, 0, "") + LangQuery(lang, ""),
		ClaimErrorText:   claimErrorText(lang, r.URL.Query().Get("claim_error")),
		EmailMasked:      row.emailMasked,
		DeclaredGuests:   declared,
		ActionURL:        guestPath(token, stay.id) + "/party" + langQuery(lang),
		RequireTurnstile: turnstile.Required(d.getenv),
		TurnstileSiteKey: turnstile.PageSiteKey(d.getenv),
	}
	if apt != nil {
		view.City = apt.CityEn
	}
	d.access().renderPage(w, r, assignedSet, view, map[string]string{"Cache-Control": "no-store"})
}

// doorCodeCard is what the #door-code card shows (Python door_codes.view).
// State is issued, failed or preparing; waiting and delayed show the preparing text.
type doorCodeCard struct {
	State      string
	PIN        string
	Checkin    string
	Checkout   string
	FirstUseBy string
}

func doorCodeCardFrom(s *doorcodes.Shown) *doorCodeCard {
	if s == nil {
		return nil
	}
	switch s.State {
	case "issued":
		return &doorCodeCard{State: "issued", PIN: s.PIN, Checkin: s.Checkin, Checkout: s.Checkout, FirstUseBy: s.FirstUseBy}
	case "failed":
		return &doorCodeCard{State: "failed"}
	}
	return &doorCodeCard{State: "preparing"}
}

// guideLive is guest.py _guide_is_live: the stay's guide link shows only once
// the host's guide is live. A guide error hides the link, never the stay page.
func (d stayClaimDeps) guideLive(ctx context.Context, apt *Apartment) bool {
	if apt == nil {
		return false
	}
	env := ai.HavelEnv(func(k string) (string, bool) { v := d.getenv(k); return v, v != "" })
	items, err := ai.LeonStore{HavelStore: ai.HavelStore{Pool: d.pool, Env: env}}.Items(ctx, apt.ID)
	if err != nil {
		return false
	}
	return ai.LeonProgressOf(items).Live
}

// claimLastSent is the day the assigned page shows as the last claim mail sent
// to this stay (guest.py assigned: MAX(sent_at) over the claim kinds). Empty when none.
func (d stayClaimDeps) claimLastSent(ctx context.Context, stayID int64) string {
	var day *string
	err := d.pool.QueryRow(ctx, `SELECT MAX(sent_at)::date::text FROM email_outbox
		WHERE reservation_id = $1 AND kind IN ('claim', 'claim_resend') AND sent_at IS NOT NULL`, stayID).Scan(&day)
	if err != nil || day == nil {
		return ""
	}
	return *day
}
