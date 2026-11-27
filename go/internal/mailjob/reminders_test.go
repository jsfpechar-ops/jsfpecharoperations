package mailjob

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
)

// now is 2026-11-15 10:00 in Prague (09:00 UTC): tomorrow is 2026-11-16.
var remindNow = time.Date(2026, 11, 15, 9, 0, 0, 0, time.UTC)

func remindTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_mailjob_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
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
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	remindApplyMigrations(t, pool)
	return pool
}

func remindApplyMigrations(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(context.Background(), up); err != nil {
			t.Fatalf("migration %s: %v", filepath.Base(f), err)
		}
	}
}

// remindFixture is one legal entity (host contact) and one active apartment.
func remindFixture(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO legal_entity (id, name, contact_email, created_at)
		   VALUES (1, 'Example Host s.r.o.', 'host@example.test', '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO apartment (id, legal_entity_id, owner_user_id, internal_name, permalink_token, active, created_at)
		   VALUES (1, 1, NULL, 'Harbour Flat', 'tok-a', 1, '2026-01-01T00:00:00+00:00')`,
	}
	for _, s := range stmts {
		if _, err := pool.Exec(ctx, s); err != nil {
			t.Fatal(err)
		}
	}
}

// remindStay inserts one active reservation; claimState "" means no claim row.
func remindStay(t *testing.T, pool *pgxpool.Pool, id int64, dateFrom, source, claimState string) {
	t.Helper()
	ctx := context.Background()
	stamp := "2026-11-15T09:00:00+00:00"
	if _, err := pool.Exec(ctx,
		`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, declared_guests, status, created_at, updated_at)
		   VALUES ($1, 1, $2, $3, $4, $5, 2, 'active', $6, $6)`,
		id, source, fmt.Sprintf("uid-%d", id), dateFrom, dateFrom, stamp); err != nil {
		t.Fatal(err)
	}
	if claimState == "" {
		return
	}
	claimed := "2026-11-14T10:00:00+00:00" // 23 h before now: past the 6 h maturity
	if _, err := pool.Exec(ctx,
		`INSERT INTO reservation_claim (reservation_id, state, email, email_masked, lang, claimed_at, created_at, updated_at)
		   VALUES ($1, $2, 'guest@example.test', 'g***@example.test', 'en', $3, $4, $4)`,
		id, claimState, claimed, stamp); err != nil {
		t.Fatal(err)
	}
}

func remindOutbox(t *testing.T, pool *pgxpool.Pool) []string {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT idempotency_key || ' ' || to_email || ' ' || COALESCE(payload, '') FROM email_outbox ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			t.Fatal(err)
		}
		out = append(out, s)
	}
	return out
}

func remindAlertOpen(t *testing.T, pool *pgxpool.Pool, key string) (open int, resolved int) {
	t.Helper()
	if err := pool.QueryRow(context.Background(),
		`SELECT count(*) FILTER (WHERE resolved_at IS NULL), count(*) FILTER (WHERE resolved_at IS NOT NULL)
		   FROM alert WHERE dedupe_key = $1`, key).Scan(&open, &resolved); err != nil {
		t.Fatal(err)
	}
	return open, resolved
}

func TestRemindersGuestQueuedOnce(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	pool := remindTestPool(t)
	remindFixture(t, pool)
	remindStay(t, pool, 10, "2026-11-16", "ical", claimStateClaimed)
	ctx := context.Background()

	first, err := SweepReminders(ctx, pool, remindNow)
	if err != nil {
		t.Fatal(err)
	}
	if first["guest"] != 1 || first["host"] != 0 || first["host_early"] != 0 || first["locked"] != 0 {
		t.Fatalf("first run summary: %v", first)
	}
	out := remindOutbox(t, pool)
	if len(out) != 1 {
		t.Fatalf("want 1 outbox row, got %d: %v", len(out), out)
	}
	if !strings.HasPrefix(out[0], "reminder_guest:10:2026-11-16 guest@example.test ") {
		t.Fatalf("bad key or address: %s", out[0])
	}
	if !strings.Contains(out[0], `"lang": "en"`) || !strings.Contains(out[0], `"text": `) {
		t.Fatalf("payload not in Python shape: %s", out[0])
	}

	// The second run finds the same key: no second row. Python's enqueue returns the
	// existing id, so the guest counter still ticks, and the test keeps that parity.
	if _, err := SweepReminders(ctx, pool, remindNow); err != nil {
		t.Fatal(err)
	}
	if n := len(remindOutbox(t, pool)); n != 1 {
		t.Fatalf("second run queued again: %d rows", n)
	}
}

func TestRemindersHostCheckinAlertRaisedThenResolved(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	pool := remindTestPool(t)
	remindFixture(t, pool)
	remindStay(t, pool, 20, "2026-11-15", "ical", "")
	ctx := context.Background()
	key := "guest_incomplete_checkin:20"

	checkInTime := time.Date(2026, 11, 15, 14, 5, 0, 0, time.UTC) // 15:05 Prague (default checkin_hour 15)
	sum, err := SweepReminders(ctx, pool, checkInTime)
	if err != nil {
		t.Fatal(err)
	}
	if sum["host"] != 1 {
		t.Fatalf("host summary: %v", sum)
	}
	out := remindOutbox(t, pool)
	if len(out) != 1 || !strings.HasPrefix(out[0], "reminder_host:checkin:20:2026-11-15 host@example.test ") {
		t.Fatalf("host mail: %v", out)
	}
	if open, _ := remindAlertOpen(t, pool, key); open != 1 {
		t.Fatalf("alert not raised: open=%d", open)
	}

	// The check-in day has passed: the warning is resolved, nothing new is queued.
	if _, err := pool.Exec(ctx, `UPDATE reservation SET date_from = '2026-11-14', date_to = '2026-11-14' WHERE id = 20`); err != nil {
		t.Fatal(err)
	}
	if _, err := SweepReminders(ctx, pool, checkInTime); err != nil {
		t.Fatal(err)
	}
	if open, resolved := remindAlertOpen(t, pool, key); open != 0 || resolved != 1 {
		t.Fatalf("alert not resolved: open=%d resolved=%d", open, resolved)
	}
}

func TestRemindersHostEarlyVariantSkipsAlert(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	pool := remindTestPool(t)
	remindFixture(t, pool)
	remindStay(t, pool, 30, "2026-11-16", "ical", "")
	evening := time.Date(2026, 11, 15, 17, 30, 0, 0, time.UTC) // 18:30 Prague
	sum, err := SweepReminders(context.Background(), pool, evening)
	if err != nil {
		t.Fatal(err)
	}
	if sum["host_early"] != 1 || sum["host"] != 0 {
		t.Fatalf("early summary: %v", sum)
	}
	out := remindOutbox(t, pool)
	if len(out) != 1 || !strings.HasPrefix(out[0], "reminder_host:day_before:30:2026-11-16 host@example.test ") {
		t.Fatalf("early host mail: %v", out)
	}
	if open, _ := remindAlertOpen(t, pool, "guest_incomplete_checkin:30"); open != 0 {
		t.Fatal("early variant must not raise the check-in alert")
	}

	// On check-in day at checkin_hour (15:00 Prague), a SECOND email with distinct checkin key queues.
	nextDayCheckIn := time.Date(2026, 11, 16, 14, 5, 0, 0, time.UTC) // 15:05 Prague
	sum2, err := SweepReminders(context.Background(), pool, nextDayCheckIn)
	if err != nil {
		t.Fatal(err)
	}
	if sum2["host"] != 1 {
		t.Fatalf("check-in summary after day-before: %v", sum2)
	}
	if out2 := remindOutbox(t, pool); len(out2) != 2 {
		t.Fatalf("expected 2 distinct host emails (day_before + checkin), got %d: %v", len(out2), out2)
	}
}

func TestRemindersQueueNothingWhenMailOffOrDemo(t *testing.T) {
	pool := remindTestPool(t)
	remindFixture(t, pool)
	remindStay(t, pool, 40, "2026-11-16", "ical", claimStateClaimed)
	remindStay(t, pool, 41, "2026-11-16", "demo", claimStateClaimed)
	ctx := context.Background()

	t.Setenv("UBYHOST_MAIL_BACKEND", "")
	sum, err := SweepReminders(ctx, pool, remindNow)
	if err != nil {
		t.Fatal(err)
	}
	if sum["guest"] != 0 || len(remindOutbox(t, pool)) != 0 {
		t.Fatalf("backend off must queue nothing: %v", sum)
	}

	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	sum, err = SweepReminders(ctx, pool, remindNow)
	if err != nil {
		t.Fatal(err)
	}
	out := remindOutbox(t, pool)
	if sum["guest"] != 1 || len(out) != 1 || !strings.HasPrefix(out[0], "reminder_guest:40:") {
		t.Fatalf("demo stay must not be mailed; real stay must: sum=%v out=%v", sum, out)
	}
}

// remindAssertContent checks one queued mail's subject, text and html against the
// mailnotify builder's output for the same input.
func remindAssertContent(t *testing.T, label, subject string, payload map[string]string, want mailnotify.Content) {
	t.Helper()
	if subject != want.Subject {
		t.Errorf("%s subject: got %q want %q", label, subject, want.Subject)
	}
	if payload["text"] != want.Text {
		t.Errorf("%s text differs from builder output:\ngot:\n%s\nwant:\n%s", label, payload["text"], want.Text)
	}
	if payload["html"] != want.HTML {
		t.Errorf("%s html differs from builder output (len got %d, want %d)", label, len(payload["html"]), len(want.HTML))
	}
}

func TestRemindersPayloadMatchesBuilders(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_PUBLIC_BASE_URL", "https://example.test/")
	t.Setenv("UBYHOST_APP_BASE_URL", "")
	pool := remindTestPool(t)
	remindFixture(t, pool)
	remindStay(t, pool, 10, "2026-11-16", "ical", claimStateClaimed)
	remindStay(t, pool, 30, "2026-11-16", "ical", "")
	evening := time.Date(2026, 11, 15, 17, 30, 0, 0, time.UTC) // 18:30 Prague
	if _, err := SweepReminders(context.Background(), pool, evening); err != nil {
		t.Fatal(err)
	}

	rows, err := pool.Query(context.Background(),
		`SELECT kind, subject, payload::text FROM email_outbox ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	type outboxRow struct {
		subject string
		payload map[string]string
	}
	byKind := map[string]outboxRow{}
	for rows.Next() {
		var kind, subject, raw string
		if err := rows.Scan(&kind, &subject, &raw); err != nil {
			t.Fatal(err)
		}
		var payload map[string]string
		if err := json.Unmarshal([]byte(raw), &payload); err != nil {
			t.Fatalf("payload is not JSON: %v: %s", err, raw)
		}
		byKind[kind] = outboxRow{subject: subject, payload: payload}
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	guest, ok := byKind[reminderGuestKind]
	if !ok {
		t.Fatalf("no guest reminder queued: %v", byKind)
	}
	host, ok := byKind[reminderHostKind]
	if !ok {
		t.Fatalf("no host reminder queued: %v", byKind)
	}

	wantGuest := mailnotify.BuildReminderGuest("https://example.test", mailnotify.ReminderGuestInput{
		Lang:         "en",
		PropertyName: "Harbour Flat",
		StayURL:      "https://example.test/l/tok-a/10",
		Host:         &mailnotify.Host{Name: "Example Host s.r.o.", Email: "host@example.test"},
		Filled:       0,
		Expected:     ptr(2),
	})
	remindAssertContent(t, "guest", guest.subject, guest.payload, wantGuest)
	if guest.payload["lang"] != "en" || guest.payload["reply_to"] != "host@example.test" {
		t.Errorf("guest payload lang/reply_to: %v", guest.payload)
	}

	wantHost := mailnotify.BuildReminderHost("https://example.test", mailnotify.ReminderHostInput{
		Lang:         "en",
		PropertyName: "Harbour Flat",
		Date:         "16.11.2026",
		Assigned:     "",
		StayURL:      "https://example.test/reservations/30#now",
		Claimed:      false,
		Filled:       0,
		Expected:     ptr(2),
		Tomorrow:     true,
	})
	remindAssertContent(t, "host", host.subject, host.payload, wantHost)
	if host.payload["lang"] != "en" {
		t.Errorf("host payload lang: %v", host.payload)
	}
	if _, has := host.payload["reply_to"]; has {
		t.Errorf("host payload must not carry reply_to: %v", host.payload)
	}
}
