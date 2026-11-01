package ical

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// testPool is a copy of ubyport's claimTestPool: a fresh database with the
// PostgreSQL migrations applied. It skips without UBYHOST_TEST_DATABASE_URL.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_ical_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	must(t, err)
	_, err = admin.Exec(ctx, "CREATE DATABASE "+name)
	_ = admin.Close(ctx)
	must(t, err)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	must(t, err)
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	must(t, err)
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	must(t, err)
	if len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		must(t, err)
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}

func noEnv(string) string { return "" }

func seedApartment(t *testing.T, pool *pgxpool.Pool) int64 {
	t.Helper()
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO apartment (internal_name, created_at) VALUES ($1, $2) RETURNING id`,
		"Test flat", ubyport.UTCNow()).Scan(&id)
	must(t, err)
	return id
}

func seedReservation(t *testing.T, pool *pgxpool.Pool, apartmentID int64, uid, dateFrom, dateTo string) int64 {
	t.Helper()
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, 'active', $5, $5) RETURNING id`,
		apartmentID, uid, dateFrom, dateTo, ubyport.UTCNow()).Scan(&id)
	must(t, err)
	return id
}

func seedGuest(t *testing.T, pool *pgxpool.Pool, reservationID int64, submitState, stayFrom, stayTo string) int64 {
	t.Helper()
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO guest (reservation_id, created_at, updated_at, submit_state, stay_from, stay_to)
		 VALUES ($1, $2, $2, $3, $4, $5) RETURNING id`,
		reservationID, ubyport.UTCNow(), submitState, stayFrom, stayTo).Scan(&id)
	must(t, err)
	return id
}

func seedClaim(t *testing.T, pool *pgxpool.Pool, reservationID int64, locked bool) {
	t.Helper()
	var lock any
	if locked {
		lock = ubyport.UTCNow()
	}
	_, err := pool.Exec(context.Background(),
		`INSERT INTO reservation_claim (reservation_id, created_at, updated_at, guest_access_locked_at)
		 VALUES ($1, $2, $2, $3)`, reservationID, ubyport.UTCNow(), lock)
	must(t, err)
}

func scalarInt(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) int64 {
	t.Helper()
	var n int64
	must(t, pool.QueryRow(context.Background(), sql, args...).Scan(&n))
	return n
}

func scalarText(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) string {
	t.Helper()
	var s string
	must(t, pool.QueryRow(context.Background(), sql, args...).Scan(&s))
	return s
}

func openAlerts(t *testing.T, pool *pgxpool.Pool, key string) int64 {
	t.Helper()
	return scalarInt(t, pool, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key)
}

func TestSyntheticKeysPure(t *testing.T) {
	summary := strings.Repeat("ž", 25)
	legacy := legacySyntheticUID("2026-07-01", "2026-07-05", summary)
	if want := "synthetic-2026-07-01-2026-07-05-" + strings.Repeat("ž", 20); legacy != want {
		t.Fatalf("legacy = %q, want %q", legacy, want)
	}
	uid := "synthetic-0123456789abcdef"
	got := strings.Join(syntheticAliases(uid, legacy, "2026-07-01"), "|")
	// The bare digest key equals uid here, so it is dropped (alias != uid).
	want := strings.Join([]string{legacy, "synthetic-0123456789abcdef-2026-07-01"}, "|")
	if got != want {
		t.Fatalf("aliases = %q, want %q", got, want)
	}
	if n := len(syntheticAliases("synthetic-xyz", legacy, "2026-07-01")); n != 1 {
		t.Fatalf("non-digest uid: %d aliases, want 1", n)
	}
	if n := len(syntheticAliases(legacy, legacy, "2026-07-01")); n != 0 {
		t.Fatalf("alias equal to uid must be dropped, got %d", n)
	}
	if d := syntheticDigest("synthetic-0123456789abcdef-2026-07-01"); d != "0123456789abcdef" {
		t.Fatalf("digest = %q", d)
	}
	if d := syntheticDigest("synthetic-ABC"); d != "" {
		t.Fatalf("bad digest = %q, want empty", d)
	}
}

func TestSendInFlight(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)

	idle := seedReservation(t, pool, apt, "u-idle", "2026-08-01", "2026-08-03")
	seedGuest(t, pool, idle, "pending", "2026-08-01", "2026-08-03")
	if got, err := sendInFlight(ctx, pool, idle); err != nil || got {
		t.Fatalf("no send: got %v, %v", got, err)
	}

	claimed := seedReservation(t, pool, apt, "u-claim", "2026-08-01", "2026-08-03")
	g := seedGuest(t, pool, claimed, "pending", "2026-08-01", "2026-08-03")
	_, err := pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'tok', $2)`,
		g, epochSeconds())
	must(t, err)
	if got, err := sendInFlight(ctx, pool, claimed); err != nil || !got {
		t.Fatalf("live claim: got %v, %v", got, err)
	}

	running := seedReservation(t, pool, apt, "u-run", "2026-08-01", "2026-08-03")
	g2 := seedGuest(t, pool, running, "pending", "2026-08-01", "2026-08-03")
	var sub int64
	must(t, pool.QueryRow(ctx,
		`INSERT INTO submission (apartment_id, created_at, state) VALUES ($1, $2, 'running') RETURNING id`,
		apt, ubyport.UTCNow()).Scan(&sub))
	_, err = pool.Exec(ctx, `UPDATE guest SET submission_id = $1 WHERE id = $2`, sub, g2)
	must(t, err)
	if got, err := sendInFlight(ctx, pool, running); err != nil || !got {
		t.Fatalf("running submission: got %v, %v", got, err)
	}
}

func TestFitUnsentGuestWindows(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)
	res := seedReservation(t, pool, apt, "u-fit", "2026-01-01", "2026-01-10")
	moving := seedGuest(t, pool, res, "pending", "2026-01-01", "2026-01-10")
	sent := seedGuest(t, pool, res, "sent", "2026-01-01", "2026-01-10")
	claimed := seedGuest(t, pool, res, "pending", "2026-01-01", "2026-01-10")
	_, err := pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'tok', $2)`,
		claimed, epochSeconds())
	must(t, err)

	moved, err := fitUnsentGuestWindows(ctx, pool, res, apt, "2026-01-03", "2026-01-07")
	must(t, err)
	if moved != 1 {
		t.Fatalf("moved = %d, want 1", moved)
	}
	if got := scalarText(t, pool, `SELECT stay_from || ' ' || stay_to FROM guest WHERE id = $1`, moving); got != "2026-01-03 2026-01-07" {
		t.Fatalf("moved guest window = %q", got)
	}
	if got := scalarText(t, pool, `SELECT stay_from || ' ' || stay_to FROM guest WHERE id = $1`, sent); got != "2026-01-01 2026-01-10" {
		t.Fatalf("sent guest window changed: %q", got)
	}
	if got := scalarText(t, pool, `SELECT stay_from || ' ' || stay_to FROM guest WHERE id = $1`, claimed); got != "2026-01-01 2026-01-10" {
		t.Fatalf("guest with live claim changed: %q", got)
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'guest_stay_window_fitted'`); n != 1 {
		t.Fatalf("audit rows = %d, want 1", n)
	}
	if n, err := fitUnsentGuestWindows(ctx, pool, res, apt, "not-a-date", "2026-01-07"); err != nil || n != 0 {
		t.Fatalf("bad date: %d, %v", n, err)
	}
}

func TestCancelExistingStay(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)
	const future = "2999-06-01"

	cancelled := seedReservation(t, pool, apt, "u-cancel", future, "2999-06-03")
	seedGuest(t, pool, cancelled, "pending", future, "2999-06-03")
	seedClaim(t, pool, cancelled, false)
	_, err := pool.Exec(ctx,
		`INSERT INTO email_outbox (idempotency_key, kind, created_at, updated_at, reservation_id, state)
		 VALUES ('k-cancel', 'mail', $1, $1, $2, 'queued')`, ubyport.UTCNow(), cancelled)
	must(t, err)
	stats := &SyncStats{}
	must(t, cancelExistingStay(ctx, pool, noEnv, apt, "u-cancel", stats))
	if stats.Cancelled != 1 {
		t.Fatalf("Cancelled = %d, want 1", stats.Cancelled)
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE id = $1 AND status = 'cancelled'`, cancelled); n != 1 {
		t.Fatal("stay not cancelled")
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1 AND guest_access_locked_at IS NOT NULL`, cancelled); n != 1 {
		t.Fatal("claim not locked")
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE reservation_id = $1 AND state = 'failed'`, cancelled); n != 1 {
		t.Fatal("queued mail not failed")
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_with_guests:%d", cancelled)); n != 1 {
		t.Fatalf("cancelled_with_guests alerts = %d, want 1", n)
	}

	reported := seedReservation(t, pool, apt, "u-sent", future, "2999-06-03")
	seedGuest(t, pool, reported, "sent", future, "2999-06-03")
	stats2 := &SyncStats{}
	must(t, cancelExistingStay(ctx, pool, noEnv, apt, "u-sent", stats2))
	if stats2.Cancelled != 0 {
		t.Fatal("sent guest: stay must not be cancelled")
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE id = $1 AND status = 'active'`, reported); n != 1 {
		t.Fatal("sent guest: stay must stay active")
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_after_report:%d", reported)); n != 1 {
		t.Fatalf("cancelled_after_report alerts = %d, want 1", n)
	}

	past := seedReservation(t, pool, apt, "u-past", "2000-01-01", "2000-01-03")
	seedGuest(t, pool, past, "pending", "2000-01-01", "2000-01-03")
	stats3 := &SyncStats{}
	must(t, cancelExistingStay(ctx, pool, noEnv, apt, "u-past", stats3))
	if stats3.Cancelled != 0 {
		t.Fatal("past stay must not be cancelled")
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE id = $1 AND status = 'active'`, past); n != 1 {
		t.Fatal("past stay must stay active")
	}
}

func TestRekeyLegacySynthetic(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)
	legacyUID := legacySyntheticUID("2026-07-01", "2026-07-05", "Booking")
	res := seedReservation(t, pool, apt, legacyUID, "2026-07-01", "2026-07-05")
	ev := Event{UID: "synthetic-0123456789abcdef", DateFrom: "2026-07-01", DateTo: "2026-07-05", Summary: "Booking"}

	row, found, err := existingReservation(ctx, pool, apt, ev)
	must(t, err)
	if !found || row.ID != res || row.UID != ev.UID {
		t.Fatalf("rekey: found=%v row=%+v", found, row)
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE uid = $1`, ev.UID); n != 1 {
		t.Fatalf("rows with new uid = %d, want 1", n)
	}
	again, found, err := existingReservation(ctx, pool, apt, ev)
	must(t, err)
	if !found || again.ID != res {
		t.Fatal("second lookup must find the re-keyed stay")
	}
}

func TestReopenGuestAccess(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)

	locked := seedReservation(t, pool, apt, "u-locked", "2026-09-01", "2026-09-03")
	seedClaim(t, pool, locked, true)
	ok, err := reopenGuestAccess(ctx, pool, locked)
	must(t, err)
	if !ok {
		t.Fatal("locked stay must reopen")
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1 AND guest_access_locked_at IS NULL AND guest_access_reopened_at IS NOT NULL`, locked); n != 1 {
		t.Fatal("reopen not recorded")
	}

	open := seedReservation(t, pool, apt, "u-open", "2026-09-01", "2026-09-03")
	seedClaim(t, pool, open, false)
	if ok, err := reopenGuestAccess(ctx, pool, open); err != nil || ok {
		t.Fatalf("unlocked stay: %v, %v", ok, err)
	}
	if ok, err := reopenGuestAccess(ctx, pool, open+1000); err != nil || ok {
		t.Fatalf("no claim row: %v, %v", ok, err)
	}
}

func seedFeed(t *testing.T, pool *pgxpool.Pool, apartmentID int64) int64 {
	t.Helper()
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO ical_feed (apartment_id, url, created_at) VALUES ($1, 'https://example.invalid/feed.ics', $2) RETURNING id`,
		apartmentID, ubyport.UTCNow()).Scan(&id)
	must(t, err)
	return id
}

func TestRecordFeedFailure(t *testing.T) {
	pool := testPool(t)
	apt := seedApartment(t, pool)
	id := seedFeed(t, pool, apt)
	feed := Feed{ID: id, ApartmentID: apt}
	must(t, recordFeedFailure(context.Background(), pool, feed, errors.New("boom")))
	if got := scalarText(t, pool, `SELECT last_status || ' ' || last_error FROM ical_feed WHERE id = $1`, id); got != "error boom" {
		t.Fatalf("feed row = %q", got)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("feed_error:%d", id)); n != 1 {
		t.Fatalf("feed_error alerts = %d, want 1", n)
	}
}

func TestReportImportLimits(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)
	id := seedFeed(t, pool, apt)
	label := "Airbnb"
	feed := Feed{ID: id, ApartmentID: apt, Label: &label}
	events := []Event{{UID: "u1", Summary: "Guest A"}}

	must(t, reportImportLimits(ctx, pool, feed, []string{"u1"}, []string{"r1"}, events))
	if n := openAlerts(t, pool, fmt.Sprintf("feed_duplicate_uid:%d", id)); n != 1 {
		t.Fatalf("duplicate alerts = %d, want 1", n)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("feed_recurring_event:%d", id)); n != 1 {
		t.Fatalf("recurring alerts = %d, want 1", n)
	}
	must(t, reportImportLimits(ctx, pool, feed, nil, nil, events))
	if n := openAlerts(t, pool, fmt.Sprintf("feed_duplicate_uid:%d", id)); n != 0 {
		t.Fatalf("duplicate alert not resolved: %d", n)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("feed_recurring_event:%d", id)); n != 0 {
		t.Fatalf("recurring alert not resolved: %d", n)
	}
}
