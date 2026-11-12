// dsr_due.go is dsr.raise_due_alerts (App/app/dsr.py 153-172): a warning card
// for every data-subject request whose one-month deadline is near or past. It
// lives here with the other background-job ports (watch.go). Nothing calls it
// yet: brief 1132 §10 E adds the job kind. testdata/dsr_due_golden.json,
// written by App/scripts/dsr_due_golden.py, is the parity check.
package calendar

import (
	"context"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// dsrDueSoonDays is dsr.DUE_SOON_DAYS.
const dsrDueSoonDays = 5

// dsrDueSQL is the open and extended requests due on or before the horizon
// date ($1, YYYY-MM-DD). ubyhost_sqlite_date is the function db.sqlite_date_expr
// names on PostgreSQL (baseline migration): it reads due_at as SQLite date()
// does, so an offset moves the date to UTC. The order only makes runs repeatable.
const dsrDueSQL = `SELECT id, owner_user_id, due_at FROM data_subject_request
	WHERE status IN ('open', 'extended') AND ubyhost_sqlite_date(due_at) <= $1
	ORDER BY id`

type dsrDueRow struct {
	id    int64
	owner *int64
	dueAt string
}

// RaiseDSRDueAlerts raises (or refreshes) one `dsr_due` warning per request due
// within five days of today, and returns how many requests it found. It never
// resolves a card: a closed request's card is cleared by the host. today is the
// calendar date to compare (only its year, month and day are used, no zone
// conversion): Python's date.today() is the server's local date, so the caller
// passes the local time.
func RaiseDSRDueAlerts(ctx context.Context, pool *pgxpool.Pool, today time.Time) (int, error) {
	horizon := time.Date(today.Year(), today.Month(), today.Day()+dsrDueSoonDays, 0, 0, 0, 0, time.UTC).
		Format("2006-01-02")
	rs, err := pool.Query(ctx, dsrDueSQL, horizon)
	if err != nil {
		return 0, err
	}
	var rows []dsrDueRow
	for rs.Next() {
		var r dsrDueRow
		if err := rs.Scan(&r.id, &r.owner, &r.dueAt); err != nil {
			rs.Close()
			return 0, err
		}
		rows = append(rows, r)
	}
	rs.Close()
	if err := rs.Err(); err != nil {
		return 0, err
	}
	for _, r := range rows {
		err := ubyport.RaiseAlert(ctx, pool, "warning", "dsr_due",
			"Data-subject request due "+r.dueAt+".",
			"Handle it and record the outcome.",
			"dsr_due:"+strconv.FormatInt(r.id, 10),
			nil, nil, r.owner, ubyport.AlertParams{"due": r.dueAt})
		if err != nil {
			return 0, err
		}
	}
	return len(rows), nil
}
