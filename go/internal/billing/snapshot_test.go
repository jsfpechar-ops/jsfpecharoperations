package billing

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

func TestWriteMonthSnapshotMatchesFixturePrices(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	stamp := "2026-11-01T03:30:00+00:00"
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at) VALUES
		(1, 'founder', 'x', '2026-01-01T00:00:00+00:00'), (2, 'maxer', 'x', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	// Founder yearly: 3 x 890 = 2670, monthly 2670/12 = 222.5 -> 222 (half to even).
	// Max monthly: list 2220, 15 % off -> 1887, plus carry 100 -> net 1987.
	if _, err := pool.Exec(ctx, `INSERT INTO billing_account (owner_user_id, status, plan, billing_interval,
		apartments_billed, addon_ttlock, addon_whitelabel, founder, carry_czk, discount_percent, updated_at) VALUES
		(1, 'active', 'standard', 'year', 3, 0, 0, 1, 0, 0, '2026-01-01T00:00:00+00:00'),
		(2, 'active', 'max', 'month', 12, 0, 0, 0, 100, 15, '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	for run := 0; run < 2; run++ {
		n, err := WriteMonthSnapshot(ctx, pool, "2026-11", stamp)
		if err != nil || n != 2 {
			t.Fatalf("run %d: n=%d err=%v", run, n, err)
		}
	}
	want := map[int64][3]int{1: {2670, 2670, 222}, 2: {2220, 1987, 1987}}
	rows, err := pool.Query(ctx, "SELECT owner_user_id, list_czk, net_czk, monthly_czk FROM billing_month_snapshot WHERE month = '2026-11'")
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	seen := 0
	for rows.Next() {
		var owner int64
		var list, net, monthly int
		if err := rows.Scan(&owner, &list, &net, &monthly); err != nil {
			t.Fatal(err)
		}
		seen++
		if got := [3]int{list, net, monthly}; got != want[owner] {
			t.Errorf("owner %d: got %v want %v", owner, got, want[owner])
		}
	}
	if seen != 2 {
		t.Fatalf("snapshot rows: %d", seen)
	}
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
	name := fmt.Sprintf("ubyhost_go_billing_%d", time.Now().UnixNano())
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
