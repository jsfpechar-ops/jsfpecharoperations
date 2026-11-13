package invoices

// The lead guest of a stay as the invoice buyer's suggestion: routes/invoices.py
// _lead_guest, _guest_buyer_values, _merge_guest_fill, _drop_guest_suggestion.
// The guest's address is personal data: it is read only for the host who owns
// the stay, decrypted in memory, and never logged.

import (
	"context"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// guestBuyer is _guest_buyer_values for one guest.
type guestBuyer struct {
	Name, Street, City, Country string
}

// values are the buyer_* slots a guest can fill, in Python's key order.
func (g guestBuyer) values() [][2]string {
	return [][2]string{
		{"buyer_name", g.Name}, {"buyer_street", g.Street}, {"buyer_city", g.City}, {"buyer_country", g.Country},
	}
}

// decrypter reads a plain column or its *_enc twin the way db._hydrate does.
type decrypter struct {
	getenv func(string) string
	keys   *secure.MultiFernet
	at     time.Time
}

func (d *decrypter) value(plain, token string) (string, error) {
	if token == "" {
		return plain, nil
	}
	if d.keys == nil {
		keys, err := secure.LoadDataKeys(d.getenv)
		if err != nil {
			return "", err
		}
		d.keys = keys
	}
	b, err := d.keys.Decrypt(token, 0, d.at)
	return string(b), err
}

// leadGuest is _lead_guest: the lowest-id complete guest on the stay, or nil.
func leadGuest(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, s *stay, at time.Time) (*guestBuyer, error) {
	rows, err := pool.Query(ctx,
		`SELECT COALESCE(surname,''), COALESCE(first_name,''), COALESCE(nationality,''), COALESCE(res_country,''),
		        COALESCE(purpose,''), COALESCE(note,''), COALESCE(stay_from,''), COALESCE(stay_to,''),
		        COALESCE(doc_number,''), COALESCE(doc_number_enc,''), COALESCE(visa_number,''), COALESCE(visa_number_enc,''),
		        COALESCE(birth_date,''), COALESCE(birth_date_enc,''), COALESCE(res_street,''), COALESCE(res_street_enc,''),
		        COALESCE(res_city,''), COALESCE(res_city_enc,''), COALESCE(signature_png,''), COALESCE(signature_png_enc,'')
		 FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id ASC`, s.ReservationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	dec := &decrypter{getenv: getenv, at: at}
	today := time.Date(at.Year(), at.Month(), at.Day(), 0, 0, 0, 0, time.UTC)
	for rows.Next() {
		var surname, first, nationality, resCountry, purpose, note, stayFrom, stayTo string
		var docP, docE, visaP, visaE, birthP, birthE, streetP, streetE, cityP, cityE, sigP, sigE string
		if err := rows.Scan(&surname, &first, &nationality, &resCountry, &purpose, &note, &stayFrom, &stayTo,
			&docP, &docE, &visaP, &visaE, &birthP, &birthE, &streetP, &streetE, &cityP, &cityE, &sigP, &sigE); err != nil {
			return nil, err
		}
		var vals [6]string
		for i, p := range [6][2]string{{docP, docE}, {visaP, visaE}, {birthP, birthE}, {streetP, streetE}, {cityP, cityE}, {sigP, sigE}} {
			if vals[i], err = dec.value(p[0], p[1]); err != nil {
				return nil, err
			}
		}
		row := validation.GuestRow{
			Surname: surname, FirstName: first, BirthDate: vals[2], Nationality: nationality,
			DocNumber: vals[0], VisaNumber: vals[1], ResStreet: vals[3], ResCity: vals[4],
			ResCountry: resCountry, Purpose: purpose, Note: note, StayFrom: stayFrom, StayTo: stayTo, SignaturePNG: vals[5],
		}
		if !validation.GuestIsComplete(row, s.DateFrom, s.DateTo, today) {
			continue
		}
		return &guestBuyer{
			Name:    strings.TrimSpace(strings.TrimSpace(first) + " " + strings.TrimSpace(surname)),
			Street:  strings.TrimSpace(vals[3]),
			City:    strings.TrimSpace(vals[4]),
			Country: strings.TrimSpace(resCountry),
		}, nil
	}
	return nil, rows.Err()
}

// mergeGuestFill is _merge_guest_fill: copy guest address fields into blank
// buyer slots only.
func mergeGuestFill(state map[string]string, g *guestBuyer) {
	for _, kv := range g.values() {
		if kv[1] != "" && strings.TrimSpace(state[kv[0]]) == "" {
			state[kv[0]] = kv[1]
		}
	}
}

// dropGuestSuggestion is _drop_guest_suggestion (0843): blank buyer slots that
// still hold the guest's suggestion, so the register lookup can fill them.
func dropGuestSuggestion(state map[string]string, g *guestBuyer) {
	if g == nil {
		return
	}
	for _, kv := range g.values() {
		if kv[0] != "buyer_country" && kv[1] != "" && strings.TrimSpace(state[kv[0]]) == kv[1] {
			state[kv[0]] = ""
		}
	}
}
