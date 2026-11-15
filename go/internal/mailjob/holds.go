// Package mailjob ports two scheduler steps from the Python app:
// expire_holds (App/app/claim.py) and expire_requests
// (App/app/booking_checkout.py).
package mailjob

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	_ "time/tzdata" // Europe/Prague must load on a slim image
)

const (
	holdStateProvisional = "provisional"
	holdStateUnclaimed   = "unclaimed"
	bookingRequested     = "requested"
	bookingExpired       = "expired"

	// configTimeZone mirrors config.TIMEZONE. Naive stored deadlines are read
	// in this zone, as _parse_provisional_until does.
	configTimeZone = "Europe/Prague"
)

// utcStamp formats t the way Python db.utcnow() does: whole seconds and a
// +00:00 offset, e.g. "2026-11-15T10:00:00+00:00". It matches jobs.Now.
func utcStamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// parseHoldDeadline normalises a stored provisional_until value to UTC, like
// claim.py _parse_provisional_until: a "Z" suffix is read as +00:00, and a
// value without an offset is taken to be local Prague time.
func parseHoldDeadline(value string) (time.Time, error) {
	s := strings.ReplaceAll(value, "Z", "+00:00")
	if t, err := time.Parse(time.RFC3339Nano, s); err == nil {
		return t.UTC(), nil
	}
	loc, err := time.LoadLocation(configTimeZone)
	if err != nil {
		return time.Time{}, err
	}
	for _, layout := range []string{
		"2006-01-02T15:04:05.999999999",
		"2006-01-02 15:04:05.999999999",
		"2006-01-02T15:04",
		"2006-01-02 15:04",
	} {
		if t, err := time.ParseInLocation(layout, s, loc); err == nil {
			return t.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unparseable provisional_until %q", value)
}

func keepFirst(first, next error) error {
	if first != nil {
		return first
	}
	return next
}

// ExpireHolds sets provisional claims whose deadline is at or before now back
// to unclaimed, clearing token_hash and provisional_until. It returns how many
// claims were expired. A row that fails is skipped and the first such error is
// returned alongside the count of the rows that did expire.
func ExpireHolds(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	stamp := utcStamp(now)
	nowUTC := now.UTC()

	rows, err := pool.Query(ctx,
		`SELECT reservation_id, provisional_until FROM reservation_claim
		 WHERE state = $1 AND provisional_until IS NOT NULL`, holdStateProvisional)
	if err != nil {
		return 0, err
	}
	type candidate struct {
		reservationID int64
		until         string
	}
	var found []candidate
	for rows.Next() {
		var c candidate
		if err := rows.Scan(&c.reservationID, &c.until); err != nil {
			rows.Close()
			return 0, err
		}
		found = append(found, c)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	n := 0
	var firstErr error
	for _, c := range found {
		until, err := parseHoldDeadline(c.until)
		if err != nil {
			firstErr = keepFirst(firstErr, err)
			continue
		}
		if until.After(nowUTC) {
			continue
		}
		if _, err := pool.Exec(ctx,
			`UPDATE reservation_claim SET state = $1, token_hash = NULL,
			 provisional_until = NULL, updated_at = $2
			 WHERE reservation_id = $3 AND state = $4`,
			holdStateUnclaimed, stamp, c.reservationID, holdStateProvisional); err != nil {
			firstErr = keepFirst(firstErr, err)
			continue
		}
		n++
	}
	return n, firstErr
}

// ExpireRequests moves booking requests still unconfirmed past their
// request_expires_at to expired, then deletes each one's booking_hold row so
// the dates are freed. It returns how many bookings moved. Like the Python job,
// a row that fails or has already changed status is skipped and does not count.
func ExpireRequests(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	stamp := utcStamp(now)

	// The text comparison uses COLLATE "C" to keep SQLite's byte-wise ordering.
	rows, err := pool.Query(ctx,
		`SELECT id, hold_id FROM site_booking
		 WHERE status = $1 AND request_expires_at IS NOT NULL
		   AND request_expires_at COLLATE "C" <= $2`, bookingRequested, stamp)
	if err != nil {
		return 0, err
	}
	type request struct {
		id     int64
		holdID *int64
	}
	var due []request
	for rows.Next() {
		var r request
		if err := rows.Scan(&r.id, &r.holdID); err != nil {
			rows.Close()
			return 0, err
		}
		due = append(due, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	done := 0
	var firstErr error
	for _, r := range due {
		// set_status(id, "expired") from requested: the only side effect is
		// status and updated_at. The status guard means a row that has moved on
		// since the select is left alone, as set_status would raise or return False.
		tag, err := pool.Exec(ctx,
			`UPDATE site_booking SET status = $1, updated_at = $2
			 WHERE id = $3 AND status = $4`,
			bookingExpired, stamp, r.id, bookingRequested)
		if err != nil {
			firstErr = keepFirst(firstErr, err)
			continue
		}
		if tag.RowsAffected() != 1 {
			continue
		}
		done++
		if r.holdID != nil && *r.holdID != 0 {
			if _, err := pool.Exec(ctx,
				`DELETE FROM booking_hold WHERE id = $1`, *r.holdID); err != nil {
				firstErr = keepFirst(firstErr, err)
			}
		}
	}
	return done, firstErr
}
