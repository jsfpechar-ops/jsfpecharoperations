package stayfee

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Querier is the part of *pgxpool.Pool and pgx.Tx the loader uses. A job that
// reads and writes in one transaction passes its pgx.Tx.
type Querier interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// Decrypter opens one stored token (secure.MultiFernet.Decrypt as a string
// function). A token that will not decrypt is an error, like db.decrypt_field.
type Decrypter func(token string) (string, error)

// FernetDecrypter is the Decrypter of the data keys (secure.LoadDataKeys): no
// age limit, like db.decrypt_field.
func FernetDecrypter(keys *secure.MultiFernet) Decrypter {
	return func(token string) (string, error) {
		plain, err := keys.Decrypt(token, 0, time.Now())
		if err != nil {
			return "", err
		}
		return string(plain), nil
	}
}

// ErrNotFound is returned by the Load functions for a missing row.
var ErrNotFound = errors.New("stayfee: not found")

// pick is db.decrypt_field(token, fallback): the decrypted token when there is
// one, else the plaintext column.
func pick(dec Decrypter, token, plain string) (string, error) {
	if token == "" {
		return plain, nil
	}
	return dec(token)
}

const apartmentSelect = `SELECT id, COALESCE(legal_entity_id, 0), internal_name, stay_fee_rate_czk,
	COALESCE(stay_fee_cadence, ''), COALESCE(stay_fee_vs, ''), COALESCE(stay_fee_authority_name, ''),
	COALESCE(stay_fee_authority_address, ''), COALESCE(stay_fee_authority_contact, ''),
	COALESCE(stay_fee_payee, ''), COALESCE(stay_fee_instruction, ''), COALESCE(stay_fee_council_account, ''),
	COALESCE(stay_fee_council_iban, ''), COALESCE(stay_fee_scope_rule, ''), COALESCE(stay_fee_scope_reference, ''),
	stay_fee_collect <> 0, COALESCE(stay_fee_guest_rails, ''), COALESCE(stay_fee_guest_default_rail, ''),
	COALESCE(stay_fee_guest_revolut_link, ''), COALESCE(stay_fee_guest_cash_note, ''),
	COALESCE(addr_obec, ''), COALESCE(city_en, ''), COALESCE(addr_street, ''), COALESCE(addr_house_no, ''),
	COALESCE(addr_orient_no, ''), COALESCE(addr_zip, ''), COALESCE(archived_at, '')
	FROM apartment`

// ApartmentSelect is the column list LoadApartment reads, ending in FROM
// apartment, so a job that lists apartments (stay_fee_auto.run) can append its
// own WHERE and scan with ScanApartment.
const ApartmentSelect = apartmentSelect

// ScanApartment scans one row of ApartmentSelect.
func ScanApartment(rows pgx.Rows) (*Apartment, error) {
	var a Apartment
	if err := rows.Scan(&a.ID, &a.LegalEntityID, &a.InternalName, &a.StayFeeRateCZK, &a.StayFeeCadence,
		&a.StayFeeVS, &a.AuthorityName, &a.AuthorityAddress, &a.AuthorityContact, &a.Payee, &a.Instruction,
		&a.CouncilAccount, &a.CouncilIBAN, &a.ScopeRule, &a.ScopeReference, &a.Collect, &a.GuestRails,
		&a.GuestDefaultRail, &a.RevolutLink, &a.CashNote, &a.AddrObec, &a.CityEN, &a.AddrStreet,
		&a.AddrHouseNo, &a.AddrOrientNo, &a.AddrZip, &a.ArchivedAt); err != nil {
		return nil, err
	}
	return &a, nil
}

// LoadApartment reads one apartment; ErrNotFound when there is none.
func LoadApartment(ctx context.Context, q Querier, id int64) (*Apartment, error) {
	rows, err := q.Query(ctx, apartmentSelect+` WHERE id = $1`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		if err := rows.Err(); err != nil {
			return nil, err
		}
		return nil, ErrNotFound
	}
	return ScanApartment(rows)
}

// LoadEntity reads the payer of an apartment (nil, nil when the apartment has
// none or the row is gone). withSignature decrypts the drawn signature, which
// only MakeHlaseni needs.
func LoadEntity(ctx context.Context, q Querier, dec Decrypter, id int64, withSignature bool) (*Entity, error) {
	if id == 0 {
		return nil, nil
	}
	rows, err := q.Query(ctx, `SELECT id, COALESCE(name, ''), COALESCE(seat, ''), COALESCE(ico, ''),
		COALESCE(contact_email, ''), COALESCE(iban, ''), COALESCE(bank_account, ''),
		COALESCE(signature_png_enc, ''), COALESCE(signature_name, '') FROM legal_entity WHERE id = $1`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		return nil, rows.Err()
	}
	var e Entity
	var sigToken string
	if err := rows.Scan(&e.ID, &e.Name, &e.Seat, &e.ICO, &e.ContactEmail, &e.IBAN, &e.BankAccount,
		&sigToken, &e.SignatureName); err != nil {
		return nil, err
	}
	if withSignature && sigToken != "" {
		if e.SignaturePNG, err = dec(sigToken); err != nil {
			return nil, err
		}
	}
	return &e, nil
}

// LoadSchedule is stay_fee_rate.schedule_for: the apartment's dated rates.
func LoadSchedule(ctx context.Context, q Querier, ap *Apartment, scheduleToday time.Time) ([]RateStep, error) {
	rows, err := loadRateRows(ctx, q, ap.ID)
	if err != nil {
		return nil, err
	}
	return ScheduleFor(ap.StayFeeRateCZK, rows, scheduleToday)
}

func loadRateRows(ctx context.Context, q Querier, apartmentID int64) ([]RateRow, error) {
	rows, err := q.Query(ctx, `SELECT effective_from, rate_czk FROM stay_fee_rate
		WHERE apartment_id = $1 ORDER BY effective_from`, apartmentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []RateRow
	for rows.Next() {
		var r RateRow
		if err := rows.Scan(&r.EffectiveFrom, &r.RateCZK); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// guestSelect lists the guest columns of the stay-fee reads. With docs false
// the document number is not selected (and so not decrypted).
func guestSelect(docs bool) string {
	doc := `'', ''`
	if docs {
		doc = `COALESCE(g.doc_number, ''), COALESCE(g.doc_number_enc, '')`
	}
	return `SELECT g.id, g.reservation_id, COALESCE(g.surname, ''), COALESCE(g.first_name, ''),
		COALESCE(g.birth_date, ''), COALESCE(g.birth_date_enc, ''), COALESCE(g.nationality, ''),
		COALESCE(g.doc_type, ''), ` + doc + `,
		COALESCE(g.res_street, ''), COALESCE(g.res_street_enc, ''), COALESCE(g.res_city, ''),
		COALESCE(g.res_city_enc, ''), COALESCE(g.res_country, ''), COALESCE(g.stay_from, ''),
		COALESCE(g.stay_to, ''), COALESCE(g.fee_host_decision, ''), COALESCE(g.fee_host_reason, ''),
		COALESCE(g.fee_host_reason_enc, ''), COALESCE(g.signature_png, ''), COALESCE(g.signature_png_enc, ''),
		COALESCE(g.restricted_at, '') <> '', r.date_from, r.date_to
		FROM guest g JOIN reservation r ON r.id = g.reservation_id `
}

func loadGuests(ctx context.Context, q Querier, dec Decrypter, sql string, args ...any) ([]GuestRow, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []GuestRow
	for rows.Next() {
		var g GuestRow
		var birthEnc, docEnc, streetEnc, cityEN, reasonEnc, sigEnc string
		var docPlain, streetPlain, cityPlain, reasonPlain, birthPlain, sigPlain string
		if err := rows.Scan(&g.ID, &g.ReservationID, &g.Surname, &g.FirstName, &birthPlain, &birthEnc,
			&g.Nationality, &g.DocType, &docPlain, &docEnc, &streetPlain, &streetEnc, &cityPlain, &cityEN,
			&g.ResCountry, &g.StayFrom, &g.StayTo, &g.FeeHostDecision, &reasonPlain, &reasonEnc, &sigPlain,
			&sigEnc, &g.Restricted, &g.ResFrom, &g.ResTo); err != nil {
			return nil, err
		}
		for _, f := range []struct {
			dst          *string
			token, plain string
		}{{&g.BirthDate, birthEnc, birthPlain}, {&g.DocNumber, docEnc, docPlain},
			{&g.ResStreet, streetEnc, streetPlain}, {&g.ResCity, cityEN, cityPlain},
			{&g.FeeHostReason, reasonEnc, reasonPlain}, {&g.SignaturePNG, sigEnc, sigPlain}} {
			v, err := pick(dec, f.token, f.plain)
			if err != nil {
				return nil, fmt.Errorf("stayfee: guest %d: %w", g.ID, err)
			}
			*f.dst = v
		}
		out = append(out, g)
	}
	return out, rows.Err()
}

// periodGuestsWhere is stay_fee._GUESTS_SQL: live guests of the apartment whose
// stay touches first..last (the demo stay owes no fee).
const periodGuestsWhere = `WHERE r.apartment_id = $1 AND r.status = 'active' AND g.archived_at IS NULL
	AND COALESCE(r.source, '') != 'demo'
	AND COALESCE(g.stay_from, r.date_from) <= $2 AND COALESCE(g.stay_to, r.date_to) >= $3`

// LoadPeriodGuests is the guest read of property_period, in its order.
func LoadPeriodGuests(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, first, last time.Time) ([]GuestRow, error) {
	return loadGuests(ctx, q, dec, guestSelect(false)+periodGuestsWhere+
		` ORDER BY COALESCE(g.stay_from, r.date_from), g.id`, apartmentID, ISO(last), ISO(first))
}

// ActiveAdjustments is stay_fee_adjustment.active: the open corrections of one
// period key with their signed bed-days (remove is negative) and the net total.
func ActiveAdjustments(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, key string) (int, []Adjustment, error) {
	rows, err := q.Query(ctx, `SELECT id, direction, mode, bed_days, COALESCE(reason_enc, '')
		FROM stay_fee_adjustment WHERE apartment_id = $1 AND period_key = $2 AND reversed_at IS NULL
		ORDER BY id`, apartmentID, key)
	if err != nil {
		return 0, nil, err
	}
	defer rows.Close()
	out := []Adjustment{}
	total := 0
	for rows.Next() {
		var a Adjustment
		var token string
		if err := rows.Scan(&a.ID, &a.Direction, &a.Mode, &a.BedDays, &token); err != nil {
			return 0, nil, err
		}
		a.Delta = a.BedDays
		if a.Direction == "remove" {
			a.Delta = -a.Delta
		}
		total += a.Delta
		if token != "" {
			if a.Reason, err = dec(token); err != nil {
				return 0, nil, err
			}
		}
		out = append(out, a)
	}
	return total, out, rows.Err()
}

// NetBedDays is stay_fee_adjustment.net_bed_days.
func NetBedDays(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, key string) (int, error) {
	total, _, err := ActiveAdjustments(ctx, q, dec, apartmentID, key)
	return total, err
}

// Opts are the optional arguments of property_period and check.
type Opts struct {
	// LiveOnly false looks for a sealed filing that covers month first and
	// returns its frozen summary (the list page); true always calculates.
	LiveOnly bool
	// Cadence overrides the apartment's cadence when it is a valid one.
	Cadence string
	// Rate, when not nil, replaces the dated schedule by one flat rate.
	Rate *int
	// ScheduleToday is Python's date.today() in schedule_for (see ScheduleFor).
	ScheduleToday time.Time
}

// PropertyPeriod is stay_fee.property_period: nil when the property has no
// stay fee (and no sealed filing, unless LiveOnly).
func PropertyPeriod(ctx context.Context, q Querier, dec Decrypter, ap *Apartment, month time.Time, o Opts) (*Period, error) {
	if !o.LiveOnly {
		row, err := Covering(ctx, q, ap.ID, month)
		if err != nil {
			return nil, err
		}
		if row != nil {
			return FrozenSummary(row, ap, dec)
		}
	}
	if !IsActive(ap) {
		return nil, nil
	}
	chosen := ChooseCadence(ap, o.Cadence)
	first, last := PeriodBounds(chosen, month)
	in := PeriodInput{ScheduleToday: o.ScheduleToday}
	var err error
	if o.Rate == nil {
		if in.RateRows, err = loadRateRows(ctx, q, ap.ID); err != nil {
			return nil, err
		}
	}
	if in.Guests, err = LoadPeriodGuests(ctx, q, dec, ap.ID, first, last); err != nil {
		return nil, err
	}
	if _, in.Adjustments, err = ActiveAdjustments(ctx, q, dec, ap.ID, PeriodKey(chosen, month)); err != nil {
		return nil, err
	}
	return BuildPeriod(ap, month, chosen, o.Rate, in)
}

// UnsignedStays is stay_fee.unsigned_stays: guests in first..last with no
// signature yet. With the live period of the same property and dates its count
// is returned without a second read.
func UnsignedStays(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, first, last time.Time, period *Period) (int, error) {
	if period != nil && !period.Frozen && period.First.Equal(first) && period.Last.Equal(last) &&
		period.Apartment != nil && period.Apartment.ID == apartmentID {
		return period.UnsignedGuests, nil
	}
	guests, err := LoadPeriodGuests(ctx, q, dec, apartmentID, first, last)
	if err != nil {
		return 0, err
	}
	n := 0
	for _, g := range guests {
		if !guestSignatureSettled(g) {
			n++
		}
	}
	return n, nil
}

// LoadIssueContext reads what ReportIssues needs: the payer and the foreign overlap.
func LoadIssueContext(ctx context.Context, q Querier, dec Decrypter, g *Group) (IssueContext, error) {
	var ic IssueContext
	var err error
	if ic.Entity, err = LoadEntity(ctx, q, dec, g.Anchor.LegalEntityID, false); err != nil {
		return ic, err
	}
	if !g.First.IsZero() {
		row, err := ForeignOverlap(ctx, q, g.Anchor.ID, g.Cadence, g.First)
		if err != nil {
			return ic, err
		}
		ic.ForeignOverlap = row != nil
	}
	return ic, nil
}

// Checked is stay_fee_auto.check's result: everything that blocks sealing a period.
type Checked struct {
	Period *Period
	Group  *Group
	Issues []string
	Key    string
}

// Check is stay_fee_auto.check: the live period, its group, the issues that
// block sealing (the unsigned-stays key last) and the filing period key.
func Check(ctx context.Context, q Querier, dec Decrypter, ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {
	o.LiveOnly = true
	period, err := PropertyPeriod(ctx, q, dec, ap, month, o)
	if err != nil {
		return nil, err
	}
	group := ReportGroup(ap, month, period, o.Cadence)
	ic, err := LoadIssueContext(ctx, q, dec, group)
	if err != nil {
		return nil, err
	}
	issues := ReportIssues(group, today, ic)
	unsigned, err := UnsignedStays(ctx, q, dec, ap.ID, group.First, group.Last, period)
	if err != nil {
		return nil, err
	}
	if unsigned > 0 {
		issues = append(issues, "stay_fees.issue.unsigned")
	}
	return &Checked{Period: period, Group: group, Issues: issues, Key: PeriodKey(group.Cadence, group.First)}, nil
}

// RegisterFor is stay_fee.register_rows with the guests read from the database.
func RegisterFor(ctx context.Context, q Querier, dec Decrypter, p *Period) ([]RegisterRow, error) {
	ids := make([]int64, 0, len(p.Lines))
	for _, l := range p.Lines {
		ids = append(ids, l.GuestID)
	}
	byID := map[int64]GuestRow{}
	if len(ids) > 0 {
		guests, err := loadGuests(ctx, q, dec, guestSelect(true)+`WHERE g.id = ANY($1)`, ids)
		if err != nil {
			return nil, err
		}
		for _, g := range guests {
			byID[g.ID] = g
		}
	}
	return RegisterRows(p, byID)
}

// HlaseniFor is stay_fee.hlaseni(group, issued_on) with the payer read from the database.
func HlaseniFor(ctx context.Context, q Querier, dec Decrypter, g *Group, issuedOn time.Time) (*Hlaseni, error) {
	entity, err := LoadEntity(ctx, q, dec, g.Anchor.LegalEntityID, true)
	if err != nil {
		return nil, err
	}
	return MakeHlaseni(g, issuedOn, entity)
}
