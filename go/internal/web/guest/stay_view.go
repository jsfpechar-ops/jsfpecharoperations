package guest

import (
	"context"
	"net/http"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
)

// stayView is guest/stay.html (the claimed stay hub). The fee panel
// (_fee_pay.html) is not ported: follow-up brief, only when UBYHOST_STAY_FEE_GUEST_PAY is on.
type stayView struct {
	Page
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
		COALESCE(restricted_at::text,'')
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
		var first, surname, birth, nat, doc, visa, street, city, country, purpose, submit, restricted string
		if err := rows.Scan(&id, &first, &surname, &birth, &nat, &doc, &visa, &street, &city, &country, &purpose, &submit, &restricted); err != nil {
			return nil, 0, err
		}
		complete := validation.GuestIsComplete(validation.GuestRow{
			Surname: surname, FirstName: first, BirthDate: birth, Nationality: nat, DocNumber: doc,
			VisaNumber: visa, ResStreet: street, ResCity: city, ResCountry: country, Purpose: purpose,
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
				BirthDate:   birth,
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
func (d stayClaimDeps) renderStayPage(w http.ResponseWriter, r *http.Request, token, lang string, apt *Apartment, stay *scStay, row scClaim, mailEnabled bool) {
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
	view := stayView{
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
		Page:           page,
		StayFrom:       stay.dateFrom,
		StayTo:         stay.dateTo,
		CanPickOther:   canPickOtherStays(ctx, d.pool, apt, d.now),
		BackURL:        GuestLink(token, 0, "") + LangQuery(lang, ""),
		NotMineURL:     GuestLink(token, 0, "") + LangQuery(lang, ""),
		ClaimErrorText: claimErrorText(lang, r.URL.Query().Get("claim_error")),
		EmailMasked:    row.emailMasked,
		DeclaredGuests: declared,
		ActionURL:      guestPath(token, stay.id) + "/party" + langQuery(lang),
	}
	if apt != nil {
		view.City = apt.CityEn
	}
	d.access().renderPage(w, r, assignedSet, view, map[string]string{"Cache-Control": "no-store"})
}
