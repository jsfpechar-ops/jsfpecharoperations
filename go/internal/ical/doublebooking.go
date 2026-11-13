package ical

// Double-booking alarm (brief 1172). After a feed reconciles, every pair of
// active stays of the apartment whose date ranges overlap raises one warning
// alert and queues one host e-mail while the pair stays open. The overlap is
// derived from the reservation rows on every sync, never stored, so the alert
// resolves itself when a stay is cancelled, moved or marked ignored.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// overlapPairsSQL is the overlapping_count predicate of
// App/app/routes/dashboard_calendar.py:54 as a self-join. date_to is exclusive:
// r1.date_to == r2.date_from is not an overlap. $2 is today (Europe/Prague):
// only stays that have not ended yet count, so the first sync after deploy
// does not alarm about overlaps from the past.
const overlapPairsSQL = `SELECT r1.id, r1.date_from, r1.date_to, r1.source,
       r2.id, r2.date_from, r2.date_to, r2.source
  FROM reservation r1
  JOIN reservation r2
    ON r2.apartment_id = r1.apartment_id AND r2.id > r1.id
   AND r2.date_from < r1.date_to AND r2.date_to > r1.date_from
 WHERE r1.apartment_id = $1 AND r1.status = 'active' AND r1.archived_at IS NULL
   AND r2.status = 'active' AND r2.archived_at IS NULL
   AND r1.date_to > $2 AND r2.date_to > $2
 ORDER BY r1.id, r2.id`

type stayPair struct {
	firstID, secondID         int64
	firstFrom, firstTo        string
	secondFrom, secondTo      string
	firstSource, secondSource string
}

// fmtDay is validation.fmt_date: ISO to DD.MM.YYYY, unparseable passes through.
func fmtDay(value string) string {
	t, err := time.Parse(dateLayout, value)
	if err != nil {
		return value
	}
	return t.Format("02.01.2006")
}

// fmtRange is validation.fmt_date_range: two dates joined by an en dash (U+2013).
func fmtRange(from, to string) string {
	return fmtDay(from) + " \u2013 " + fmtDay(to)
}

// checkDoubleBookings raises or resolves the double_booking alerts of one
// apartment from the stays currently stored. It only reads reservation rows;
// the only writes go through the pinned writers ubyport.RaiseAlert,
// ubyport.ResolveAlert and ubyport.EnqueueMail. The caller logs an error and
// continues: the reconciliation already succeeded and the next sync retries.
func checkDoubleBookings(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, apartmentID int64) error {
	var internalName *string
	err := pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1`, apartmentID).Scan(&internalName)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	property := "UbyHost"
	if internalName != nil && *internalName != "" {
		property = *internalName
	}

	today := time.Now().In(prague).Format(dateLayout)
	rows, err := pool.Query(ctx, overlapPairsSQL, apartmentID, today)
	if err != nil {
		return err
	}
	var pairs []stayPair
	for rows.Next() {
		var p stayPair
		if err := rows.Scan(&p.firstID, &p.firstFrom, &p.firstTo, &p.firstSource,
			&p.secondID, &p.secondFrom, &p.secondTo, &p.secondSource); err != nil {
			rows.Close()
			return err
		}
		pairs = append(pairs, p)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}

	openRows, err := pool.Query(ctx,
		`SELECT dedupe_key FROM alert WHERE kind = 'double_booking' AND apartment_id = $1 AND resolved_at IS NULL`,
		apartmentID)
	if err != nil {
		return err
	}
	open := map[string]bool{}
	for openRows.Next() {
		var key string
		if err := openRows.Scan(&key); err != nil {
			openRows.Close()
			return err
		}
		open[key] = true
	}
	openRows.Close()
	if err := openRows.Err(); err != nil {
		return err
	}

	current := map[string]bool{}
	for _, p := range pairs {
		key := fmt.Sprintf("double_booking:%d:%d:%d", apartmentID, p.firstID, p.secondID)
		current[key] = true
		if open[key] {
			continue // already alarmed; one e-mail per pair while it stays open
		}
		dates := fmtRange(p.firstFrom, p.firstTo)
		otherDates := fmtRange(p.secondFrom, p.secondTo)
		otherSource := p.secondSource
		if otherSource == "" {
			otherSource = "ical"
		}
		aid, rid := apartmentID, p.secondID
		title := fmt.Sprintf("%s: two bookings overlap on %s.", property, dates)
		detail := fmt.Sprintf("A second booking (%s, source %s) covers the same nights. Only one of them can happen: cancel or move one booking on the portal.", otherDates, otherSource)
		if err := ubyport.RaiseAlert(ctx, pool, "warning", "double_booking", title, detail, key, &aid, &rid, nil,
			ubyport.AlertParams{
				"property": property, "dates": dates,
				"other_dates": otherDates, "other_source": otherSource,
			}); err != nil {
			return err
		}
		if _, err := ubyport.QueueDoubleBookingMail(ctx, pool, getenv, ubyport.DoubleBooking{
			ApartmentID: apartmentID, Property: property, Key: key,
			FirstID: p.firstID, FirstFrom: p.firstFrom, FirstTo: p.firstTo, FirstSource: p.firstSource,
			SecondID: p.secondID, SecondFrom: p.secondFrom, SecondTo: p.secondTo, SecondSource: p.secondSource,
		}); err != nil {
			log.Printf("ical double_booking mail not queued apartment_id=%d key=%s: %v", apartmentID, key, err)
		}
		log.Printf("ical_double_booking apartment_id=%d pair=%d:%d dates=%s other=%s source=%s",
			apartmentID, p.firstID, p.secondID, dates, otherDates, otherSource)
	}
	for key := range open {
		if !current[key] {
			if err := ubyport.ResolveAlert(ctx, pool, key); err != nil {
				return err
			}
			log.Printf("ical_double_booking_resolved apartment_id=%d key=%s", apartmentID, key)
		}
	}
	return nil
}
