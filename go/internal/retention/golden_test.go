package retention

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// golden is testdata/golden.json, written by App/scripts/retention_golden.py
// from the real Python retention.run() on the same fixture.
type golden struct {
	Today     string            `json:"today"`
	Now       string            `json:"now"`
	Photos    []string          `json:"photos"`
	Queries   map[string]string `json:"queries"`
	Scenarios []struct {
		Name   string              `json:"name"`
		Owner  *int64              `json:"owner_user_id"`
		DryRun bool                `json:"dry_run"`
		Error  *string             `json:"error"`
		Counts [][2]any            `json:"counts"`
		Photos []string            `json:"photos"`
		State  map[string][]string `json:"state"`
	} `json:"scenarios"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// TestRunMatchesPythonGolden replays every scenario of golden.json: same
// fixture, same instant, same switches; counts, first failure, every touched
// table and the photo directory must match Python.
func TestRunMatchesPythonGolden(t *testing.T) {
	g := loadGolden(t)
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	now, err := time.Parse("2006-01-02T15:04:05.000000Z", g.Now)
	if err != nil {
		t.Fatal(err)
	}
	fixture, err := os.ReadFile("testdata/fixture.sql")
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Scenarios) != 2 {
		t.Fatalf("golden has %d scenarios, want 2", len(g.Scenarios))
	}
	for _, sc := range g.Scenarios {
		t.Run(sc.Name, func(t *testing.T) {
			pool := testPool(t)
			ctx := context.Background()
			if _, err := pool.Exec(ctx, string(fixture)); err != nil {
				t.Fatal(err)
			}
			dataDir := t.TempDir()
			photos := filepath.Join(dataDir, "passport_photos")
			if err := os.MkdirAll(photos, 0o700); err != nil {
				t.Fatal(err)
			}
			for _, p := range g.Photos {
				if err := os.WriteFile(filepath.Join(photos, p), []byte("x"), 0o600); err != nil {
					t.Fatal(err)
				}
			}
			cfg := Config{DryRun: sc.DryRun, AuditDays: 1095, AlertDays: 365, RateLimitHours: 24, NoticeDays: 30, DataDir: dataDir}
			sum, err := Run(ctx, pool, cfg, today, now, sc.Owner)
			if sc.Error != nil || err != nil || !sc.DryRun {
				t.Fatalf("Run: %v; golden error %v, dry run %v", err, sc.Error, sc.DryRun)
			}
			var want, got []string
			for _, c := range sc.Counts {
				want = append(want, fmt.Sprintf("%v=%v", c[0], c[1]))
			}
			for _, c := range sum.Counts {
				got = append(got, fmt.Sprintf("%s=%d", c.Name, c.Count))
			}
			if !reflect.DeepEqual(got, want) {
				t.Errorf("counts\n got %v\nwant %v", got, want)
			}
			names := make([]string, 0, len(g.Queries))
			for k := range g.Queries {
				names = append(names, k)
			}
			sort.Strings(names)
			for _, name := range names {
				rows, err := pool.Query(ctx, g.Queries[name])
				if err != nil {
					t.Fatalf("%s: %v", name, err)
				}
				gotRows, err := pgx.CollectRows(rows, pgx.RowTo[string])
				if err != nil {
					t.Fatalf("%s: %v", name, err)
				}
				wantRows := sc.State[name]
				if wantRows == nil {
					wantRows = []string{}
				}
				if gotRows == nil {
					gotRows = []string{}
				}
				if !reflect.DeepEqual(gotRows, wantRows) {
					t.Errorf("%s\n got %s\nwant %s", name, strings.Join(gotRows, "\n     "), strings.Join(wantRows, "\n     "))
				}
			}
			entries, err := os.ReadDir(photos)
			if err != nil {
				t.Fatal(err)
			}
			left := []string{}
			for _, e := range entries {
				left = append(left, e.Name())
			}
			sort.Strings(left)
			if !reflect.DeepEqual(left, sc.Photos) {
				t.Errorf("photos left %v, want %v", left, sc.Photos)
			}
		})
	}
}

// TestApplyIsRefusedUntil1211: with both apply switches on this build fails
// closed before any step runs and writes nothing.
func TestApplyIsRefusedUntil1211(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	fixture, err := os.ReadFile("testdata/fixture.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, string(fixture)); err != nil {
		t.Fatal(err)
	}
	cfg := Config{AuditDays: 1095, AlertDays: 365, RateLimitHours: 24, NoticeDays: 30, DataDir: t.TempDir()}
	now := time.Date(2026, 1, 20, 3, 0, 0, 0, time.UTC)
	if _, err := Run(ctx, pool, cfg, now, now, nil); !errors.Is(err, errApplyNotPorted) {
		t.Fatalf("Run error %v, want errApplyNotPorted", err)
	}
	var audits, guests int
	if err := pool.QueryRow(ctx, `SELECT (SELECT COUNT(*) FROM audit), (SELECT COUNT(*) FROM guest)`).Scan(&audits, &guests); err != nil {
		t.Fatal(err)
	}
	if audits != 8 || guests != 10 {
		t.Fatalf("audit rows %d, guests %d: want 8 and 10 (nothing written)", audits, guests)
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
	name := fmt.Sprintf("ubyhost_go_retention_%d", time.Now().UnixNano())
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
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}
