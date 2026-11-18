package exports

// Brief 1704a: the reads of GET /housebook (routes/admin.py housebook_view),
// exported for go/internal/web/housebook. It reuses housebookGuests,
// housebookRow and archivedHousebookSQL, so the CSV and the page read the
// same guest rows; nothing else in this package changes.

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// HousebookRow is one row of housebook.housebook_rows as housebook.html reads
// it. DocNumber and VisaNumber are already masked as access.identifier_for
// does for a guest whose identity this request may not see.
type HousebookRow struct {
	GuestID, ApartmentID                            int64
	Apartment, StayFrom, StayTo, Surname, FirstName string
	BirthDate, Nationality, DocNumber, VisaNumber   string
	ResStreet, ResCity, ResCountry, PurposeCode     string
	Signed, Reported, ReportedAt                    string
}

// HousebookArchivedRow is one row of housebook.housebook_archived_rows.
type HousebookArchivedRow struct {
	GuestID, ApartmentID                            int64
	Apartment, StayFrom, StayTo, Surname, FirstName string
	Archived                                        string
}

// HousebookApartment is one row of access.apartments(request, "id, internal_name").
type HousebookApartment struct {
	ID   int64
	Name string
}

// HousebookPage is the data of housebook_view: the filters read from the
// query string, the rows and the property list of the signed-in workspace.
type HousebookPage struct {
	ApartmentID int64
	From, To    string
	Rows        []HousebookRow
	Archived    []HousebookArchivedRow
	Apartments  []HousebookApartment
}

// DateCZ is the date_cz filter (validation.fmt_date).
func DateCZ(v string) string { return dateCZ(v) }

// PurposeLabelCS is validation.purpose_label(code, "cs").
func PurposeLabelCS(code string) string { return purposeLabel(code) }

// maskIdentifier is access.mask_identifier: three bullets and the last three characters.
func maskIdentifier(v string) string {
	if v == "" {
		return ""
	}
	r := []rune(v)
	if len(r) <= 3 {
		return "•••"
	}
	return "•••" + string(r[len(r)-3:])
}

const housebookApartmentsSQL = `SELECT id, internal_name FROM apartment
	WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY internal_name`

// LoadHousebookPage reads the filters ?apartment=, ?from=, ?to= of r and the
// rows for h's workspace. Every query is scoped to that workspace; a request
// without one is an error, never "all hosts" (housebook.py's "? IS NULL OR").
func LoadHousebookPage(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, h *session.Host, r *http.Request) (*HousebookPage, error) {
	owner := ownerID(h)
	if owner == nil {
		return nil, errors.New("house book without a workspace owner")
	}
	d := deps{pool: pool, getenv: getenv}
	p := &HousebookPage{ApartmentID: queryInt(r, "apartment"), From: queryDate(r, "from"), To: queryDate(r, "to")}
	guests, err := housebookGuests(ctx, d, owner, p.ApartmentID, p.From, p.To)
	if err != nil {
		return nil, err
	}
	for _, g := range guests {
		f, err := housebookRow(ctx, d, g)
		if err != nil {
			return nil, err
		}
		id := g.int("id")
		visible := identityVisible(h, &id)
		doc, visa := f[8], f[9]
		if !visible {
			doc, visa = maskIdentifier(doc), maskIdentifier(visa)
		}
		p.Rows = append(p.Rows, HousebookRow{
			GuestID: id, ApartmentID: g.int("apartment_id"),
			Apartment: f[0], StayFrom: f[2], StayTo: f[3], Surname: f[4], FirstName: f[5],
			BirthDate: f[6], Nationality: f[7], DocNumber: doc, VisaNumber: visa,
			ResStreet: g.str("res_street"), ResCity: g.str("res_city"), ResCountry: strings.ToUpper(g.str("res_country")),
			PurposeCode: g.str("purpose"), Signed: f[13], Reported: f[14], ReportedAt: f[15],
		})
	}
	archived, _, err := queryRows(ctx, pool, archivedHousebookSQL, owner)
	if err != nil {
		return nil, err
	}
	for _, g := range archived {
		if p.ApartmentID != 0 && g.int("apartment_id") != p.ApartmentID {
			continue
		}
		if err := hydrate(getenv, g); err != nil {
			return nil, err
		}
		p.Archived = append(p.Archived, HousebookArchivedRow{
			GuestID: g.int("id"), ApartmentID: g.int("apartment_id"), Apartment: g.str("internal_name"),
			StayFrom: orStr(g.str("stay_from"), g.str("res_from")), StayTo: orStr(g.str("stay_to"), g.str("res_to")),
			Surname: g.str("surname"), FirstName: g.str("first_name"), Archived: g.str("archived_at"),
		})
	}
	rows, err := pool.Query(ctx, housebookApartmentsSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var a HousebookApartment
		if err := rows.Scan(&a.ID, &a.Name); err != nil {
			return nil, err
		}
		p.Apartments = append(p.Apartments, a)
	}
	return p, rows.Err()
}
