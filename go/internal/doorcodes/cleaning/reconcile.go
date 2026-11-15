package doorcleaning

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// reconcileWindowDays: stays that ended more than this many days ago are not reconciled.
const reconcileWindowDays = 30

type stay struct {
	ID          int64
	ApartmentID int64
	DateTo      string
}

// Reconcile is cleaning.reconcile(all_owners=True). It makes a cleaning_event for every
// active booking that ends within the window, moves unpinned events to a changed booking
// end date, and marks scheduled events whose booking is gone as source_cancelled. It
// returns the number of rows changed (Python: the sum of rowcounts). Each stay is one
// short transaction; a failure returns the count so far, as Python raises after the
// earlier stays are committed.
func Reconcile(ctx context.Context, pool *pgxpool.Pool, clock Clock) (int, error) {
	cutoff := pragueToday(clock.Now()).AddDate(0, 0, -reconcileWindowDays).Format("2006-01-02")
	rows, err := pool.Query(ctx,
		"SELECT r.id, r.apartment_id, r.date_to FROM reservation r "+
			"JOIN apartment a ON a.id = r.apartment_id WHERE r.status = 'active' "+
			"AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL "+
			"AND COALESCE(r.source, '') <> 'demo' AND r.date_to >= $1",
		cutoff)
	if err != nil {
		return 0, err
	}
	var stays []stay
	for rows.Next() {
		var s stay
		if err := rows.Scan(&s.ID, &s.ApartmentID, &s.DateTo); err != nil {
			rows.Close()
			return 0, err
		}
		stays = append(stays, s)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return 0, err
	}
	rows.Close()

	changed := 0
	for _, s := range stays {
		n, err := reconcileStay(ctx, pool, s, iso(clock.Now()))
		changed += n
		if err != nil {
			return changed, err
		}
	}
	// A dismissal remains a dismissal when its booking is cancelled and restored: only
	// 'scheduled' events are marked here.
	tag, err := pool.Exec(ctx,
		"UPDATE cleaning_event SET state = 'source_cancelled', revision = revision + 1, "+
			"updated_at = $1 WHERE state = 'scheduled' AND source_reservation_id IS NOT NULL "+
			"AND apartment_id IN (SELECT a.id FROM apartment a WHERE 1 = 1) "+
			"AND NOT EXISTS (SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id "+
			"WHERE r.id = cleaning_event.source_reservation_id AND r.status = 'active' "+
			"AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL)",
		iso(clock.Now()))
	if err != nil {
		return changed, err
	}
	return changed + int(tag.RowsAffected()), nil
}

// reconcileStay is one per-stay transaction of reconcile: insert the event if it is new,
// otherwise update it when the apartment or the end date changed or it was cancelled.
func reconcileStay(ctx context.Context, pool *pgxpool.Pool, s stay, now string) (int, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	inserted, err := tx.Exec(ctx,
		"INSERT INTO cleaning_event "+
			"(apartment_id, source_reservation_id, source_date, scheduled_date, created_at, updated_at) "+
			"VALUES ($1, $2, $3, $3, $4, $4) ON CONFLICT (source_reservation_id) DO NOTHING",
		s.ApartmentID, s.ID, s.DateTo, now)
	if err != nil {
		return 0, err
	}
	changed := int(inserted.RowsAffected())

	updated, err := tx.Exec(ctx,
		"UPDATE cleaning_event SET apartment_id = $1, source_date = $2, "+
			"scheduled_date = CASE WHEN overridden = 0 THEN $3 ELSE scheduled_date END, "+
			"state = CASE WHEN state = 'source_cancelled' THEN 'scheduled' ELSE state END, "+
			"revision = revision + 1, updated_at = $4 WHERE source_reservation_id = $5 "+
			"AND (apartment_id <> $6 OR source_date <> $7 OR state = 'source_cancelled')",
		s.ApartmentID, s.DateTo, s.DateTo, now, s.ID, s.ApartmentID, s.DateTo)
	if err != nil {
		return changed, err
	}
	changed += int(updated.RowsAffected())
	if err := tx.Commit(ctx); err != nil {
		return changed, fmt.Errorf("doorcleaning: commit stay %d: %w", s.ID, err)
	}
	return changed, nil
}

// errNoRow reports whether err is pgx's "no rows" answer.
func errNoRow(err error) bool {
	return errors.Is(err, pgx.ErrNoRows)
}
