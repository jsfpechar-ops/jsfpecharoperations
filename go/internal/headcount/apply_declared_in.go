package headcount

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// ApplyDeclaredInTx mirrors headcount.apply_declared_in on an open transaction.
// The caller must hold the reservation advisory lock or allow this function to take it.
func ApplyDeclaredInTx(ctx context.Context, tx pgx.Tx, reservationID int64, count int, now time.Time) (string, *int64, error) {
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "reservation", int32(reservationID)); err != nil {
		return "", nil, err
	}
	var status string
	var archived *string
	var override *int64
	var old *int64
	var reduced *int64
	err := tx.QueryRow(ctx, `SELECT status, archived_at, expected_guests_override, declared_guests, lead_reduced_guests
		FROM reservation WHERE id = $1`, reservationID).Scan(&status, &archived, &override, &old, &reduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return "stay_gone", nil, nil
	}
	if err != nil {
		return "", nil, err
	}
	if status != "active" || archived != nil {
		return "stay_gone", old, nil
	}
	if override != nil && *override != 0 {
		return "host_set", old, nil
	}
	if count < 1 {
		return "out_of_range", old, nil
	}
	if count > 60 {
		return "above_ceiling", old, nil
	}
	if old != nil && int(*old) == count {
		return "unchanged", old, nil
	}
	if reduced != nil && int(*reduced) == count {
		return "unchanged", old, nil
	}
	var live int
	if err := tx.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, reservationID).Scan(&live); err != nil {
		return "", nil, err
	}
	if count < max(1, live) {
		return "below_floor", old, nil
	}
	stamp := now.UTC().Format("2006-01-02T15:04:05") + "+00:00"
	var tag pgconn.CommandTag
	tag, err = tx.Exec(ctx, `UPDATE reservation SET declared_guests = $1,
		lead_reduced_guests = NULL, lead_reduced_from = NULL, lead_reduced_at = NULL,
		updated_at = $2 WHERE id = $3`, count, stamp, reservationID)
	if err != nil {
		return "", nil, err
	}
	if tag.RowsAffected() == 0 {
		return "stay_gone", old, nil
	}
	return "saved", old, nil
}
