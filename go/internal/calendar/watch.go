// watch.go is reporting.check_deadlines (App/app/reporting.py 2614-2736): the
// deadline watch that raises and resolves the deadline, headcount_mismatch and
// guest_record_unreadable alerts. It lives here because the port of
// reservation_progress and reservation_deadline_anchor it needs (progress.go)
// and the guest loader (handler.go) are this package's. Nothing calls it yet:
// brief 1132 §10 E adds the job kind. testdata/check_deadlines_golden.json,
// written by App/scripts/check_deadlines_golden.py, is the parity check.
package calendar

import (
	"context"
	"errors"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// watchClearSQL resolves the open cards of cancelled, ignored or archived
// stays in one statement. $2 is the owner; NULL clears every workspace.
const watchClearSQL = `UPDATE alert SET resolved_at = $1, user_dismissed = 0 WHERE id IN (
	SELECT al.id FROM alert al
	JOIN reservation r ON r.id = al.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE al.resolved_at IS NULL
	AND al.kind IN ('deadline', 'headcount_mismatch', 'guest_incomplete_checkin')
	AND (r.status != 'active' OR r.archived_at IS NOT NULL)
	AND ($2::bigint IS NULL OR a.owner_user_id = $2::bigint))`

// watchStaysSQL is the stays the watch reads: live, on an active apartment,
// not the demo stay (0100). The order only makes runs repeatable.
const watchStaysSQL = `SELECT r.id, r.apartment_id, a.internal_name, r.date_from, r.date_to,
	r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
	FROM reservation r JOIN apartment a ON a.id = r.apartment_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND ($1::bigint IS NULL OR a.owner_user_id = $1::bigint)
	ORDER BY r.id`

// CheckDeadlines is reporting.check_deadlines: it alerts on stays running out
// of legal time with data missing and returns how many deadline alerts it
// raised. at is the instant of the run; owner limits the run to one workspace
// (nil runs every workspace, as the scheduled job does).
func CheckDeadlines(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time, owner *int64) (int, error) {
	now := deadlines.LocalNow(at)
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	// Python's validation reads date.today(): the date of the run on the server clock.
	validationToday := time.Date(at.UTC().Year(), at.UTC().Month(), at.UTC().Day(), 0, 0, 0, 0, time.UTC)
	if _, err := pool.Exec(ctx, watchClearSQL, ubyport.UTCNow(), owner); err != nil {
		return 0, err
	}
	stays, err := watchStays(ctx, pool, owner)
	if err != nil {
		return 0, err
	}
	fields := &fieldReader{getenv: getenv}
	raised := 0
	for _, stay := range stays {
		start, ok, err := watchAnchor(ctx, pool, stay)
		if err != nil {
			return raised, err
		}
		if !ok {
			continue
		}
		guests, err := watchGuests(ctx, pool, stay.id, fields)
		if errors.Is(err, secure.ErrInvalidToken) {
			// One unreadable guest row stops the watch for its own stay only.
			log.Printf("deadline watch stopped for reservation_id=%d: guest record unreadable", stay.id)
			aptID, resID := stay.propertyID, stay.id
			err = ubyport.RaiseAlert(ctx, pool, "critical", "guest_record_unreadable",
				stay.property+": a guest record cannot be read, so this stay is not being watched.",
				"A stored guest document field could not be decrypted. Restore the encryption key, or have the guest's document entered again.",
				"guest_record_unreadable:reservation:"+strconv.FormatInt(stay.id, 10),
				&aptID, &resID, nil, ubyport.AlertParams{"property": stay.property})
			if err != nil {
				return raised, err
			}
			continue
		}
		if err != nil {
			return raised, err
		}
		p := progress(stay, guests, validationToday)
		n, err := watchStay(ctx, pool, stay, p, start, now, today)
		if err != nil {
			return raised, err
		}
		raised += n
	}
	return raised, nil
}

// watchStays reads the stays to watch.
func watchStays(ctx context.Context, pool *pgxpool.Pool, owner *int64) ([]stayRow, error) {
	rows, err := pool.Query(ctx, watchStaysSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []stayRow
	for rows.Next() {
		var s stayRow
		if err := rows.Scan(&s.id, &s.propertyID, &s.property, &s.dateFrom, &s.dateTo,
			&s.declared, &s.override, &s.reduced); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// watchAnchor is reservation_deadline_anchor reading its own rows: only the
// guests' stay_from, so it never decrypts and runs before the guest read, as
// Python's does. A stay with no anchor is skipped even when a guest is unreadable.
func watchAnchor(ctx context.Context, pool *pgxpool.Pool, stay stayRow) (time.Time, bool, error) {
	rows, err := pool.Query(ctx,
		`SELECT stay_from FROM guest WHERE reservation_id = $1 AND archived_at IS NULL
		AND stay_from IS NOT NULL AND stay_from != ''`, stay.id)
	if err != nil {
		return time.Time{}, false, err
	}
	defer rows.Close()
	var guests []guestRow
	for rows.Next() {
		var g guestRow
		if err := rows.Scan(&g.row.StayFrom); err != nil {
			return time.Time{}, false, err
		}
		guests = append(guests, g)
	}
	if err := rows.Err(); err != nil {
		return time.Time{}, false, err
	}
	start, ok := anchorDate(stay, guests)
	return start, ok, nil
}

// watchGuests is the guest read of reservation_progress for one stay. Python's
// SELECT * decrypts every encrypted guest column, fee_host_reason included,
// which loadGuests does not read; so that one is decrypted here as a check.
// A field that will not decrypt returns secure.ErrInvalidToken.
func watchGuests(ctx context.Context, pool *pgxpool.Pool, id int64, fields *fieldReader) ([]guestRow, error) {
	byStay, err := loadGuests(ctx, pool, []int64{id}, fields)
	if err != nil {
		return nil, err
	}
	rows, err := pool.Query(ctx,
		`SELECT COALESCE(fee_host_reason_enc, '') FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var token string
		if err := rows.Scan(&token); err != nil {
			return nil, err
		}
		if _, err := fields.value("", token); err != nil {
			return nil, err
		}
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return byStay[id], nil
}

// watchTitle is the card title: "<property> · <from> – <to>", dates as
// %d.%m.%Y, an unreadable date left out.
func watchTitle(stay stayRow) string {
	dates := ""
	if d, ok := validation.ParseISODate(stay.dateFrom); ok {
		dates = d.Format("02.01.2006")
	}
	if d, ok := validation.ParseISODate(stay.dateTo); ok {
		dates = dates + " – " + d.Format("02.01.2006")
	}
	return stay.property + " · " + dates
}

// watchStay raises or resolves the two cards of one readable stay and returns
// 1 when it raised a deadline alert.
func watchStay(ctx context.Context, pool *pgxpool.Pool, stay stayRow, p progressResult, start, now, today time.Time) (int, error) {
	id := strconv.FormatInt(stay.id, 10)
	key := "deadline:" + id
	mismatchKey := "headcount_mismatch:" + id
	settled := p.status == "reported" || p.status == "not_required"
	title := watchTitle(stay)
	aptID, resID := stay.propertyID, stay.id
	// Once the stay has started, a shortfall is said as such, so it is chased.
	if !settled && p.expected != nil && p.filled < *p.expected && start.Before(today) {
		detail := "Waiting for guest forms · " + strconv.Itoa(p.filled) + "/" + strconv.Itoa(*p.expected)
		if err := ubyport.RaiseAlert(ctx, pool, "warning", "headcount_mismatch", title, detail,
			mismatchKey, &aptID, &resID, nil, nil); err != nil {
			return 0, err
		}
	} else if err := ubyport.ResolveAlert(ctx, pool, mismatchKey); err != nil {
		return 0, err
	}
	if settled {
		return 0, ubyport.ResolveAlert(ctx, pool, key)
	}
	level := deadlines.Urgency(start, now)
	if level != "overdue" && level != "urgent" {
		return 0, ubyport.ResolveAlert(ctx, pool, key)
	}
	expected := "?"
	if p.expected != nil {
		expected = strconv.Itoa(*p.expected)
	}
	counts := strconv.Itoa(p.filled) + "/" + expected
	alertLevel, detail := "warning", "Due now · "+counts
	if level == "overdue" {
		countdown := deadlines.DescribeTimeLeft(start, now)
		if strings.HasPrefix(countdown, "overdue") {
			countdown = "O" + countdown[1:]
		}
		alertLevel, detail = "critical", countdown+" · "+counts
	}
	if err := ubyport.RaiseAlert(ctx, pool, alertLevel, "deadline", title, detail,
		key, &aptID, &resID, nil, nil); err != nil {
		return 0, err
	}
	return 1, nil
}
