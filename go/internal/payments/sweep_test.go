package payments

import (
	"context"
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

func TestSweepExpiresAndPrunes(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	today := time.Date(2026, 11, 1, 3, 30, 0, 0, time.UTC)
	stamp := "2026-11-01T03:30:00+00:00"
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at) VALUES
		(1, 'host', 'x', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO payment_request (id, owner_user_id, reason, amount_czk, rail,
		status, expires_at, created_at, updated_at) VALUES
		(1, 1, 'custom', 100, 'card', 'draft', '2026-10-30', '2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00'),
		(2, 1, 'custom', 100, 'card', 'sent', '2026-10-31', '2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00'),
		(3, 1, 'custom', 100, 'card', 'awaiting_payment', '2026-10-31', '2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00'),
		(4, 1, 'custom', 100, 'card', 'sent', '2026-11-01', '2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00'),
		(5, 1, 'custom', 100, 'card', 'paid', '2026-10-30', '2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO stripe_webhook_event (id, event_id, event_type, mode, created_at) VALUES
		(1, 'evt_old', 'invoice.paid', 'test', '2026-10-01T10:00:00+00:00'),
		(2, 'evt_new', 'invoice.paid', 'test', '2026-10-03T10:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}

	expired, deleted, err := Sweep(ctx, pool, today, stamp)
	if err != nil || expired != 2 || deleted != 1 {
		t.Fatalf("first run: expired=%d deleted=%d err=%v", expired, deleted, err)
	}
	expired, deleted, err = Sweep(ctx, pool, today, stamp)
	if err != nil || expired != 0 || deleted != 0 {
		t.Fatalf("second run: expired=%d deleted=%d err=%v", expired, deleted, err)
	}

	statuses := map[int64]string{}
	rows, err := pool.Query(ctx, "SELECT id, status FROM payment_request")
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int64
		var status string
		if err := rows.Scan(&id, &status); err != nil {
			t.Fatal(err)
		}
		statuses[id] = status
	}
	rows.Close()
	want := map[int64]string{1: "draft", 2: "expired", 3: "expired", 4: "sent", 5: "paid"}
	for id, s := range want {
		if statuses[id] != s {
			t.Errorf("request %d: got %q want %q", id, statuses[id], s)
		}
	}

	details := auditDetails(t, pool, "payment_request_status")
	if strings.Join(details, "|") != "id=2 sent->expired|id=3 awaiting_payment->expired" {
		t.Errorf("request audit: %v", details)
	}
	sweep := auditDetails(t, pool, "stripe_webhook_sweep")
	if strings.Join(sweep, "|") != "deleted=1" {
		t.Errorf("webhook audit: %v", sweep)
	}
	var left int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM stripe_webhook_event").Scan(&left); err != nil || left != 1 {
		t.Fatalf("webhook rows left: %d err=%v", left, err)
	}
}

func auditDetails(t *testing.T, pool *pgxpool.Pool, action string) []string {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		"SELECT detail FROM audit WHERE action = $1 AND actor = 'host' ORDER BY id", action)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var d string
		if err := rows.Scan(&d); err != nil {
			t.Fatal(err)
		}
		out = append(out, d)
	}
	return out
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_payments_%d", time.Now().UnixNano())
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
	applyMigrations(t, pool)
	return pool
}

func applyMigrations(t *testing.T, pool *pgxpool.Pool) {
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
