package jobs

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
)

func insertJob(t *testing.T, pool *pgxpool.Pool, kind string) {
	t.Helper()
	if _, err := pool.Exec(context.Background(),
		"INSERT INTO job (kind, run_at, payload, created_at) VALUES ($1, $2, '{}', $2)", kind, Now(0)); err != nil {
		t.Fatal(err)
	}
}

func openAlerts(t *testing.T, pool *pgxpool.Pool) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(),
		"SELECT count(*) FROM alert WHERE dedupe_key = 'job_failed:billing_snapshot' AND resolved_at IS NULL").Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestClaimHonoursKinds(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	insertJob(t, pool, "mail")
	insertJob(t, pool, "billing_snapshot")
	j, err := Claim(ctx, pool, []string{"billing_snapshot"})
	if err != nil || j == nil || j.Kind != "billing_snapshot" {
		t.Fatalf("claim: %+v %v", j, err)
	}
	if again, _ := Claim(ctx, pool, []string{"billing_snapshot"}); again != nil {
		t.Fatal("leased row claimed twice")
	}
	if other, _ := Claim(ctx, pool, []string{"mail"}); other == nil {
		t.Fatal("mail row should still be due")
	}
	if none, err := Claim(ctx, pool, nil); none != nil || err != nil {
		t.Fatal("empty kinds must claim nothing")
	}
}

func TestFailBacksOffThenDiesWithOneAlert(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	insertJob(t, pool, "billing_snapshot")
	for attempt := 1; attempt <= MaxAttempts; attempt++ {
		j, err := Claim(ctx, pool, []string{"billing_snapshot"})
		if err != nil || j == nil || j.Attempts != attempt {
			t.Fatalf("attempt %d: %+v %v", attempt, j, err)
		}
		dead, err := Fail(ctx, pool, j, errors.New("boom"), 24*60)
		if err != nil {
			t.Fatal(err)
		}
		if attempt < MaxAttempts {
			if dead {
				t.Fatalf("dead too early at attempt %d", attempt)
			}
			var runAt string
			if err := pool.QueryRow(ctx, "SELECT run_at FROM job WHERE id = $1", j.ID).Scan(&runAt); err != nil {
				t.Fatal(err)
			}
			if attempt == 1 && (runAt < Now(50*time.Second) || runAt > Now(70*time.Second)) {
				t.Fatalf("first retry not about one minute ahead: %s", runAt)
			}
			if again, _ := Claim(ctx, pool, []string{"billing_snapshot"}); again != nil {
				t.Fatal("retry was due at once")
			}
			if _, err := pool.Exec(ctx, "UPDATE job SET run_at = '2000-01-01T00:00:00+00:00'"); err != nil {
				t.Fatal(err)
			}
		} else if !dead {
			t.Fatal("row not dead after MaxAttempts")
		}
	}
	if err := RaiseFailed(ctx, pool, "billing_snapshot"); err != nil {
		t.Fatal(err)
	}
	if err := RaiseFailed(ctx, pool, "billing_snapshot"); err != nil {
		t.Fatal(err)
	}
	if n := openAlerts(t, pool); n != 1 {
		t.Fatalf("open job_failed alerts: %d", n)
	}
}

func TestDrainRunsHandlerAndRecordsSuccess(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	insertJob(t, pool, "billing_snapshot")
	if err := RaiseFailed(ctx, pool, "billing_snapshot"); err != nil {
		t.Fatal(err)
	}
	handlers := map[string]Handler{"billing_snapshot": func(context.Context) (int, error) { return 2, nil }}
	if ran := drain(ctx, pool, []string{"billing_snapshot"}, handlers, map[string]int{"billing_snapshot": 1440}); ran != 1 {
		t.Fatalf("ran %d", ran)
	}
	if n := openAlerts(t, pool); n != 0 {
		t.Fatalf("alert not resolved: %d", n)
	}
	var value string
	if err := pool.QueryRow(ctx, "SELECT value FROM settings WHERE key = 'job_last_ok:billing_snapshot'").Scan(&value); err != nil || value == "" {
		t.Fatalf("job_last_ok missing: %v", err)
	}
	var done int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM job WHERE done_at IS NOT NULL").Scan(&done); err != nil || done != 1 {
		t.Fatalf("done rows %d %v", done, err)
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
	name := fmt.Sprintf("ubyhost_go_jobs_%d", time.Now().UnixNano())
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
