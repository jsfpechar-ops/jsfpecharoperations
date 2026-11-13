package cleaning

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

var (
	timeRE  = regexp.MustCompile(`^(?:[01][0-9]|2[0-3]):[0-5][0-9]$`)
	dateRE  = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)
	tokenRE = regexp.MustCompile(`^[A-Za-z0-9_-]{43}$`)
)

// today is cleaning.today(): the Prague calendar date, as UTC midnight.
func today(at time.Time) time.Time {
	l := deadlines.LocalNow(at)
	return time.Date(l.Year(), l.Month(), l.Day(), 0, 0, 0, 0, time.UTC)
}

// stamp is db.utcnow(): UTC, whole seconds, "+00:00".
func stamp(at time.Time) string {
	return at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

func iso(d time.Time) string { return d.Format("2006-01-02") }

// parseDate is cleaning.parse_date: YYYY-MM-DD, a real date, years 1900 to 2100.
func parseDate(value string) (time.Time, error) {
	if !dateRE.MatchString(value) {
		return time.Time{}, fmt.Errorf("dates")
	}
	d, err := time.Parse("2006-01-02", value)
	if err != nil || d.Year() < 1900 || d.Year() > 2100 {
		return time.Time{}, fmt.Errorf("dates")
	}
	return d, nil
}

// parseRange is cleaning.parse_range: 1 to 370 days.
func parseRange(start, end string) (time.Time, time.Time, error) {
	first, err := parseDate(start)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	last, err := parseDate(end)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	days := int(last.Sub(first).Hours() / 24)
	if days <= 0 || days > 370 {
		return time.Time{}, time.Time{}, fmt.Errorf("dates")
	}
	return first, last, nil
}

// parseTime is cleaning.parse_time: strip, then HH:MM or empty (nil).
func parseTime(value string) (*string, error) {
	value = strings.TrimSpace(value)
	if value != "" && !timeRE.MatchString(value) {
		return nil, fmt.Errorf("times")
	}
	if value == "" {
		return nil, nil
	}
	return &value, nil
}

// stagingNoLogin is auth.staging_no_login.
func stagingNoLogin(getenv func(string) string) bool {
	if strings.ToLower(getenv("UBYHOST_DEPLOYMENT")) != "staging" {
		return false
	}
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAGING_NO_LOGIN"))) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

// home is one row of cleaning.properties.
type home struct {
	ID            int64
	Name          string
	Owner         *int64
	CheckinHour   *int64
	CheckoutHour  *int64
	LockProvider  *string
	LockID        *string
	Instructions  string
	CodeID        *int64
	PendingCodeID *int64
}

// hourText is cleaning._hour: "HH:00" for 0 to 23, else nil.
func hourText(h *int64) *string {
	if h == nil || *h < 0 || *h > 23 {
		return nil
	}
	s := fmt.Sprintf("%02d:00", *h)
	return &s
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// properties is cleaning.properties: the owner's active, not archived apartments.
func properties(ctx context.Context, pool *pgxpool.Pool, owner *int64, ids []int64) ([]home, error) {
	rows, err := pool.Query(ctx,
		`SELECT a.id, a.internal_name, a.owner_user_id, a.checkin_hour, a.checkout_hour,
		        a.lock_provider, a.lock_id, COALESCE(p.instructions, ''), p.code_id, p.pending_code_id
		   FROM apartment a LEFT JOIN cleaning_property p ON p.apartment_id = a.id
		  WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.active = 1 AND a.archived_at IS NULL
		  ORDER BY a.internal_name, a.id`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []home{}
	for rows.Next() {
		var h home
		if err := rows.Scan(&h.ID, &h.Name, &h.Owner, &h.CheckinHour, &h.CheckoutHour,
			&h.LockProvider, &h.LockID, &h.Instructions, &h.CodeID, &h.PendingCodeID); err != nil {
			return nil, err
		}
		if ids != nil && !containsID(ids, h.ID) {
			continue
		}
		out = append(out, h)
	}
	return out, rows.Err()
}

func containsID(ids []int64, id int64) bool {
	for _, v := range ids {
		if v == id {
			return true
		}
	}
	return false
}

// reconcile is cleaning.reconcile(owner): one short transaction per stay, no
// outbound call. The stays are read in id order so that new cleaning ids are
// handed out in a fixed order.
func reconcile(ctx context.Context, pool *pgxpool.Pool, owner *int64, at time.Time) error {
	stays, err := pool.Query(ctx,
		`SELECT r.id, r.apartment_id, r.date_to FROM reservation r
		   JOIN apartment a ON a.id = r.apartment_id WHERE r.status = 'active'
		    AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL
		    AND COALESCE(r.source, '') <> 'demo' AND r.date_to >= $1
		    AND a.owner_user_id IS NOT DISTINCT FROM $2 ORDER BY r.id`,
		iso(today(at).AddDate(0, 0, -30)), owner)
	if err != nil {
		return err
	}
	type stay struct {
		id, apartment int64
		dateTo        string
	}
	var list []stay
	for stays.Next() {
		var s stay
		if err := stays.Scan(&s.id, &s.apartment, &s.dateTo); err != nil {
			stays.Close()
			return err
		}
		list = append(list, s)
	}
	stays.Close()
	if err := stays.Err(); err != nil {
		return err
	}
	for _, s := range list {
		now := stamp(at)
		tx, err := pool.Begin(ctx)
		if err != nil {
			return err
		}
		_, err = tx.Exec(ctx,
			`INSERT INTO cleaning_event
			 (apartment_id, source_reservation_id, source_date, scheduled_date, created_at, updated_at)
			 VALUES ($1, $2, $3, $3, $4, $4) ON CONFLICT (source_reservation_id) DO NOTHING`,
			s.apartment, s.id, s.dateTo, now)
		if err == nil {
			_, err = tx.Exec(ctx,
				`UPDATE cleaning_event SET apartment_id = $1, source_date = $2,
				 scheduled_date = CASE WHEN overridden = 0 THEN $2 ELSE scheduled_date END,
				 state = CASE WHEN state = 'source_cancelled' THEN 'scheduled' ELSE state END,
				 revision = revision + 1, updated_at = $3 WHERE source_reservation_id = $4
				 AND (apartment_id <> $1 OR source_date <> $2 OR state = 'source_cancelled')`,
				s.apartment, s.dateTo, now, s.id)
		}
		if err != nil {
			_ = tx.Rollback(ctx)
			return err
		}
		if err := tx.Commit(ctx); err != nil {
			return err
		}
	}
	// A dismissal remains a dismissal when its booking is cancelled and restored.
	_, err = pool.Exec(ctx,
		`UPDATE cleaning_event SET state = 'source_cancelled', revision = revision + 1,
		 updated_at = $1 WHERE state = 'scheduled' AND source_reservation_id IS NOT NULL
		 AND apartment_id IN (SELECT a.id FROM apartment a WHERE a.owner_user_id IS NOT DISTINCT FROM $2)
		 AND NOT EXISTS (SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE r.id = cleaning_event.source_reservation_id AND r.status = 'active'
		 AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL)`,
		stamp(at), owner)
	return err
}

// fieldReader decrypts stored fields; the data keys load on first use.
type fieldReader struct {
	getenv func(string) string
	keys   *secure.MultiFernet
	at     time.Time
}

// decrypt is db.decrypt_field for a token that is present.
func (f *fieldReader) decrypt(token string) (string, error) {
	if f.keys == nil {
		keys, err := secure.LoadDataKeys(f.getenv)
		if err != nil {
			return "", err
		}
		f.keys = keys
	}
	b, err := f.keys.Decrypt(token, 0, f.at)
	return string(b), err
}

// codeInfo is the dict cleaning._code returns.
type codeInfo struct{ Value, Source, Pending string }

// code is cleaning._code. It only reads; nothing is queued with the lock provider.
func code(ctx context.Context, pool *pgxpool.Pool, f *fieldReader, h home) (codeInfo, error) {
	var out codeInfo
	var state, source, pin, lockID *string
	var lockAccount *int64
	found := false
	if h.CodeID != nil {
		err := pool.QueryRow(ctx,
			`SELECT state, source, pin_enc, lock_account_id, lock_id FROM cleaning_code WHERE id = $1`,
			*h.CodeID).Scan(&state, &source, &pin, &lockAccount, &lockID)
		if err == nil {
			found = true
		} else if err != pgx.ErrNoRows {
			return out, err
		}
	}
	if h.PendingCodeID != nil {
		var pending *string
		err := pool.QueryRow(ctx, `SELECT state FROM cleaning_code WHERE id = $1`, *h.PendingCodeID).Scan(&pending)
		if err == nil {
			out.Pending = str(pending)
		} else if err != pgx.ErrNoRows {
			return out, err
		}
	}
	if !found {
		return out, nil
	}
	out.Source = str(source)
	usable := !stagingNoLogin(f.getenv) && str(state) == "active" && str(pin) != ""
	if usable && str(source) == "ttlock" {
		var accountOwner *int64
		var accountFound bool
		if lockAccount != nil {
			err := pool.QueryRow(ctx, `SELECT owner_user_id FROM lock_account WHERE id = $1`, *lockAccount).Scan(&accountOwner)
			if err == nil {
				accountFound = true
			} else if err != pgx.ErrNoRows {
				return out, err
			}
		}
		homeLock := "None"
		if h.LockID != nil {
			homeLock = *h.LockID
		}
		sameOwner := (accountOwner == nil && h.Owner == nil) || (accountOwner != nil && h.Owner != nil && *accountOwner == *h.Owner)
		usable = accountFound && sameOwner && str(h.LockProvider) == "ttlock" && lockID != nil && homeLock == *lockID
	}
	if usable {
		v, err := f.decrypt(*pin)
		if err != nil {
			return out, err
		}
		out.Value = v
	}
	return out, nil
}

// booking is one booking bar of the schedule. Key order is Python's dict order.
type booking struct {
	ID             string `json:"id"`
	Kind           string `json:"kind"`
	PropertyID     int64  `json:"propertyId"`
	Property       string `json:"property"`
	Start          string `json:"start"`
	End            string `json:"end"`
	DisplayStart   string `json:"displayStart"`
	DisplayEnd     string `json:"displayEnd"`
	TimingFallback bool   `json:"timingFallback"`
	Label          string `json:"label"`
	Tone           string `json:"tone"`
	Expected       *int   `json:"expected"`
	URL            string `json:"url"`
}

// cleaningItem is one cleaning. Key order is Python's dict order.
type cleaningItem struct {
	ID                string  `json:"id"`
	EventID           int64   `json:"eventId"`
	Kind              string  `json:"kind"`
	PropertyID        int64   `json:"propertyId"`
	Property          string  `json:"property"`
	Start             string  `json:"start"`
	End               string  `json:"end"`
	DisplayStart      string  `json:"displayStart"`
	DisplayEnd        string  `json:"displayEnd"`
	TimingUnavailable bool    `json:"timingUnavailable"`
	Date              string  `json:"date"`
	StartTime         *string `json:"startTime"`
	EndTime           *string `json:"endTime"`
	Checkout          *string `json:"checkout"`
	CheckoutTime      *string `json:"checkoutTime"`
	NextArrival       *string `json:"nextArrival"`
	CheckinTime       *string `json:"checkinTime"`
	Notes             string  `json:"notes"`
	Instructions      string  `json:"instructions"`
	Code              string  `json:"code"`
	CodeSource        string  `json:"codeSource"`
	CodePending       string  `json:"codePending"`
	Origin            string  `json:"origin"`
	Overridden        bool    `json:"overridden"`
	Revision          int64   `json:"revision"`
	Conflict          bool    `json:"conflict"`
	Tone              string  `json:"tone"`
	Label             string  `json:"label"`
	Expected          *int    `json:"expected"`
	URL               string  `json:"url"`
}

// schedule is cleaning.schedule's result before _payload adds the property list.
type schedule struct {
	Events    []any
	Cleanings []*cleaningItem
	From, To  string
}

type stayRow struct {
	id       int64
	from, to string
}

// buildSchedule is cleaning.schedule(owner, first, last, ids) with include_private=True.
func buildSchedule(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner *int64, first, last time.Time, ids []int64, at time.Time) (*schedule, error) {
	if err := reconcile(ctx, pool, owner, at); err != nil {
		return nil, err
	}
	homes, err := properties(ctx, pool, owner, ids)
	if err != nil {
		return nil, err
	}
	out := &schedule{Events: []any{}, Cleanings: []*cleaningItem{}, From: iso(first), To: iso(last)}
	fields := &fieldReader{getenv: getenv, at: at}
	firstS, lastS := iso(first), iso(last)
	for _, h := range homes {
		stays, err := loadStays(ctx, pool, h.ID)
		if err != nil {
			return nil, err
		}
		cd, err := code(ctx, pool, fields, h)
		if err != nil {
			return nil, err
		}
		checkoutTime, checkinTime := hourText(h.CheckoutHour), hourText(h.CheckinHour)
		for _, s := range stays {
			if s.from < lastS && s.to >= firstS {
				in, outH := "12:00", "12:00"
				if checkinTime != nil {
					in = *checkinTime
				}
				if checkoutTime != nil {
					outH = *checkoutTime
				}
				out.Events = append(out.Events, &booking{
					ID: fmt.Sprintf("reservation:%d", s.id), Kind: "booking", PropertyID: h.ID, Property: h.Name,
					Start: s.from, End: s.to, DisplayStart: s.from + "T" + in, DisplayEnd: s.to + "T" + outH,
					TimingFallback: checkinTime == nil || checkoutTime == nil,
					Label:          "", Tone: "neutral", URL: "#cleaning-list",
				})
			}
		}
		events, err := loadEvents(ctx, pool, h.ID, firstS, lastS)
		if err != nil {
			return nil, err
		}
		for _, e := range events {
			item, err := cleaningFor(h, stays, e, cd, checkoutTime, checkinTime, fields)
			if err != nil {
				return nil, err
			}
			out.Events = append(out.Events, item)
			out.Cleanings = append(out.Cleanings, item)
		}
	}
	sortCleanings(out.Cleanings)
	return out, nil
}

func loadStays(ctx context.Context, pool *pgxpool.Pool, apartment int64) ([]stayRow, error) {
	rows, err := pool.Query(ctx,
		`SELECT id, date_from, date_to FROM reservation WHERE apartment_id = $1
		  AND status = 'active' AND archived_at IS NULL AND COALESCE(source, '') <> 'demo'
		  ORDER BY date_from, date_to, id`, apartment)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []stayRow
	for rows.Next() {
		var s stayRow
		if err := rows.Scan(&s.id, &s.from, &s.to); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

type eventRow struct {
	id         int64
	source     *int64
	date       string
	start, end *string
	notes      *string
	overridden int64
	revision   int64
}

func loadEvents(ctx context.Context, pool *pgxpool.Pool, apartment int64, first, last string) ([]eventRow, error) {
	rows, err := pool.Query(ctx,
		`SELECT id, source_reservation_id, scheduled_date, start_time, end_time, notes_enc, overridden, revision
		   FROM cleaning_event WHERE apartment_id = $1 AND state = 'scheduled'
		    AND scheduled_date >= $2 AND scheduled_date < $3 ORDER BY scheduled_date, start_time, id`,
		apartment, first, last)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []eventRow
	for rows.Next() {
		var e eventRow
		if err := rows.Scan(&e.id, &e.source, &e.date, &e.start, &e.end, &e.notes, &e.overridden, &e.revision); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

func sortCleanings(list []*cleaningItem) {
	less := func(a, b *cleaningItem) bool {
		if a.Date != b.Date {
			return a.Date < b.Date
		}
		if str(a.StartTime) != str(b.StartTime) {
			return str(a.StartTime) < str(b.StartTime)
		}
		if a.Property != b.Property {
			return a.Property < b.Property
		}
		return a.EventID < b.EventID
	}
	// Insertion sort: stable, and the lists are short.
	for i := 1; i < len(list); i++ {
		for j := i; j > 0 && less(list[j], list[j-1]); j-- {
			list[j], list[j-1] = list[j-1], list[j]
		}
	}
}

// cleaningFor is the body of the events loop in cleaning.schedule.
func cleaningFor(h home, stays []stayRow, e eventRow, cd codeInfo, checkoutTime, checkinTime *string, fields *fieldReader) (*cleaningItem, error) {
	var source *stayRow
	for i := range stays {
		if e.source != nil && stays[i].id == *e.source {
			source = &stays[i]
			break
		}
	}
	threshold := e.date
	if source != nil {
		threshold = source.to
	}
	var arrival *string
	for i := range stays {
		if e.source != nil && stays[i].id == *e.source {
			continue
		}
		if stays[i].from >= threshold {
			a := stays[i].from
			arrival = &a
			break
		}
	}
	var departure *string
	warning := false
	if source != nil {
		d := source.to
		departure = &d
		warning = e.date < d
		warning = warning || (e.date == d && str(e.start) != "" && checkoutTime != nil && *e.start < *checkoutTime)
		warning = warning || (arrival != nil && e.date > *arrival)
		warning = warning || (arrival != nil && *arrival == e.date && str(e.end) != "" && checkinTime != nil && *e.end > *checkinTime)
		for _, r := range stays {
			if r.id != source.id && r.from < d && r.to > d {
				warning = true
			}
		}
		warning = warning || (arrival != nil && *arrival == d && checkoutTime != nil && checkinTime != nil && *checkoutTime >= *checkinTime)
	}
	defaultWindow := checkoutTime != nil && checkinTime != nil && *checkoutTime < *checkinTime
	var explicitStart, explicitEnd *string
	s, errS := parseTime(str(e.start))
	en, errE := parseTime(str(e.end))
	if errS == nil && errE == nil {
		explicitStart, explicitEnd = s, en
	}
	explicitWindow := explicitStart != nil && explicitEnd != nil && *explicitEnd > *explicitStart
	var visualStart, visualEnd string
	switch {
	case explicitWindow:
		visualStart, visualEnd = *explicitStart, *explicitEnd
	case defaultWindow:
		visualStart, visualEnd = *checkoutTime, *checkinTime
	default:
		visualStart, visualEnd = "12:00", "13:00"
	}
	day, _ := time.Parse("2006-01-02", e.date)
	item := &cleaningItem{
		ID: fmt.Sprintf("cleaning:%d", e.id), EventID: e.id, Kind: "cleaning",
		PropertyID: h.ID, Property: h.Name, Start: e.date, End: iso(day.AddDate(0, 0, 1)),
		DisplayStart: e.date + "T" + visualStart, DisplayEnd: e.date + "T" + visualEnd,
		TimingUnavailable: !(explicitWindow || defaultWindow), Date: e.date,
		Checkout: departure, CheckoutTime: checkoutTime, NextArrival: arrival, CheckinTime: checkinTime,
		Instructions: h.Instructions, Code: cd.Value, CodeSource: cd.Source, CodePending: cd.Pending,
		Origin: "manual", Overridden: e.overridden != 0, Revision: e.revision, Conflict: warning,
		Tone: "neutral", Label: "", URL: fmt.Sprintf("#cleaning-%d", e.id),
	}
	if explicitWindow {
		item.StartTime, item.EndTime = e.start, e.end
	}
	if source != nil {
		item.Origin = "automatic"
	}
	if str(e.notes) != "" {
		n, err := fields.decrypt(*e.notes)
		if err != nil {
			return nil, err
		}
		item.Notes = n
	}
	return item, nil
}

// sharedLink is cleaning.shared: the owner and the still-valid property ids of a
// live share, or ok false for a malformed, unknown, revoked or expired token.
func sharedLink(ctx context.Context, pool *pgxpool.Pool, token string, at time.Time) (owner *int64, ids []int64, ok bool, err error) {
	if !tokenRE.MatchString(token) {
		return nil, nil, false, nil
	}
	sum := sha256.Sum256([]byte(token))
	var shareID int64
	err = pool.QueryRow(ctx,
		`SELECT id, owner_user_id FROM cleaning_share WHERE token_hash = $1 AND revoked_at IS NULL AND expires_at > $2`,
		hex.EncodeToString(sum[:]), stamp(at)).Scan(&shareID, &owner)
	if err == pgx.ErrNoRows {
		return nil, nil, false, nil
	}
	if err != nil {
		return nil, nil, false, err
	}
	rows, err := pool.Query(ctx, `SELECT apartment_id FROM cleaning_share_property WHERE share_id = $1`, shareID)
	if err != nil {
		return nil, nil, false, err
	}
	linked := []int64{}
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return nil, nil, false, err
		}
		linked = append(linked, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, nil, false, err
	}
	// Ownership and availability are rechecked on every request.
	homes, err := properties(ctx, pool, owner, linked)
	if err != nil {
		return nil, nil, false, err
	}
	for _, h := range homes {
		ids = append(ids, h.ID)
	}
	if len(ids) == 0 {
		return nil, nil, false, nil
	}
	return owner, ids, true, nil
}

// eventOwned is cleaning.event_for: does the owner's active apartment hold the event.
func eventOwned(ctx context.Context, pool *pgxpool.Pool, owner *int64, eventID int64) (bool, error) {
	var id int64
	err := pool.QueryRow(ctx,
		`SELECT e.id FROM cleaning_event e JOIN apartment a ON a.id = e.apartment_id
		  WHERE e.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2
		  AND a.active = 1 AND a.archived_at IS NULL`, eventID, owner).Scan(&id)
	if err == pgx.ErrNoRows {
		return false, nil
	}
	return err == nil, err
}

// dismiss is cleaning.dismiss: true when the revision still matched.
func dismiss(ctx context.Context, pool *pgxpool.Pool, eventID, revision int64, at time.Time) (bool, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE cleaning_event SET state = 'dismissed', revision = $1, updated_at = $2
		  WHERE id = $3 AND revision = $4 AND state = 'scheduled'`,
		revision+1, stamp(at), eventID, revision)
	return err == nil && tag.RowsAffected() == 1, err
}

// revokeShare is the UPDATE of routes/cleaning.revoke_share, scoped to the owner.
func revokeShare(ctx context.Context, pool *pgxpool.Pool, owner *int64, shareID int64, at time.Time) error {
	_, err := pool.Exec(ctx,
		`UPDATE cleaning_share SET revoked_at = $1 WHERE id = $2 AND owner_user_id IS NOT DISTINCT FROM $3`,
		stamp(at), shareID, owner)
	return err
}
