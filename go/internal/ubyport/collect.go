package ubyport

// collect.go is reporting.collect_sendable (App/app/reporting.py 1354-1470)
// with its helpers: due_for_automatic_send (1043-1086), _as_utc (897),
// signature_dates_stale (974), blocked_as_duplicate (1142), auto_attempts
// (1182), guest_filed_by_hand (2117), reservation_deadline_anchor (2267, the
// guests=None path) and deadlines.reporting_deadline (App/app/deadlines.py
// 19-44). Decryption follows db.decrypt_field (App/app/db.py 2380-2400).

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	collectGuestSent        = "sent"
	collectGuestBlocked     = "blocked"
	collectGuestNotRequired = "not_required"
	collectMaxAutoAttempts  = 1 // SUBMISSION_MAX_AUTO_ATTEMPTS
	collectMarginHours      = 6 // AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS
)

// ApartmentRow is the apartment as collect and the sweep need it. Fields holds
// every text column, for validation.ValidateApartment.
type ApartmentRow struct {
	Apartment        Apartment
	Ref              ApartmentRef
	AutomationMode   string
	SubmitAfterHours int
	Fields           map[string]string
}

// LoadApartment reads one apartment. It returns nil, nil when the row is missing.
func LoadApartment(ctx context.Context, pool *pgxpool.Pool, id int64) (*ApartmentRow, error) {
	var txt string
	err := pool.QueryRow(ctx, `SELECT row_to_json(a)::text FROM apartment a WHERE a.id = $1`, id).Scan(&txt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	dec := json.NewDecoder(strings.NewReader(txt))
	dec.UseNumber()
	var m map[string]any
	if err := dec.Decode(&m); err != nil {
		return nil, err
	}
	fields := map[string]string{}
	for k, v := range m {
		if s, ok := v.(string); ok {
			fields[k] = s
		}
	}
	ap := &ApartmentRow{
		Apartment: Apartment{
			UbyIdub: fields["uby_idub"], UbyMark: fields["uby_mark"], UbyName: fields["uby_name"],
			UbyContact: fields["uby_contact"], AddrOkres: fields["addr_okres"], AddrObec: fields["addr_obec"],
			AddrObecCast: fields["addr_obec_cast"], AddrStreet: fields["addr_street"],
			AddrHouseNo: fields["addr_house_no"], AddrOrientNo: fields["addr_orient_no"], AddrZip: fields["addr_zip"],
		},
		AutomationMode:   fields["automation_mode"],
		SubmitAfterHours: int(jsonInt(m, "submit_after_hours")),
		Fields:           fields,
	}
	ap.Ref = ApartmentRef{
		ID:            id,
		LegalEntityID: jsonIntPtr(m, "legal_entity_id"),
		OwnerUserID:   jsonIntPtr(m, "owner_user_id"),
		InternalName:  fields["internal_name"],
	}
	return ap, nil
}

func jsonInt(m map[string]any, key string) int64 {
	if p := jsonIntPtr(m, key); p != nil {
		return *p
	}
	return 0
}

func jsonIntPtr(m map[string]any, key string) *int64 {
	n, ok := m[key].(json.Number)
	if !ok {
		return nil
	}
	i, err := n.Int64()
	if err != nil {
		return nil
	}
	return &i
}

// FieldDecrypter is the mirror of FieldEncrypter: it returns the plain text of
// one stored token, or an error when the token will not decrypt.
type FieldDecrypter func(token string) (string, error)

// CollectOptions mirrors the keyword arguments of collect_sendable.
// IgnoreSchedule nil means "same as IgnoreAutomation". Now nil means time.Now.
type CollectOptions struct {
	OnlyGuestIDs           []int64
	IgnoreAutomation       bool
	AllowResend            bool
	IgnoreSchedule         *bool
	RestrictedBlocksFiling bool
	Now                    func() time.Time
	Decrypt                FieldDecrypter
}

type collectGuest struct {
	id, resID    int64
	nationality  string
	submitState  string
	lastErrors   string
	manualFiled  string
	stayFrom     string
	stayTo       string
	restrictedAt string
	submissionID *int64
	receiptID    *int64
	submittedAt  *string
	attempts     int64
	guest        Guest
	row          validation.GuestRow
}

type collectStay struct {
	dateFrom, dateTo, completed, source string
}

// CollectSendable returns the guests of one apartment that Python's
// collect_sendable would offer now, in stay start then guest id order. The one
// write of the function (a non-reportable guest set to not_required) happens here too.
func CollectSendable(ctx context.Context, pool *pgxpool.Pool, aptID int64, o CollectOptions) ([]BatchPair, error) {
	ap, err := LoadApartment(ctx, pool, aptID)
	if err != nil || ap == nil {
		return nil, err
	}
	now := time.Now()
	if o.Now != nil {
		now = o.Now()
	}
	ignoreSchedule := o.IgnoreAutomation
	if o.IgnoreSchedule != nil {
		ignoreSchedule = *o.IgnoreSchedule
	}
	loc, err := time.LoadLocation(pragueZone)
	if err != nil {
		return nil, fmt.Errorf("collect: local zone unavailable: %w", err)
	}
	local := now.In(loc)
	today := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)

	stays := map[int64]collectStay{}
	rrows, err := pool.Query(ctx,
		`SELECT id, COALESCE(date_from,''), COALESCE(date_to,''), COALESCE(registration_completed_at,''), COALESCE(source,'')
		   FROM reservation WHERE apartment_id = $1 AND status = 'active' AND archived_at IS NULL
		   AND COALESCE(source, '') != 'demo'`, aptID)
	if err != nil {
		return nil, err
	}
	for rrows.Next() {
		var id int64
		var s collectStay
		if err := rrows.Scan(&id, &s.dateFrom, &s.dateTo, &s.completed, &s.source); err != nil {
			rrows.Close()
			return nil, err
		}
		stays[id] = s
	}
	rrows.Close()
	if err := rrows.Err(); err != nil {
		return nil, err
	}

	query := `SELECT g.id, g.reservation_id, COALESCE(g.nationality,''), COALESCE(g.submit_state,''),
		g.submission_id, COALESCE(g.last_errors,''), g.submit_attempts, COALESCE(g.manual_filed_at,''),
		COALESCE(g.restricted_at,''), COALESCE(g.stay_from,''), COALESCE(g.stay_to,''),
		COALESCE(g.surname,''), COALESCE(g.first_name,''), COALESCE(g.res_country,''),
		COALESCE(g.purpose,''), COALESCE(g.note,''),
		COALESCE(g.doc_number,''), COALESCE(g.doc_number_enc,''),
		COALESCE(g.visa_number,''), COALESCE(g.visa_number_enc,''),
		COALESCE(g.birth_date,''), COALESCE(g.birth_date_enc,''),
		COALESCE(g.res_street,''), COALESCE(g.res_street_enc,''),
		COALESCE(g.res_city,''), COALESCE(g.res_city_enc,''),
		COALESCE(g.signature_png,''), COALESCE(g.signature_png_enc,''),
		g.submitted_at, g.receipt_submission_id
		FROM guest g JOIN reservation r ON r.id = g.reservation_id
		WHERE r.apartment_id = $1 AND r.status = 'active' AND r.archived_at IS NULL AND g.archived_at IS NULL`
	args := []any{aptID}
	if len(o.OnlyGuestIDs) > 0 {
		query += ` AND g.id = ANY($2)`
		args = append(args, o.OnlyGuestIDs)
	}
	query += ` ORDER BY r.date_from, g.id`

	grows, err := pool.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	var guests []collectGuest
	for grows.Next() {
		var c collectGuest
		var surname, first, resCountry, purpose, note string
		var docP, docE, visaP, visaE, birthP, birthE, streetP, streetE, cityP, cityE, sigP, sigE string
		if err := grows.Scan(&c.id, &c.resID, &c.nationality, &c.submitState, &c.submissionID,
			&c.lastErrors, &c.attempts, &c.manualFiled, &c.restrictedAt, &c.stayFrom, &c.stayTo,
			&surname, &first, &resCountry, &purpose, &note,
			&docP, &docE, &visaP, &visaE, &birthP, &birthE, &streetP, &streetE, &cityP, &cityE,
			&sigP, &sigE, &c.submittedAt, &c.receiptID); err != nil {
			grows.Close()
			return nil, err
		}
		fields := []struct {
			plain, enc string
			dst        *string
		}{
			{docP, docE, new(string)}, {visaP, visaE, new(string)}, {birthP, birthE, new(string)},
			{streetP, streetE, new(string)}, {cityP, cityE, new(string)}, {sigP, sigE, new(string)},
		}
		for _, f := range fields {
			v, err := decryptOrPlain(o.Decrypt, f.enc, f.plain)
			if err != nil {
				grows.Close()
				return nil, err
			}
			*f.dst = v
		}
		c.guest = Guest{
			StayFrom: c.stayFrom, StayTo: c.stayTo, Surname: surname, FirstName: first,
			BirthDate: *fields[2].dst, Nationality: c.nationality, DocNumber: *fields[0].dst,
			VisaNumber: *fields[1].dst, ResStreet: *fields[3].dst, ResCity: *fields[4].dst,
			ResCountry: resCountry, Purpose: purpose, Note: note,
		}
		c.row = validation.GuestRow{
			Surname: surname, FirstName: first, BirthDate: *fields[2].dst, Nationality: c.nationality,
			DocNumber: *fields[0].dst, VisaNumber: *fields[1].dst, ResStreet: *fields[3].dst,
			ResCity: *fields[4].dst, ResCountry: resCountry, Purpose: purpose, Note: note,
			StayFrom: c.stayFrom, StayTo: c.stayTo, SignaturePNG: *fields[5].dst,
		}
		guests = append(guests, c)
	}
	grows.Close()
	if err := grows.Err(); err != nil {
		return nil, err
	}

	anchors := map[int64]*time.Time{}
	out := []BatchPair{}
	for _, c := range guests {
		st, ok := stays[c.resID]
		if !ok {
			continue
		}
		if o.RestrictedBlocksFiling && c.restrictedAt != "" {
			continue
		}
		if !validation.GuestIsReportable(c.nationality) {
			if c.submitState != collectGuestNotRequired && c.submitState != collectGuestSent {
				if _, err := pool.Exec(ctx,
					`UPDATE guest SET submit_state = $1, updated_at = $2 WHERE id = $3`,
					collectGuestNotRequired, UTCNow(), c.id); err != nil {
					return nil, err
				}
			}
			continue
		}
		// guest_filed_by_hand: a guest the host filed by hand is never resent.
		if c.submitState == collectGuestSent && (!o.AllowResend || c.manualFiled != "") {
			continue
		}
		if c.submitState == collectGuestBlocked && !o.AllowResend {
			continue
		}
		if c.submitState == collectGuestBlocked && blockedAsDuplicate(c.lastErrors) {
			continue
		}
		if !o.IgnoreAutomation && c.attempts >= collectMaxAutoAttempts {
			continue
		}
		if !o.IgnoreAutomation && c.submissionID != nil && *c.submissionID != 0 {
			var one int
			err := pool.QueryRow(ctx,
				`SELECT 1 FROM submission WHERE id = $1 AND state = 'outcome_unknown' LIMIT 1`,
				*c.submissionID).Scan(&one)
			if err == nil {
				continue
			}
			if !errors.Is(err, pgx.ErrNoRows) {
				return nil, err
			}
		}
		if !validation.GuestIsComplete(c.row, st.dateFrom, st.dateTo, today) {
			continue
		}
		if signatureDatesStale(c.stayFrom, c.stayTo, st.dateFrom, st.dateTo) {
			continue
		}
		if !ignoreSchedule {
			anchor, cached := anchors[c.resID]
			if !cached {
				anchor, err = reservationDeadlineAnchor(ctx, pool, c.resID, st.dateFrom)
				if err != nil {
					return nil, err
				}
				anchors[c.resID] = anchor
			}
			if !DueForAutomaticSend(ap.AutomationMode, ap.SubmitAfterHours, st.completed, anchor, now) {
				continue
			}
		}
		resID, state, attempts := c.resID, c.submitState, c.attempts
		out = append(out, BatchPair{
			Guest:       c.guest,
			Reservation: Reservation{DateFrom: st.dateFrom, DateTo: st.dateTo},
			Outcome: OutcomeGuest{
				ID: c.id, ReservationID: &resID, SubmitState: &state, SubmittedAt: c.submittedAt,
				SubmissionID: c.submissionID, ReceiptSubmissionID: c.receiptID, SubmitAttempts: &attempts,
			},
			Source: st.source,
		})
	}
	return out, nil
}

// decryptOrPlain is db.decrypt_field: no token gives the plain column verbatim;
// a token that will not decrypt is an error, never an empty value.
func decryptOrPlain(dec FieldDecrypter, token, plain string) (string, error) {
	if token == "" {
		return plain, nil
	}
	if dec == nil {
		return "", errors.New("collect: no field decrypter for a stored token")
	}
	v, err := dec(token)
	if err != nil {
		return "", fmt.Errorf("collect: stored guest document field could not be decrypted: %w", err)
	}
	return v, nil
}

// blockedAsDuplicate is reporting.blocked_as_duplicate.
func blockedAsDuplicate(lastErrors string) bool {
	for _, part := range strings.Split(lastErrors, " | ") {
		if IsDuplicate(part) {
			return true
		}
	}
	return false
}

// signatureDatesStale is reporting.signature_dates_stale: a guest window must
// lie inside the booking.
func signatureDatesStale(stayFrom, stayTo, dateFrom, dateTo string) bool {
	if stayFrom == "" && stayTo == "" {
		return false
	}
	if stayFrom != "" && dateFrom != "" && stayFrom < dateFrom {
		return true
	}
	return stayTo != "" && dateTo != "" && stayTo > dateTo
}

// reservationDeadlineAnchor is reservation_deadline_anchor with guests=None: the
// earliest live guest stay_from, else the reservation's date_from.
func reservationDeadlineAnchor(ctx context.Context, pool *pgxpool.Pool, resID int64, dateFrom string) (*time.Time, error) {
	rows, err := pool.Query(ctx,
		`SELECT stay_from FROM guest WHERE reservation_id = $1 AND archived_at IS NULL
		   AND stay_from IS NOT NULL AND stay_from != ''`, resID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var earliest *time.Time
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, err
		}
		if d, ok := validation.ParseISODate(s); ok && (earliest == nil || d.Before(*earliest)) {
			dd := d
			earliest = &dd
		}
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if earliest != nil {
		return earliest, nil
	}
	if d, ok := validation.ParseISODate(dateFrom); ok {
		return &d, nil
	}
	return nil, nil
}

// DueForAutomaticSend is reporting.due_for_automatic_send. completedAt is the
// stay's registration_completed_at; anchor is the deadline anchor (nil when none).
func DueForAutomaticSend(mode string, submitAfterHours int, completedAt string, anchor *time.Time, now time.Time) bool {
	if mode == "manual" || completedAt == "" {
		return false
	}
	completed, ok := parseStoredUTC(completedAt)
	if !ok {
		return false
	}
	hours := submitAfterHours
	if hours == 0 {
		hours = 24 // "submit_after_hours or 24": 0 and NULL both mean 24
	}
	if mode == "immediate" {
		hours = 0
	}
	sendAt := completed.Add(time.Duration(hours) * time.Hour)
	if anchor != nil {
		latest := ReportingDeadline(*anchor).Add(-collectMarginHours * time.Hour)
		if latest.Before(sendAt) {
			sendAt = latest
		}
	}
	return !now.Before(sendAt)
}

// ReportingDeadline is deadlines.reporting_deadline: 23:59:59 Prague wall time on
// the third working day of the window that opens on checkIn (its Y/M/D are used).
func ReportingDeadline(checkIn time.Time) time.Time {
	loc, err := time.LoadLocation(pragueZone)
	if err != nil {
		panic("collect: embedded Prague zone missing: " + err.Error())
	}
	start := time.Date(checkIn.Year(), checkIn.Month(), checkIn.Day(), 0, 0, 0, 0, time.UTC)
	day := addWorkingDays(start, reportingWorkingDays)
	return time.Date(day.Year(), day.Month(), day.Day(), 23, 59, 59, 0, loc)
}

const reportingWorkingDays = 3 // deadlines.REPORTING_WORKING_DAYS

// addWorkingDays is deadlines.add_working_days: Monday to Friday; holidays count.
func addWorkingDays(start time.Time, count int) time.Time {
	current := start
	remaining := count
	if isWorkingDay(current) {
		remaining = count - 1
	}
	for remaining > 0 {
		current = current.AddDate(0, 0, 1)
		if isWorkingDay(current) {
			remaining--
		}
	}
	return current
}

func isWorkingDay(d time.Time) bool {
	return d.Weekday() != time.Saturday && d.Weekday() != time.Sunday
}

// parseStoredUTC is reporting._as_utc: a naive stored timestamp reads as UTC.
func parseStoredUTC(v string) (time.Time, bool) {
	layouts := []string{
		time.RFC3339Nano,
		"2006-01-02T15:04:05.999999999",
		"2006-01-02 15:04:05.999999999Z07:00",
		"2006-01-02 15:04:05.999999999",
		"2006-01-02",
	}
	for _, layout := range layouts {
		if t, err := time.Parse(layout, v); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}
