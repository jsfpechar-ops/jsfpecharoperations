package ical

import (
	"context"
	"fmt"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

func testGetenv(key string) string {
	switch key {
	case "UBYHOST_MAIL_BACKEND":
		return "console"
	case "UBYHOST_PUBLIC_BASE_URL", "UBYHOST_APP_BASE_URL":
		return "https://app.example.test"
	}
	return ""
}

func seedLegalEntity(t *testing.T, pool *pgxpool.Pool, apartmentID int64) {
	t.Helper()
	ctx := context.Background()
	var entityID int64
	must(t, pool.QueryRow(ctx,
		`INSERT INTO legal_entity (name, contact_email, created_at) VALUES ('Host s.r.o.', 'host@example.test', $1) RETURNING id`,
		ubyport.UTCNow()).Scan(&entityID))
	_, err := pool.Exec(ctx, `UPDATE apartment SET legal_entity_id = $1 WHERE id = $2`, entityID, apartmentID)
	must(t, err)
}

func TestDoubleBookingRaisesAlertAndMailOnce(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	seedLegalEntity(t, pool, aid)
	r1 := seedReservation(t, pool, aid, "abnb-1", "2027-05-05", "2027-05-08")
	r2 := seedReservation(t, pool, aid, "b-1", "2027-05-07", "2027-05-10")
	_, err := pool.Exec(ctx, `UPDATE reservation SET source = 'booking' WHERE id = $1`, r2)
	must(t, err)
	key := fmt.Sprintf("double_booking:%d:%d:%d", aid, r1, r2)

	must(t, checkDoubleBookings(ctx, pool, testGetenv, aid))
	if got := openAlerts(t, pool, key); got != 1 {
		t.Fatalf("open alerts = %d, want 1", got)
	}
	if got := scalarInt(t, pool,
		`SELECT COUNT(*) FROM email_outbox WHERE kind = 'double_booking' AND idempotency_key = $1 AND state = 'queued'`, key); got != 1 {
		t.Fatalf("outbox rows = %d, want 1", got)
	}

	must(t, checkDoubleBookings(ctx, pool, testGetenv, aid))
	if got := openAlerts(t, pool, key); got != 1 {
		t.Fatalf("after rerun open alerts = %d, want 1", got)
	}
	if got := scalarInt(t, pool,
		`SELECT COUNT(*) FROM email_outbox WHERE kind = 'double_booking' AND idempotency_key = $1`, key); got != 1 {
		t.Fatalf("after rerun outbox rows = %d, want 1", got)
	}

	_, err = pool.Exec(ctx, `UPDATE reservation SET status = 'cancelled' WHERE id = $1`, r2)
	must(t, err)
	must(t, checkDoubleBookings(ctx, pool, testGetenv, aid))
	var resolved bool
	must(t, pool.QueryRow(ctx, `SELECT resolved_at IS NOT NULL FROM alert WHERE dedupe_key = $1`, key).Scan(&resolved))
	if !resolved {
		t.Fatal("alert not resolved after the overlap ended")
	}
}

func TestDoubleBookingIgnoresAdjacentAndIgnored(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	seedReservation(t, pool, aid, "a-1", "2027-06-01", "2027-06-03")
	seedReservation(t, pool, aid, "a-2", "2027-06-03", "2027-06-05")
	seedReservation(t, pool, aid, "i-1", "2027-06-10", "2027-06-12")
	r4 := seedReservation(t, pool, aid, "i-2", "2027-06-11", "2027-06-13")
	_, err := pool.Exec(ctx, `UPDATE reservation SET status = 'ignored' WHERE id = $1`, r4)
	must(t, err)
	// A past overlap (both stays ended before today) must not alert either.
	seedReservation(t, pool, aid, "old-1", "2020-01-01", "2020-01-05")
	seedReservation(t, pool, aid, "old-2", "2020-01-03", "2020-01-07")

	must(t, checkDoubleBookings(ctx, pool, testGetenv, aid))
	if got := scalarInt(t, pool, `SELECT COUNT(*) FROM alert WHERE kind = 'double_booking' AND apartment_id = $1`, aid); got != 0 {
		t.Fatalf("alerts = %d, want 0", got)
	}
}

func TestDoubleBookingFiresFromSyncFeed(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feedID := seedFeed(t, pool, aid)
	icsText := "BEGIN:VCALENDAR\r\n" +
		"VERSION:2.0\r\n" +
		"BEGIN:VEVENT\r\n" +
		"UID:abnb-1\r\n" +
		"DTSTART;VALUE=DATE:20270505\r\n" +
		"DTEND;VALUE=DATE:20270508\r\n" +
		"SUMMARY:Reserved\r\n" +
		"END:VEVENT\r\n" +
		"BEGIN:VEVENT\r\n" +
		"UID:b-1\r\n" +
		"DTSTART;VALUE=DATE:20270507\r\n" +
		"DTEND;VALUE=DATE:20270510\r\n" +
		"SUMMARY:Reserved\r\n" +
		"END:VEVENT\r\n" +
		"END:VCALENDAR\r\n"
	_, err := SyncFeed(ctx, pool, testGetenv, Feed{ID: feedID, ApartmentID: aid, URL: "https://example.invalid/feed.ics"}, FetchOptions{}, &icsText)
	must(t, err)
	if got := scalarInt(t, pool,
		`SELECT COUNT(*) FROM alert WHERE kind = 'double_booking' AND apartment_id = $1 AND resolved_at IS NULL`, aid); got != 1 {
		t.Fatalf("open double_booking alerts = %d, want 1", got)
	}
}
