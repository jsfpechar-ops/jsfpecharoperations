package billingweb

import (
	"archive/zip"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// dispatch maps a golden scenario's fn to the Go call. Every entry must be used
// by the golden file, and every golden scenario must have an entry.
var dispatch = map[string]func(ctx context.Context, q DB, a map[string]string, day time.Time) (any, error){
	"invoices": func(ctx context.Context, q DB, a map[string]string, _ time.Time) (any, error) {
		return Invoices(ctx, q, a["month"])
	},
	"unpaid": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return Unpaid(ctx, q, d)
	},
	"accounts_by_status": func(ctx context.Context, q DB, _ map[string]string, _ time.Time) (any, error) {
		return AccountsByStatus(ctx, q)
	},
	"export_csv": func(ctx context.Context, q DB, a map[string]string, _ time.Time) (any, error) {
		b, err := ExportCSV(ctx, q, a["month"])
		return string(b), err
	},
	"unmatched": func(ctx context.Context, q DB, _ map[string]string, _ time.Time) (any, error) {
		return Unmatched(ctx, q)
	},
	"portfolio": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return GetPortfolio(ctx, q, d)
	},
	"revenue_totals": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return RevenueTotals(ctx, q, d)
	},
	"watchlists": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return Watchlists(ctx, q, d)
	},
	"operator_queue": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return OperatorQueue(ctx, q, d)
	},
	"aging": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return Aging(ctx, q, d)
	},
	"forecast": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return GetForecast(ctx, q, d)
	},
	"movement": func(ctx context.Context, q DB, a map[string]string, _ time.Time) (any, error) {
		return GetMovement(ctx, q, a["month"])
	},
	"funnel": func(ctx context.Context, q DB, _ map[string]string, _ time.Time) (any, error) {
		return GetFunnel(ctx, q)
	},
	"trend": func(ctx context.Context, q DB, _ map[string]string, _ time.Time) (any, error) {
		return Trend(ctx, q, 12)
	},
	"discount_overview": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		return DiscountOverview(ctx, q, d)
	},
	"export_all_files": func(ctx context.Context, q DB, _ map[string]string, d time.Time) (any, error) {
		blob, err := ExportAllZip(ctx, q, d)
		if err != nil {
			return nil, err
		}
		zr, err := zip.NewReader(strings.NewReader(string(blob)), int64(len(blob)))
		if err != nil {
			return nil, err
		}
		files := map[string]string{}
		for _, f := range zr.File {
			if strings.HasSuffix(strings.ToLower(f.Name), ".pdf") {
				return nil, fmt.Errorf("the bulk export holds a PDF: %s", f.Name)
			}
			rc, err := f.Open()
			if err != nil {
				return nil, err
			}
			b, err := io.ReadAll(rc)
			rc.Close()
			if err != nil {
				return nil, err
			}
			files[f.Name] = string(b)
		}
		return files, nil
	},
	"admin_page": func(ctx context.Context, q DB, a map[string]string, d time.Time) (any, error) {
		return AdminPageData(ctx, q, a["mesic"], a["q"], a["state"], d)
	},
}

// minScenarios is how many scenarios the golden file must hold; a shorter file
// (or a run that compares fewer) fails instead of passing quietly.
const minScenarios = 30

func TestAdminReadSideMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Scenarios) < minScenarios || len(g.Seed) < 5 {
		t.Fatalf("golden file has %d scenarios and %d seed tables", len(g.Scenarios), len(g.Seed))
	}
	pool := testPool(t)
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = v
				if n, ok := v.(interface{ Int64() (int64, error) }); ok {
					x, err := n.Int64()
					if err != nil {
						t.Fatalf("%s: %v", table.Table, err)
					}
					args[i] = x
				}
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s %v: %v", table.Table, row, err)
			}
		}
	}
	used := map[string]bool{}
	compared := 0
	for i, s := range g.Scenarios {
		call, ok := dispatch[s.Fn]
		if !ok {
			t.Fatalf("scenario %d: no Go call for %q", i, s.Fn)
		}
		used[s.Fn] = true
		got, err := call(ctx, pool, s.Args, mustDay(t, s.Today))
		if err != nil {
			t.Errorf("%s %v %s: %v", s.Fn, s.Args, s.Today, err)
			continue
		}
		compared++
		if ok, gb, wb := sameJSON(t, got, s.Result); !ok {
			t.Errorf("%s %v %s differs from Python\n got: %s\nwant: %s", s.Fn, s.Args, s.Today, clip(gb), clip(wb))
		}
	}
	for fn := range dispatch {
		if !used[fn] {
			t.Errorf("no golden scenario for %s", fn)
		}
	}
	if compared != len(g.Scenarios) {
		t.Fatalf("compared %d of %d scenarios", compared, len(g.Scenarios))
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
	name := fmt.Sprintf("ubyhost_go_billingweb_%d", time.Now().UnixNano())
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
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
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
