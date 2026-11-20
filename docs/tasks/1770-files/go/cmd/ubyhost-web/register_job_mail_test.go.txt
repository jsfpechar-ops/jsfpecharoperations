package main

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// The mail job is registered every 5 minutes and its factory builds without
// a pool (parseGoKinds calls it with nil).
func TestMailJobIsRegistered(t *testing.T) {
	if goIntervals["mail"] != 5 {
		t.Fatalf("interval %d", goIntervals["mail"])
	}
	if _, ok := goHandlers(nil)["mail"]; !ok {
		t.Fatal("mail is not registered")
	}
	if _, err := parseGoKinds("mail"); err != nil {
		t.Fatalf("parseGoKinds: %v", err)
	}
}

// The handler sends a queued console row once, expires a due provisional
// hold, and pings nothing when no heartbeat URL is set. Console backend, no
// network. Skips without UBYHOST_TEST_DATABASE_URL, like the other DB tests.
func TestMailJobRunsAgainstDatabase(t *testing.T) {
	pool := mailJobTestPool(t)
	ctx := context.Background()

	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatal(err)
	}
	env := map[string]string{
		"UBYHOST_MAIL_BACKEND":       "console",
		"UBYHOST_DEPLOYMENT":         "staging",
		"UBYHOST_DATA_KEYS":          base64.URLEncoding.EncodeToString(key),
		"UBYHOST_DATA_KEY_LEGACY":    "0",
		"UBYHOST_LIFECYCLE_MAIL":     "",
		"UBYHOST_HEARTBEAT_MAIL_URL": "",
	}
	getenv := func(k string) string { return env[k] }

	const past = "2020-01-01T00:00:00+00:00"
	var outboxID int64
	if err := pool.QueryRow(ctx, `INSERT INTO email_outbox
		(idempotency_key, kind, to_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		VALUES ('mail-job-test-1', 'completion', 'guest@example.test', 'Subject', $1, 'queued', 0, $2, $2, $2)
		RETURNING id`, `{"text":"hello","html":"<p>hello</p>"}`, past).Scan(&outboxID); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO reservation_claim
		(reservation_id, state, token_hash, token_version, provisional_until, created_at, updated_at)
		VALUES (1, 'provisional', 'hash-expired', 1, $1, $1, $1)`, past); err != nil {
		t.Fatal(err)
	}

	total, err := runMailJob(ctx, pool, getenv, time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatalf("first run: %v", err)
	}
	if total < 2 {
		t.Fatalf("first run counted %d items, want at least the sent row and the expired hold", total)
	}

	var state string
	var attempts int
	if err := pool.QueryRow(ctx, `SELECT state, attempts FROM email_outbox WHERE id = $1`, outboxID).Scan(&state, &attempts); err != nil {
		t.Fatal(err)
	}
	if state != "sent" || attempts != 1 {
		t.Fatalf("outbox row: state %s attempts %d", state, attempts)
	}
	var holdState string
	var holdUntil *string
	if err := pool.QueryRow(ctx, `SELECT state, provisional_until FROM reservation_claim WHERE reservation_id = 1`).Scan(&holdState, &holdUntil); err != nil {
		t.Fatal(err)
	}
	if holdState != "unclaimed" || holdUntil != nil {
		t.Fatalf("hold: state %s until %v", holdState, holdUntil)
	}

	// A second run must not send the row again.
	if _, err := runMailJob(ctx, pool, getenv, time.Date(2026, 11, 15, 10, 5, 0, 0, time.UTC)); err != nil {
		t.Fatalf("second run: %v", err)
	}
	var logged int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log WHERE outbox_id = $1`, outboxID).Scan(&logged); err != nil {
		t.Fatal(err)
	}
	if logged != 1 {
		t.Fatalf("console log rows for the outbox row: %d, want 1", logged)
	}
}

// mailJobTestPool creates a temporary database, applies App/migrations_pg in
// order and drops the database at the end.
func mailJobTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_mailjob_run_%d", time.Now().UnixNano())
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
	// Seed rows without parent apartments, users and reservations.
	cfg.AfterConnect = func(ctx context.Context, c *pgx.Conn) error {
		_, err := c.Exec(ctx, "SET session_replication_role = replica")
		return err
	}
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	mailJobMigrate(t, pool)
	return pool
}

func mailJobMigrate(t *testing.T, pool *pgxpool.Pool) {
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
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
}
