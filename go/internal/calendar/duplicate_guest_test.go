package calendar

import (
	"context"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"
)

func TestRunDuplicateGuestCheck_RaisesMailsAndResolves(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()

	var ownerID, leID, aptID, resID, g1ID, g2ID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, created_at) VALUES ('host2095@example.test', 'x', 'host', '2026-01-01T00:00:00Z') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, contact_email, seat, created_at) VALUES ($1, 'Host Entity', 'owner2095@example.test', 'Prague', '2026-01-01T00:00:00Z') RETURNING id`, ownerID).Scan(&leID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, uby_name, permalink_token, active, checkin_hour, created_at) VALUES ($1, $2, 'Flat 2095', 'Flat 2095', 'tok2095', 1, 15, '2026-01-01T00:00:00Z') RETURNING id`, ownerID, leID).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at) VALUES ($1, 'uid2095', '2026-06-01', '2026-06-04', 'active', 'manual', 2, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z') RETURNING id`, aptID).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO guest (reservation_id, surname, first_name, birth_date, nationality, submit_state, created_at, updated_at) VALUES ($1, 'Novak', 'Jan', '01021990', 'DEU', 'pending', '2026-05-30T10:00:00Z', '2026-05-30T10:00:00Z') RETURNING id`, resID).Scan(&g1ID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO guest (reservation_id, surname, first_name, birth_date, nationality, submit_state, created_at, updated_at) VALUES ($1, 'novak', 'Jan', '01021990', 'DEU', 'pending', '2026-05-30T10:05:00Z', '2026-05-30T10:05:00Z') RETURNING id`, resID).Scan(&g2ID); err != nil {
		t.Fatal(err)
	}

	getenv := func(k string) string {
		switch k {
		case "UBYHOST_MAIL_BACKEND":
			return "log"
		case "UBYHOST_APP_BASE_URL":
			return "https://app.example.test"
		}
		return os.Getenv(k)
	}

	now := time.Date(2026, 6, 1, 10, 0, 0, 0, time.UTC)
	n, err := RunDuplicateGuestCheck(ctx, pool, getenv, now)
	if err != nil {
		t.Fatalf("first run: %v", err)
	}
	if n != 1 {
		t.Fatalf("expected 1 duplicate alert, got %d", n)
	}

	// Verify alert exists and contains ZERO guest PII.
	var msg, detail string
	if err := pool.QueryRow(ctx, `SELECT message, detail FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, fmt.Sprintf("duplicate_guest_in_stay:%d", resID)).Scan(&msg, &detail); err != nil {
		t.Fatalf("alert missing: %v", err)
	}
	if strings.Contains(strings.ToLower(msg+detail), "novak") || strings.Contains(msg+detail, "01021990") {
		t.Fatalf("alert leaked guest PII: msg=%q detail=%q", msg, detail)
	}

	// Repeat run is idempotent: still 1 outbox email.
	if _, err := RunDuplicateGuestCheck(ctx, pool, getenv, now.Add(time.Hour)); err != nil {
		t.Fatalf("second run: %v", err)
	}
	var mailCount int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE kind = 'duplicate_guest_in_stay' AND reservation_id = $1`, resID).Scan(&mailCount); err != nil {
		t.Fatal(err)
	}
	if mailCount != 1 {
		t.Fatalf("expected 1 email, got %d", mailCount)
	}

	// Archiving the duplicate guest resolves the alert automatically.
	if _, err := pool.Exec(ctx, `UPDATE guest SET archived_at = '2026-06-01T11:00:00Z' WHERE id = $1`, g2ID); err != nil {
		t.Fatal(err)
	}
	if _, err := RunDuplicateGuestCheck(ctx, pool, getenv, now.Add(2*time.Hour)); err != nil {
		t.Fatalf("third run: %v", err)
	}
	var openAlerts int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, fmt.Sprintf("duplicate_guest_in_stay:%d", resID)).Scan(&openAlerts); err != nil {
		t.Fatal(err)
	}
	if openAlerts != 0 {
		t.Fatalf("expected alert resolved after archiving duplicate, got %d open", openAlerts)
	}
}
