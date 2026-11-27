package calendar

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"
)

func TestRunCheckInIncompleteAlarm_TimingIdempotencyAndResolve(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()

	var ownerID, leID, aptID, resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, created_at) VALUES ('host2094@example.test', 'x', 'host', '2026-01-01T00:00:00Z') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatalf("insert user: %v", err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, contact_email, seat, created_at) VALUES ($1, 'Host Entity', 'owner2094@example.test', 'Prague', '2026-01-01T00:00:00Z') RETURNING id`, ownerID).Scan(&leID); err != nil {
		t.Fatalf("insert entity: %v", err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, uby_name, permalink_token, active, checkin_hour, created_at) VALUES ($1, $2, 'Flat 2094', 'Flat 2094', 'tok2094', 1, 15, '2026-01-01T00:00:00Z') RETURNING id`, ownerID, leID).Scan(&aptID); err != nil {
		t.Fatalf("insert apartment: %v", err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at) VALUES ($1, 'uid2094', '2026-06-01', '2026-06-04', 'active', 'manual', 2, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z') RETURNING id`, aptID).Scan(&resID); err != nil {
		t.Fatalf("insert reservation: %v", err)
	}
	// Simulate an existing day-before email row with the day-before key so we verify it never blocks the check-in mail.
	if _, err := pool.Exec(ctx, `INSERT INTO email_outbox (kind, idempotency_key, to_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at) VALUES ('reminder_host', $1, 'owner2094@example.test', 'day before', '{}', 'sent', 1, '2026-05-31T16:00:00Z', '2026-05-31T16:00:00Z', '2026-05-31T16:00:00Z')`,
		fmt.Sprintf("reminder_host:day_before:%d:2026-06-01", resID)); err != nil {
		t.Fatalf("seed day_before mail: %v", err)
	}

	getenv := func(k string) string {
		switch k {
		case "UBYHOST_MAIL_BACKEND":
			return "log"
		case "UBYHOST_APP_URL", "UBYHOST_PUBLIC_URL":
			return "https://app.example.test"
		}
		return os.Getenv(k)
	}

	// 14:30 Prague = 12:30 UTC (CEST) -> before 15:00 check-in hour: must NOT fire.
	before := time.Date(2026, 6, 1, 12, 30, 0, 0, time.UTC)
	n, err := RunCheckInIncompleteAlarm(ctx, pool, getenv, before)
	if err != nil {
		t.Fatalf("before checkin: %v", err)
	}
	if n != 0 {
		t.Fatalf("expected 0 alarms before checkin_hour, got %d", n)
	}

	// 15:05 Prague = 13:05 UTC -> at check-in hour: must raise alert and queue check-in mail.
	atCheckIn := time.Date(2026, 6, 1, 13, 5, 0, 0, time.UTC)
	n, err = RunCheckInIncompleteAlarm(ctx, pool, getenv, atCheckIn)
	if err != nil {
		t.Fatalf("at checkin: %v", err)
	}
	if n != 1 {
		t.Fatalf("expected 1 alarm at checkin_hour, got %d", n)
	}

	var activeAlerts, checkInMails int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, fmt.Sprintf("guest_incomplete_checkin:%d", resID)).Scan(&activeAlerts); err != nil {
		t.Fatal(err)
	}
	if activeAlerts != 1 {
		t.Fatalf("expected 1 active alert, got %d", activeAlerts)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = $1`, fmt.Sprintf("reminder_host:checkin:%d:2026-06-01", resID)).Scan(&checkInMails); err != nil {
		t.Fatal(err)
	}
	if checkInMails != 1 {
		t.Fatalf("expected 1 checkin email queued, got %d", checkInMails)
	}

	// Repeat run is idempotent (still 1 email row).
	if _, err := RunCheckInIncompleteAlarm(ctx, pool, getenv, atCheckIn.Add(30*time.Minute)); err != nil {
		t.Fatalf("repeat run: %v", err)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = $1`, fmt.Sprintf("reminder_host:checkin:%d:2026-06-01", resID)).Scan(&checkInMails); err != nil {
		t.Fatal(err)
	}
	if checkInMails != 1 {
		t.Fatalf("expected still 1 checkin email after repeat run, got %d", checkInMails)
	}

	// Next day (past check-in day) automatically resolves the alert.
	nextDay := time.Date(2026, 6, 2, 10, 0, 0, 0, time.UTC)
	if _, err := RunCheckInIncompleteAlarm(ctx, pool, getenv, nextDay); err != nil {
		t.Fatalf("next day: %v", err)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, fmt.Sprintf("guest_incomplete_checkin:%d", resID)).Scan(&activeAlerts); err != nil {
		t.Fatal(err)
	}
	if activeAlerts != 0 {
		t.Fatalf("expected alert resolved next day, still %d active", activeAlerts)
	}
}
