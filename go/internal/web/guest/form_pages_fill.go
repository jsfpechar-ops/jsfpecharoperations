package guest

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// formNoticeVersion is config.GUEST_NOTICE_VERSION.
func formNoticeVersion(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_GUEST_NOTICE_VERSION")); v != "" {
		return v
	}
	return "1.0"
}

func formGuestFieldMap(g *formGuestRow) map[string]string {
	if g == nil {
		return nil
	}
	return map[string]string{
		"first_name":  g.firstName,
		"surname":     g.surname,
		"nationality": g.nationality,
		"birth_date":  g.birthDate,
		"doc_number":  g.docNumber,
		"visa_number": g.visaNumber,
		"res_street":  g.resStreet,
		"res_city":    g.resCity,
		"res_country": g.resCountry,
		"purpose":     g.purpose,
		"note":        g.note,
	}
}

func formPagesFillU15(ctx context.Context, d formPageDeps, view *formView, res formResRow, guest *formGuestRow, r *http.Request) {
	var guestID int64
	if guest != nil {
		guestID = guest.id
	}
	signers, pending := formU15Lists(ctx, d.pool, res.id, guestID, formPagesOwnedIDs(r, d.getenv), d.getenv, d.now, res.dateFrom)
	view.PendingChildren = pending
	if len(pending) > 0 {
		names := make([]string, len(pending))
		for i, c := range pending {
			names[i] = c.Name
		}
		view.PendingChildrenNames = strings.Join(names, ", ")
	}
	view.ChildSigners = signers
	if guest != nil && guest.birthDate != "" {
		arrival := rowArrivalDate(guest.stayFrom, res.dateFrom)
		view.Under15 = validation.CertainlyUnderAge(guest.birthDate, arrival, guestcontract.UnderSignAge)
		view.AdultSigner = validation.CertainlyAtLeastAge(guest.birthDate, arrival, adultSignerAge)
	} else {
		view.AdultSigner = true
	}
}

func formU15Lists(ctx context.Context, pool *pgxpool.Pool, resID, guestID int64, owned map[int64]bool, getenv func(string) string, now func() time.Time, stayFrom string) (adults, pending []formChildEntry) {
	if len(owned) == 0 || pool == nil {
		return nil, nil
	}
	rows, err := pool.Query(ctx, `SELECT id, COALESCE(first_name,''), COALESCE(surname,''), COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
		COALESCE(signature_png,''), COALESCE(signature_png_enc,''), COALESCE(signed_for_guest_id,0), COALESCE(stay_from,'')
		FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`, resID)
	if err != nil {
		return nil, nil
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var first, surname, birthEnc, birthPlain, sigPlain, sigEnc, rowStayFrom string
		var signedFor int64
		if err := rows.Scan(&id, &first, &surname, &birthEnc, &birthPlain, &sigPlain, &sigEnc, &signedFor, &rowStayFrom); err != nil {
			return nil, nil
		}
		if !owned[id] || id == guestID {
			continue
		}
		name := strings.TrimSpace(first + " " + surname)
		birth := birthPlain
		if birthEnc != "" {
			if plain, err := decryptGuestField(getenv, now, birthEnc, birthPlain); err == nil {
				birth = plain
			}
		}
		sig := sigPlain
		if sigEnc != "" {
			if plain, err := decryptGuestField(getenv, now, sigEnc, sigPlain); err == nil {
				sig = plain
			}
		}
		arrival := rowArrivalDate(rowStayFrom, stayFrom)
		entry := formChildEntry{ID: id, Name: name}
		if validation.IsValidSignature(sig) && validation.CertainlyAtLeastAge(birth, arrival, adultSignerAge) {
			adults = append(adults, entry)
			continue
		}
		if signedFor == 0 && validation.CertainlyUnderAge(birth, arrival, guestcontract.UnderSignAge) {
			pending = append(pending, entry)
		}
	}
	return adults, pending
}

func formGuestUnder15OnStay(birth, stayFrom string) bool {
	from, ok := validation.ParseISODate(stayFrom)
	if !ok {
		return false
	}
	return validation.CertainlyUnderAge(birth, &from, guestcontract.UnderSignAge)
}

func formDisplayName(first, surname string) string {
	var parts []string
	for _, raw := range []string{first, surname} {
		for _, word := range strings.Fields(strings.TrimSpace(raw)) {
			r := []rune(strings.ToLower(word))
			if len(r) == 0 {
				continue
			}
			r[0] = []rune(strings.ToUpper(string(r[0])))[0]
			parts = append(parts, string(r))
		}
	}
	return strings.Join(parts, " ")
}

type formSameAddress struct {
	Name         string
	Nationality  string
	Country      string
	CountryLabel string
	City         string
	Street       string
}

// formSameAddressCandidate returns the most recent completed guest's permanent
// home address from the same browser device cookie for an opt-in checkbox on
// companion forms. It never pre-fills the inputs automatically.
func formSameAddressCandidate(ctx context.Context, pool *pgxpool.Pool, resID int64, owned map[int64]bool, lang string, getenv func(string) string, now func() time.Time) *formSameAddress {
	if len(owned) == 0 || pool == nil {
		return nil
	}
	rows, err := pool.Query(ctx, `SELECT id, COALESCE(first_name,''), COALESCE(surname,''),
		COALESCE(nationality,''),
		COALESCE(res_street,''), COALESCE(res_street_enc,''),
		COALESCE(res_city,''), COALESCE(res_city_enc,''),
		COALESCE(res_country,'')
		FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL AND filled_at IS NOT NULL
		ORDER BY id DESC`, resID)
	if err != nil {
		return nil
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var first, surname, nat, streetPlain, streetEnc, cityPlain, cityEnc, country string
		if err := rows.Scan(&id, &first, &surname, &nat, &streetPlain, &streetEnc, &cityPlain, &cityEnc, &country); err != nil {
			return nil
		}
		if !owned[id] {
			continue
		}
		street := strings.TrimSpace(streetPlain)
		if streetEnc != "" {
			if plain, err := decryptGuestField(getenv, now, streetEnc, streetPlain); err == nil {
				street = strings.TrimSpace(plain)
			}
		}
		city := strings.TrimSpace(cityPlain)
		if cityEnc != "" {
			if plain, err := decryptGuestField(getenv, now, cityEnc, cityPlain); err == nil {
				city = strings.TrimSpace(plain)
			}
		}
		country = strings.TrimSpace(country)
		if street == "" || city == "" || country == "" {
			continue
		}
		label := strings.TrimSpace(ubyport.CountryName(country, lang))
		if label == "" {
			label = country
		}
		return &formSameAddress{
			Name:         formDisplayName(first, surname),
			Nationality:  strings.ToUpper(strings.TrimSpace(nat)),
			Country:      strings.ToUpper(country),
			CountryLabel: label,
			City:         city,
			Street:       street,
		}
	}
	return nil
}
