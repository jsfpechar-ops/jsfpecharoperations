package booking

import (
	"context"
	"crypto/hmac"
	"errors"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// KeepPastDays is booking_ical.KEEP_PAST_DAYS.
const KeepPastDays = 30

// ApartmentForSlug is booking_ical.apartment_for_slug: a live or historic
// slug to its apartment id (feeds survive renames); ok is false for none.
func ApartmentForSlug(ctx context.Context, db DB, slug string) (int64, bool, error) {
	var id int64
	err := db.QueryRow(ctx, `SELECT apartment_id FROM property_slug WHERE slug = $1 LIMIT 1`, slug).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		err = db.QueryRow(ctx, `SELECT apartment_id FROM property_slug_history WHERE old_slug = $1 LIMIT 1`, slug).Scan(&id)
	}
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, false, nil
	}
	if err != nil {
		return 0, false, err
	}
	return id, true, nil
}

// FeedTokenOK is booking_ical.token_ok. Like Python it creates the
// apartment's token first when it has none.
func FeedTokenOK(ctx context.Context, db DB, apartmentID int64, token string) (bool, error) {
	want, err := ICalToken(ctx, db, apartmentID)
	if err != nil {
		return false, err
	}
	return hmac.Equal([]byte(want), []byte(token)), nil
}

func icsDay(iso string) (string, error) {
	d, ok := ParseISODate(iso)
	if !ok {
		return "", errBadStoredDate
	}
	return d.Format("20060102"), nil
}

func icsStamp(now time.Time) string {
	return now.UTC().Format("20060102T150405Z")
}

// ExportICS is booking_ical.export_ics(apartment_id, today=today): website
// and manual stays only, no personal data. now stamps DTSTAMP.
func ExportICS(ctx context.Context, db DB, apartmentID int64, today, now time.Time) (string, error) {
	since := isoDay(civil(today).AddDate(0, 0, -KeepPastDays))
	rows, err := db.Query(ctx, `SELECT id, date_from, date_to FROM reservation
		WHERE apartment_id = $1 AND status = 'active' AND archived_at IS NULL
		AND source IN ('site', 'manual') AND date_to >= $2
		ORDER BY date_from, id`, apartmentID, since)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	stamp := icsStamp(now)
	lines := []string{
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		"PRODID:-//UbyHost//Booking site//CS",
		"CALSCALE:GREGORIAN",
		"METHOD:PUBLISH",
	}
	for rows.Next() {
		var id int64
		var from, to string
		if err := rows.Scan(&id, &from, &to); err != nil {
			return "", err
		}
		start, err := icsDay(from)
		if err != nil {
			return "", err
		}
		end, err := icsDay(to)
		if err != nil {
			return "", err
		}
		lines = append(lines,
			"BEGIN:VEVENT",
			"UID:ubyhost-"+strconv.FormatInt(id, 10)+"@ubyhost.cz",
			"DTSTAMP:"+stamp,
			"DTSTART;VALUE=DATE:"+start,
			"DTEND;VALUE=DATE:"+end,
			"SUMMARY:Reserved",
			"END:VEVENT",
		)
	}
	if err := rows.Err(); err != nil {
		return "", err
	}
	lines = append(lines, "END:VCALENDAR")
	return strings.Join(lines, "\r\n") + "\r\n", nil
}

// StayICS is booking_manage.calendar_ics: one all-day event for the guest's
// own calendar, the apartment's name as summary, no personal data.
func StayICS(bookingID int64, dateFrom, dateTo, name string, now time.Time) (string, error) {
	start, err := icsDay(dateFrom)
	if err != nil {
		return "", err
	}
	end, err := icsDay(dateTo)
	if err != nil {
		return "", err
	}
	summary := strings.NewReplacer("\\", " ", ",", " ", ";", " ", "\n", " ").Replace(name)
	lines := []string{"BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//UbyHost//Booking//CS", "BEGIN:VEVENT",
		"UID:ubyhost-booking-" + strconv.FormatInt(bookingID, 10) + "@ubyhost.cz", "DTSTAMP:" + icsStamp(now),
		"DTSTART;VALUE=DATE:" + start, "DTEND;VALUE=DATE:" + end,
		"SUMMARY:" + summary, "END:VEVENT", "END:VCALENDAR"}
	return strings.Join(lines, "\r\n") + "\r\n", nil
}
