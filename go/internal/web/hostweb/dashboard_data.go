package hostweb

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

type apartmentRow struct {
	ID   int64
	Name string
}

// DashboardData is what dashboard.tmpl reads.
type DashboardData struct {
	Apartments []apartmentRow
	Rows       []stays.Row
	FeedCount  int
	TodayISO   string
	TodayLong  string
	Lang       string
	CalView    bool
}

func loadDashboard(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner int64, at time.Time, calView bool, lang string) (DashboardData, error) {
	today := stays.PragueToday(at)
	out := DashboardData{
		TodayISO:  today.Format("2006-01-02"),
		TodayLong: formatDateLong(lang, today),
		Lang:      lang,
		CalView:   calView,
	}
	rows, err := pool.Query(ctx,
		`SELECT id, internal_name FROM apartment
		 WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL
		 ORDER BY internal_name`, owner)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var a apartmentRow
		if err := rows.Scan(&a.ID, &a.Name); err != nil {
			return out, err
		}
		out.Apartments = append(out.Apartments, a)
	}
	if err := rows.Err(); err != nil {
		return out, err
	}
	var n int64
	if err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM ical_feed f
		 JOIN apartment a ON a.id = f.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL AND f.active = 1`, owner).Scan(&n); err != nil {
		return out, err
	}
	out.FeedCount = int(n)
	if len(out.Apartments) == 0 {
		return out, nil
	}
	end := today.AddDate(0, 0, 30).Format("2006-01-02")
	stayRows, err := pool.Query(ctx,
		`SELECT r.id, r.apartment_id, r.date_from, r.date_to, r.status, COALESCE(r.source, ''),
			COALESCE(r.summary, ''), r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
			a.internal_name, COALESCE(a.permalink_token, ''), COALESCE(a.automation_mode, ''), a.submit_after_hours,
			(SELECT s.slug FROM apartment_slug s WHERE s.apartment_id = a.id AND s.is_current = 1) AS permalink_slug,
			a.active
		 FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL AND r.archived_at IS NULL
		   AND a.owner_user_id IS NOT DISTINCT FROM $1 AND r.date_from <= $2
		 ORDER BY r.date_from`, owner, end)
	if err != nil {
		return out, err
	}
	defer stayRows.Close()
	var bare []stays.Row
	for stayRows.Next() {
		var r stays.Row
		var active int
		if err := stayRows.Scan(
			&r.Reservation.ID, &r.Reservation.ApartmentID, &r.Reservation.DateFrom, &r.Reservation.DateTo,
			&r.Reservation.Status, &r.Reservation.Source, &r.Reservation.Summary,
			&r.Reservation.Declared, &r.Reservation.Override, &r.Reservation.Reduced,
			&r.Reservation.InternalName, &r.Reservation.PermalinkToken, &r.Reservation.AutomationMode,
			&r.Reservation.SubmitAfterHours, &r.Reservation.PermalinkSlug, &active,
		); err != nil {
			return out, err
		}
		r.ApartmentActive = active != 0
		bare = append(bare, r)
	}
	if err := stayRows.Err(); err != nil {
		return out, err
	}
	out.Rows, _, err = stays.EnrichDashboardRows(ctx, pool, getenv, bare, at)
	return out, err
}

func formatDateLong(lang string, t time.Time) string {
	// host_i18n.date_long: keep ISO for golden stability when locale tables are absent.
	_ = lang
	return fmt.Sprintf("%d %s %d", t.Day(), t.Month().String()[:3], t.Year())
}
