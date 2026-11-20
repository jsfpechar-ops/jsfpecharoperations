package ttlock

import (
	"context"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// testPool is the jobs/queue_test.go pattern: a fresh database per test, created on the
// server named by UBYHOST_TEST_DATABASE_URL, migrated from App/migrations_pg, dropped after.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_ttlock_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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

func seedUsage(t *testing.T, pool *pgxpool.Pool, month, provider string, calls int64) {
	t.Helper()
	if _, err := pool.Exec(context.Background(),
		"INSERT INTO lock_api_usage (month, provider, calls) VALUES ($1, $2, $3) "+
			"ON CONFLICT (month, provider) DO UPDATE SET calls = EXCLUDED.calls",
		month, provider, calls); err != nil {
		t.Fatal(err)
	}
}

func mustAllow(t *testing.T, b *PGBudget, priority string, want bool) {
	t.Helper()
	got, err := b.Allows(context.Background(), priority)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("Allows(%s) = %v, want %v", priority, got, want)
	}
}

func TestMonthKeyIsUTC(t *testing.T) {
	if got := MonthKey(time.Date(2026, 11, 30, 23, 30, 0, 0, time.UTC)); got != "2026-11" {
		t.Fatalf("got %s", got)
	}
	// 00:30 on 1 December in UTC+2 is still 30 November in UTC.
	if got := MonthKey(time.Date(2026, 12, 1, 0, 30, 0, 0, time.FixedZone("plus2", 2*3600))); got != "2026-11" {
		t.Fatalf("zone offset leaked into the month: %s", got)
	}
}

func TestPGBudgetGuardsByPriorityAndMonth(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 11, 20, 10, 0, 0, 0, time.UTC)
	clock := func() time.Time { return now }
	b := NewPGBudget(pool, 100, clock)

	mustAllow(t, b, PriorityLow, true)
	mustAllow(t, b, PriorityNormal, true)
	mustAllow(t, b, PriorityCritical, true)

	seedUsage(t, pool, "2026-11", budgetProvider, 80)
	mustAllow(t, b, PriorityLow, false)
	mustAllow(t, b, PriorityNormal, true)
	mustAllow(t, b, PriorityCritical, true)

	seedUsage(t, pool, "2026-11", budgetProvider, 95)
	mustAllow(t, b, PriorityLow, false)
	mustAllow(t, b, PriorityNormal, false)
	mustAllow(t, b, PriorityCritical, true)

	if err := b.Count(ctx); err != nil {
		t.Fatal(err)
	}
	if calls, err := b.CallsThisMonth(ctx); err != nil || calls != 96 {
		t.Fatalf("after count: %d %v", calls, err)
	}

	// Other providers and other months do not count against TTLock's budget.
	seedUsage(t, pool, "2026-11", "other-provider", 1000)
	seedUsage(t, pool, "2026-10", budgetProvider, 1000)
	if calls, _ := b.CallsThisMonth(ctx); calls != 96 {
		t.Fatalf("other rows leaked in: %d", calls)
	}

	// A new UTC month starts at zero.
	now = time.Date(2026, 12, 1, 0, 0, 0, 0, time.UTC)
	if calls, _ := b.CallsThisMonth(ctx); calls != 0 {
		t.Fatalf("new month: %d", calls)
	}
	mustAllow(t, b, PriorityLow, true)
	if err := b.Count(ctx); err != nil {
		t.Fatal(err)
	}
	if calls, _ := b.CallsThisMonth(ctx); calls != 1 {
		t.Fatalf("new month first count: %d", calls)
	}

	// A limit of zero or less turns the guard off.
	off := NewPGBudget(pool, 0, func() time.Time { return time.Date(2026, 11, 20, 0, 0, 0, 0, time.UTC) })
	mustAllow(t, off, PriorityLow, true)
}

func TestClientCountsEveryAttemptAndStopsAtBudget(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	b := NewPGBudget(pool, 10, func() time.Time { return fixedNow })
	f := newFakeTTLock(t, func(string, url.Values) string { return respond(map[string]any{"errcode": 0}) })
	c := buildClient(f, newMemStore(), b, true)

	for i := 0; i < 9; i++ {
		if _, err := c.post(ctx, "/v3/key/list", nil, PriorityCritical); err != nil {
			t.Fatal(err)
		}
	}
	// 9 of 10 used: a normal call still passes and is the tenth.
	if _, err := c.post(ctx, "/v3/key/list", nil, PriorityNormal); err != nil {
		t.Fatalf("tenth call: %v", err)
	}
	// 10 of 10 used: a normal call is refused before anything is sent.
	before := f.total()
	if _, err := c.post(ctx, "/v3/key/list", nil, PriorityNormal); !IsKind(err, KindBudget) {
		t.Fatalf("eleventh call: %v", err)
	}
	if f.total() != before {
		t.Fatal("a refused call must not reach TTLock")
	}
	if calls, _ := b.CallsThisMonth(ctx); calls != 10 {
		t.Fatalf("counted %d calls, want 10", calls)
	}
}
