package stays

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
)

// Row is one line of the stays table (reservation + progress metadata).
type Row struct {
	Reservation     Reservation
	Progress        calendar.AlertProgress
	Controls        map[string]any
	ApartmentActive bool
}

// Reservation is reservation r.* plus joined apartment columns from the list query.
type Reservation struct {
	ID               int64
	ApartmentID      int64
	DateFrom, DateTo string
	Status, Source   string
	InternalName     string
	PermalinkToken   string
	AutomationMode   string
	SubmitAfterHours *int64
	PermalinkSlug    *string
}

// List runs the reservations_list query and builds the view model.
func List(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, accountID int64, p Params, at time.Time) (View, error) {
	todayISO := formatISODate(civilDate(at))
	var overdueIDs []int64
	if p.DateRange == "upcoming" && p.DateFrom != "" {
		var err error
		overdueIDs, err = overdueUnfinishedIDs(ctx, pool, getenv, accountID, at)
		if err != nil {
			return View{}, err
		}
	}
	sql, args := listSQL(accountID, p, todayISO, overdueIDs)
	var total int
	if err := pool.QueryRow(ctx, "SELECT COUNT(*) AS n FROM ("+sql+") AS sub", args...).Scan(&total); err != nil {
		return View{}, err
	}
	pageCount := max(1, (total+PageSize-1)/PageSize)
	page := p.Page
	if page < 1 {
		page = 1
	}
	if page > pageCount {
		page = pageCount
	}
	offset := (page - 1) * PageSize
	orderSQL, orderArgs := listOrder(sql, args, todayISO, overdueIDs, offset)
	rows, err := pool.Query(ctx, orderSQL, orderArgs...)
	if err != nil {
		return View{}, err
	}
	defer rows.Close()
	var alertStays []calendar.AlertStay
	type scanned struct {
		res    Reservation
		active int
	}
	var scannedRows []scanned
	for rows.Next() {
		var r Reservation
		var active int
		if err := rows.Scan(
			&r.ID, &r.ApartmentID, &r.DateFrom, &r.DateTo, &r.Status, &r.Source,
			&r.InternalName, &r.PermalinkToken, &r.AutomationMode, &r.SubmitAfterHours, &r.PermalinkSlug, &active,
		); err != nil {
			return View{}, err
		}
		scannedRows = append(scannedRows, scanned{res: r, active: active})
		alertStays = append(alertStays, calendar.AlertStay{ID: r.ID, DateFrom: r.DateFrom, DateTo: r.DateTo})
	}
	if err := rows.Err(); err != nil {
		return View{}, err
	}
	progs, err := calendar.AlertProgresses(ctx, pool, getenv, alertStays, at)
	if err != nil {
		return View{}, err
	}
	out := make([]Row, 0, len(scannedRows))
	for _, s := range scannedRows {
		prog := progs[s.res.ID]
		out = append(out, Row{
			Reservation:     s.res,
			Progress:        prog,
			Controls:        map[string]any{},
			ApartmentActive: s.active != 0,
		})
	}
	return BuildView(p, out, total, page, pageCount), nil
}

func listSQL(owner int64, p Params, today string, overdueIDs []int64) (string, []any) {
	sql := `SELECT r.id, r.apartment_id, r.date_from, r.date_to, r.status, COALESCE(r.source, ''),
	a.internal_name, COALESCE(a.permalink_token, ''), COALESCE(a.automation_mode, ''), a.submit_after_hours,
	(SELECT s.slug FROM apartment_slug s WHERE s.apartment_id = a.id AND s.is_current = 1) AS permalink_slug,
	a.active
	FROM reservation r JOIN apartment a ON a.id = r.apartment_id
	WHERE a.owner_user_id IS NOT DISTINCT FROM $1`
	args := []any{owner}
	n := 1
	if p.ShowArchive {
		sql += " AND r.archived_at IS NOT NULL"
	} else {
		sql += " AND r.archived_at IS NULL"
	}
	if p.Status != "all" {
		n++
		sql += fmt.Sprintf(" AND r.status = $%d", n)
		args = append(args, p.Status)
	}
	if p.ApartmentID != 0 {
		n++
		sql += fmt.Sprintf(" AND a.id = $%d", n)
		args = append(args, p.ApartmentID)
	}
	if p.DateFrom != "" && p.DateRange == "upcoming" {
		if len(overdueIDs) > 0 {
			n++
			fromMark := n
			args = append(args, p.DateFrom)
			marks := make([]string, len(overdueIDs))
			for i, id := range overdueIDs {
				n++
				marks[i] = fmt.Sprintf("$%d", n)
				args = append(args, id)
			}
			sql += fmt.Sprintf(" AND (r.date_to >= $%d OR r.id IN (%s))", fromMark, strings.Join(marks, ","))
		} else {
			n++
			sql += fmt.Sprintf(" AND r.date_to >= $%d", n)
			args = append(args, p.DateFrom)
		}
	} else if p.DateFrom != "" {
		n++
		sql += fmt.Sprintf(" AND r.date_to >= $%d", n)
		args = append(args, p.DateFrom)
	}
	if p.DateTo != "" {
		n++
		if p.DateRange == "past" {
			sql += fmt.Sprintf(" AND r.date_to <= $%d", n)
		} else {
			sql += fmt.Sprintf(" AND r.date_from <= $%d", n)
		}
		args = append(args, p.DateTo)
	}
	if p.Report == "failed" {
		sql += ` AND EXISTS (SELECT 1 FROM guest g WHERE g.reservation_id = r.id AND g.submit_state IN ('error', 'blocked'))`
	}
	_ = today
	return sql, args
}

func listOrder(base string, args []any, today string, overdueIDs []int64, offset int) (string, []any) {
	out := append([]any(nil), args...)
	overdueFirst := ""
	if len(overdueIDs) > 0 {
		marks := make([]string, len(overdueIDs))
		for i, id := range overdueIDs {
			out = append(out, id)
			marks[i] = fmt.Sprintf("$%d", len(out))
		}
		overdueFirst = fmt.Sprintf("CASE WHEN r.id IN (%s) THEN 0 ELSE 1 END, ", strings.Join(marks, ","))
	}
	a, b, c := len(out)+1, len(out)+2, len(out)+3
	out = append(out, today, today, today)
	g := fmt.Sprintf("CASE WHEN r.date_from <= $%d AND r.date_to >= $%d THEN 0 WHEN r.date_from > $%d THEN 1 ELSE 2 END", a, b, c)
	limit := len(out) + 1
	offsetArg := len(out) + 2
	out = append(out, PageSize, offset)
	sql := base + fmt.Sprintf(` ORDER BY %s%s,
 CASE WHEN %s = 0 THEN r.date_to WHEN %s = 1 THEN r.date_from END ASC,
 CASE WHEN %s = 2 THEN r.date_to END DESC,
 r.date_from ASC, r.id ASC LIMIT $%d OFFSET $%d`, overdueFirst, g, g, g, g, limit, offsetArg)
	return sql, out
}
