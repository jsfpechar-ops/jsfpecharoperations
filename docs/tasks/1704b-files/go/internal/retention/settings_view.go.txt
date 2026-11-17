package retention

// Brief 1704b: the read side of Settings > Data and privacy (the numbers
// settings.html shows from housebook.retention_cutoff, expired_guest_ids and
// due_guest_ids). Nothing here writes. The owner is always given: an owner of
// nil would read every host, so these functions take a plain id.

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// HousebookCutoff is housebook.retention_cutoff(today): stays that ended
// before this date are due for deletion.
func HousebookCutoff(today time.Time) time.Time {
	return housebookCutoff(time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC))
}

const guestCountSQL = `SELECT COUNT(*) FROM guest g JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) >= $1
	AND COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) < $2
	AND a.owner_user_id = $3`

// ExpiredGuestCount is len(housebook.expired_guest_ids(today, owner)): the
// owner's guest records whose stay ended before the cutoff.
func ExpiredGuestCount(ctx context.Context, pool *pgxpool.Pool, today time.Time, owner int64) (int, error) {
	var n int
	err := pool.QueryRow(ctx, guestCountSQL, "0001-01-01", isoDate(HousebookCutoff(today)), owner).Scan(&n)
	return n, err
}

// DueGuestCount is len(housebook.due_guest_ids(today, within_days, owner)):
// the owner's guest records that reach the cutoff within the next withinDays.
func DueGuestCount(ctx context.Context, pool *pgxpool.Pool, today time.Time, withinDays int, owner int64) (int, error) {
	var n int
	err := pool.QueryRow(ctx, guestCountSQL,
		isoDate(HousebookCutoff(today)), isoDate(HousebookCutoff(today.AddDate(0, 0, withinDays))), owner).Scan(&n)
	return n, err
}
