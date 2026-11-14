package scheduler

import (
	"context"
	"fmt"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL with the
// job table of App/migrations_pg/00003_job.sql and drops it at the end. It
// skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_scheduler_%d", time.Now().UnixNano())
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
	raw, err := os.ReadFile("../../../App/migrations_pg/00003_job.sql")
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
	if _, err := pool.Exec(ctx, up); err != nil {
		t.Fatal(err)
	}
	return pool
}

func openRows(t *testing.T, pool *pgxpool.Pool, kind string) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(),
		"SELECT count(*) FROM job WHERE kind = $1 AND done_at IS NULL AND dead_at IS NULL", kind).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// One open row per kind: a second enqueue, Go's or Python's, is a no-op until
// the row is done or dead; then the next enqueue adds a new row.
func TestEnqueueKeepsOneOpenRowPerKind(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if added, err := Enqueue(ctx, pool, "submit"); err != nil || !added {
		t.Fatalf("first enqueue %v %v", added, err)
	}
	if added, err := Enqueue(ctx, pool, "submit"); err != nil || added {
		t.Fatalf("second enqueue %v %v", added, err)
	}
	// The row Python's jobqueue.enqueue writes for the same kind collides too.
	tag, err := pool.Exec(ctx,
		"INSERT INTO job (kind, run_at, payload, created_at) VALUES ($1, $2, '{}', $2) "+
			"ON CONFLICT (kind) WHERE done_at IS NULL AND dead_at IS NULL DO NOTHING", "submit", "2026-01-01T00:00:00+00:00")
	if err != nil || tag.RowsAffected() != 0 {
		t.Fatalf("python-style insert %v %v", tag.RowsAffected(), err)
	}
	if added, err := Enqueue(ctx, pool, "push"); err != nil || !added {
		t.Fatalf("other kind %v %v", added, err)
	}
	var runAt, createdAt, payload string
	if err := pool.QueryRow(ctx, "SELECT run_at, created_at, payload FROM job WHERE kind = 'submit'").Scan(&runAt, &createdAt, &payload); err != nil {
		t.Fatal(err)
	}
	if runAt != createdAt || payload != "{}" || !strings.HasSuffix(runAt, "+00:00") || len(runAt) != len("2026-01-01T00:00:00+00:00") {
		t.Fatalf("row %q %q %q", runAt, createdAt, payload)
	}
	if _, err := pool.Exec(ctx, "UPDATE job SET done_at = run_at WHERE kind = 'submit'"); err != nil {
		t.Fatal(err)
	}
	if added, err := Enqueue(ctx, pool, "submit"); err != nil || !added {
		t.Fatalf("after done %v %v", added, err)
	}
	if n := openRows(t, pool, "submit"); n != 1 {
		t.Fatalf("open submit rows %d", n)
	}
}

// Both sides enqueueing the same kind at the same moment (the switch or the
// rollback) still leave exactly one open row.
func TestConcurrentEnqueueAddsOneRow(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	var wg sync.WaitGroup
	var mu sync.Mutex
	added := 0
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ok, err := Enqueue(ctx, pool, "deadlines")
			if err != nil {
				t.Error(err)
				return
			}
			if ok {
				mu.Lock()
				added++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	if added != 1 || openRows(t, pool, "deadlines") != 1 {
		t.Fatalf("added %d, open %d", added, openRows(t, pool, "deadlines"))
	}
}
