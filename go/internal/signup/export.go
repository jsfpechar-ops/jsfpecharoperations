package signup

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// ErrBadTime is datetime.fromisoformat refusing a stored timestamp.
var ErrBadTime = errors.New("signup: stored time is not ISO 8601")

// isoLayouts are the fromisoformat forms the app stores; a value without an
// offset is UTC, as conversion_time assumes.
var isoLayouts = []string{
	"2006-01-02T15:04:05.999999Z07:00",
	"2006-01-02 15:04:05.999999Z07:00",
	"2006-01-02T15:04:05.999999",
	"2006-01-02 15:04:05.999999",
	"2006-01-02",
}

// ConversionTime is conversion_time: a stored UTC time as Prague time with
// its offset, "yyyy-MM-dd HH:mm:ss+zzzz".
func ConversionTime(stored string) (string, error) {
	for _, layout := range isoLayouts {
		if t, err := time.Parse(layout, stored); err == nil {
			zone, err := time.LoadLocation("Europe/Prague")
			if err != nil {
				return "", err
			}
			return t.In(zone).Format("2006-01-02 15:04:05-0700"), nil
		}
	}
	return "", ErrBadTime
}

// ExportRow is one row of export_rows.
type ExportRow struct {
	ID              int64
	Gclid           string
	EmailVerifiedAt string
}

// isoDaysAgo is _iso_days_ago.
func isoDaysAgo(days int, now time.Time) string {
	return session.UTCNow(now.Add(-time.Duration(days) * 24 * time.Hour))
}

// ExportRows is export_rows: consented, verified, not withdrawn Google
// clicks from the last 85 days; with again also the ones exported before.
func ExportRows(ctx context.Context, pool *pgxpool.Pool, now time.Time, again bool) ([]ExportRow, error) {
	sql := `SELECT c.id, c.gclid, u.email_verified_at FROM ad_click c
		JOIN user_account u ON u.id = c.user_account_id
		WHERE c.platform = $1 AND c.gclid IS NOT NULL AND c.withdrawn_at IS NULL
		AND c.ids_deleted_at IS NULL AND u.email_verified_at IS NOT NULL
		AND c.clicked_at >= $2`
	if !again {
		sql += " AND c.uploaded_at IS NULL"
	}
	sql += " ORDER BY u.email_verified_at, c.id"
	rows, err := pool.Query(ctx, sql, Google, isoDaysAgo(GoogleExportDays, now))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ExportRow
	for rows.Next() {
		var r ExportRow
		if err := rows.Scan(&r.ID, &r.Gclid, &r.EmailVerifiedAt); err != nil {
			return nil, err
		}
		if CleanGclid(r.Gclid) != "" {
			out = append(out, r)
		}
	}
	return out, rows.Err()
}

// csvField is csv.writer's QUOTE_MINIMAL with the default dialect.
func csvField(s string) string {
	if strings.ContainsAny(s, ",\"\r\n") {
		return `"` + strings.ReplaceAll(s, `"`, `""`) + `"`
	}
	return s
}

func csvRow(fields []string) string {
	out := make([]string, len(fields))
	for i, f := range fields {
		out[i] = csvField(f)
	}
	return strings.Join(out, ",") + "\r\n"
}

// ConversionsCSV is conversions_csv: the Google Ads offline click-conversion file.
func ConversionsCSV(getenv func(string) string, rows []ExportRow) (string, error) {
	var b strings.Builder
	b.WriteString("Parameters:TimeZone=Europe/Prague\r\n")
	b.WriteString(csvRow(CSVHeader))
	name := conversionName(getenv)
	for _, r := range rows {
		when, err := ConversionTime(r.EmailVerifiedAt)
		if err != nil {
			return "", err
		}
		b.WriteString(csvRow([]string{r.Gclid, name, when, ConsentGranted, ConsentDenied}))
	}
	return b.String(), nil
}

// ExportConversions is export_conversions: the CSV body and its row count;
// rows not exported before are marked uploaded_at.
func ExportConversions(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now time.Time, again bool) (string, int, error) {
	rows, err := ExportRows(ctx, pool, now, again)
	if err != nil {
		return "", 0, err
	}
	body, err := ConversionsCSV(getenv, rows)
	if err != nil {
		return "", 0, err
	}
	if len(rows) > 0 && !again {
		ids := make([]int64, len(rows))
		for i, r := range rows {
			ids[i] = r.ID
		}
		if _, err := pool.Exec(ctx, `UPDATE ad_click SET uploaded_at = $1 WHERE uploaded_at IS NULL AND id = ANY($2)`,
			session.UTCNow(now), ids); err != nil {
			return "", 0, err
		}
	}
	return body, len(rows), nil
}
