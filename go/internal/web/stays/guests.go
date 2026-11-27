package stays

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// progGuest is one guest row for reservation_progress (calendar guestRow).
type progGuest struct {
	id                 int64
	nationality        string
	submitState        string
	manualFiledAt      string
	submittedAt        string
	submittedRef       string
	identityVerifiedAt string
	firstName, surname string
	isLead             bool
	row                validation.GuestRow
}

type guestFields struct {
	getenv func(string) string
	keys   *secure.MultiFernet
}

func (f *guestFields) value(plain, token string) (string, error) {
	if token == "" {
		return plain, nil
	}
	if f.keys == nil {
		keys, err := secure.LoadDataKeys(f.getenv)
		if err != nil {
			return "", err
		}
		f.keys = keys
	}
	b, err := f.keys.Decrypt(token, 0, time.Now())
	return string(b), err
}

// loadProgGuests reads live guests for the given stays in one query.
func loadProgGuests(ctx context.Context, pool *pgxpool.Pool, ids []int64, getenv func(string) string) (map[int64][]progGuest, error) {
	out := map[int64][]progGuest{}
	if len(ids) == 0 {
		return out, nil
	}
	fields := &guestFields{getenv: getenv}
	rows, err := pool.Query(ctx,
		`SELECT g.id, g.reservation_id, COALESCE(g.nationality,''), COALESCE(g.submit_state,''),
		COALESCE(g.manual_filed_at,''), COALESCE(g.submitted_at,''),
		COALESCE(NULLIF(g.filled_at,''), NULLIF(g.updated_at,''), NULLIF(g.created_at,''), ''),
		COALESCE(g.identity_verified_at,''),
		COALESCE(g.stay_from,''), COALESCE(g.stay_to,''),
		COALESCE(g.surname,''), COALESCE(g.first_name,''), COALESCE(g.is_lead,0) != 0,
		COALESCE(g.res_country,''), COALESCE(g.purpose,''), COALESCE(g.note,''),
		COALESCE(g.doc_number,''), COALESCE(g.doc_number_enc,''),
		COALESCE(g.visa_number,''), COALESCE(g.visa_number_enc,''),
		COALESCE(g.birth_date,''), COALESCE(g.birth_date_enc,''),
		COALESCE(g.res_street,''), COALESCE(g.res_street_enc,''),
		COALESCE(g.res_city,''), COALESCE(g.res_city_enc,''),
		COALESCE(g.signature_png,''), COALESCE(g.signature_png_enc,'')
		FROM guest g
		WHERE g.reservation_id = ANY($1) AND g.archived_at IS NULL
		ORDER BY g.reservation_id, g.is_lead DESC, g.id`, ids)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var g progGuest
		var resID int64
		var stayFrom, stayTo, resCountry, purpose, note string
		var docP, docE, visaP, visaE, birthP, birthE, streetP, streetE, cityP, cityE, sigP, sigE string
		if err := rows.Scan(&g.id, &resID, &g.nationality, &g.submitState, &g.manualFiledAt,
			&g.submittedAt, &g.submittedRef, &g.identityVerifiedAt, &stayFrom, &stayTo,
			&g.surname, &g.firstName, &g.isLead,
			&resCountry, &purpose, &note,
			&docP, &docE, &visaP, &visaE, &birthP, &birthE, &streetP, &streetE, &cityP, &cityE,
			&sigP, &sigE); err != nil {
			return nil, err
		}
		pairs := [][2]string{{docP, docE}, {visaP, visaE}, {birthP, birthE}, {streetP, streetE}, {cityP, cityE}, {sigP, sigE}}
		vals := make([]string, len(pairs))
		for i, p := range pairs {
			v, err := fields.value(p[0], p[1])
			if err != nil {
				return nil, err
			}
			vals[i] = v
		}
		g.row = validation.GuestRow{
			Surname: g.surname, FirstName: g.firstName, BirthDate: vals[2], Nationality: g.nationality,
			DocNumber: vals[0], VisaNumber: vals[1], ResStreet: vals[3], ResCity: vals[4],
			ResCountry: resCountry, Purpose: purpose, Note: note,
			StayFrom: stayFrom, StayTo: stayTo, SignaturePNG: vals[5],
		}
		out[resID] = append(out[resID], g)
	}
	return out, rows.Err()
}

func displayGuests(gs []progGuest) []Guest {
	out := make([]Guest, 0, len(gs))
	for _, g := range gs {
		out = append(out, Guest{FirstName: g.firstName, Surname: g.surname, IsLead: g.isLead})
	}
	return out
}
