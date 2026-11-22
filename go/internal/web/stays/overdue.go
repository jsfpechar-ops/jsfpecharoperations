package stays

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// overdueUnfinishedIDs is admin._overdue_unfinished_ids: stays the dashboard
// still treats as overdue and unfinished (reporting.FINISHED_STATUSES excluded).
func overdueUnfinishedIDs(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, ownerID int64, at time.Time) ([]int64, error) {
	today := civilDate(at)
	start := formatISODate(today.AddDate(0, 0, -45))
	end := formatISODate(today.AddDate(0, 0, 21))
	rows, err := pool.Query(ctx, `SELECT r.id, r.date_from, r.date_to, r.declared_guests,
		r.expected_guests_override, r.lead_reduced_guests
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL AND r.archived_at IS NULL
		AND a.owner_user_id = $1 AND r.date_from BETWEEN $2 AND $3
		ORDER BY r.date_from`, ownerID, start, end)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var stays []calendar.AlertStay
	for rows.Next() {
		var s calendar.AlertStay
		if err := rows.Scan(&s.ID, &s.DateFrom, &s.DateTo, &s.Declared, &s.Override, &s.Reduced); err != nil {
			return nil, err
		}
		stays = append(stays, s)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(stays) == 0 {
		return nil, nil
	}
	progs, err := calendar.AlertProgresses(ctx, pool, getenv, stays, at)
	if err != nil {
		return nil, err
	}
	now := deadlines.LocalNow(at)
	var ids []int64
	for _, s := range stays {
		p := progs[s.ID]
		if p.Unreadable {
			continue
		}
		if p.Status == "reported" || p.Status == "not_required" {
			continue
		}
		level := "future"
		if p.HasAnchor {
			level = deadlines.Urgency(p.Anchor, now)
		}
		if level != "overdue" {
			continue
		}
		// Python keeps a stay here for as long as its police deadline is past
		// and a guest is still unfiled, however long ago the guests left
		// (reporting.dashboard_rows only ages out *finished* stays, and those
		// were skipped above).
		ids = append(ids, s.ID)
	}
	return ids, nil
}

func civilDate(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}
