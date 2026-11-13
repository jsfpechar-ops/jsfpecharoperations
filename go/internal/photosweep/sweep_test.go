package photosweep

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

type goldenTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type goldenFile struct {
	Dir      string `json:"dir"`
	Name     string `json:"name"`
	MtimeAgo int64  `json:"mtime_ago"`
	Kind     string `json:"kind"`
}

type goldenSignup struct {
	ClickIDsCleared   int `json:"click_ids_cleared"`
	MetaEventsExpired int `json:"meta_events_expired"`
	UnverifiedDeleted int `json:"unverified_deleted"`
}

type goldenCounts struct {
	Photos       int          `json:"photos"`
	GuideOrphans int          `json:"guide_orphans"`
	Payloads     int          `json:"payloads"`
	Drafts       int          `json:"drafts"`
	Signup       goldenSignup `json:"signup"`
}

type golden struct {
	Now          string             `json:"now"`
	Today        string             `json:"today"`
	Seed         []goldenTable      `json:"seed"`
	Files        []goldenFile       `json:"files"`
	Snapshot     []goldenTable      `json:"snapshot"`
	AuditColumns []string           `json:"audit_columns"`
	Counts       goldenCounts       `json:"counts"`
	FilesLeft    []string           `json:"files_left"`
	After        map[string][][]any `json:"after"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/photo_sweep_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g golden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Seed) == 0 || len(g.Files) == 0 || len(g.Snapshot) == 0 {
		t.Fatal("golden file has no seed, files or snapshot")
	}
	return g
}

// dbPool creates a throwaway database with every App/migrations_pg file, as
// go/internal/calendar/handler_test.go does.
func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_photosweep_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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
	files, _ := filepath.Glob("../../../App/migrations_pg/*.sql")
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

// seedValue turns a decoded JSON value into a query argument.
func seedValue(t *testing.T, v any) any {
	t.Helper()
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed number %s: %v", n, err)
		}
		return i
	}
	return v
}

// seed loads the golden rows and files; it returns the data directory.
func seed(t *testing.T, pool *pgxpool.Pool, g golden, now time.Time) string {
	t.Helper()
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = "$" + strconv.Itoa(i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") + ") VALUES (" +
			strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(t, v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	dir := t.TempDir()
	for _, f := range g.Files {
		folder := filepath.Join(dir, f.Dir)
		if err := os.MkdirAll(folder, 0o755); err != nil {
			t.Fatal(err)
		}
		path := filepath.Join(folder, f.Name)
		if f.Kind == "dir" {
			if err := os.Mkdir(path, 0o755); err != nil {
				t.Fatal(err)
			}
			continue
		}
		if err := os.WriteFile(path, []byte("golden"), 0o600); err != nil {
			t.Fatal(err)
		}
		at := now.Add(-time.Duration(f.MtimeAgo) * time.Second)
		if err := os.Chtimes(path, at, at); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

// rowLines reads every row of a query as one JSON line.
func rowLines(t *testing.T, pool *pgxpool.Pool, sql string) []string {
	t.Helper()
	rows, err := pool.Query(context.Background(), sql)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		vals, err := rows.Values()
		if err != nil {
			t.Fatal(err)
		}
		b, _ := json.Marshal(vals)
		out = append(out, string(b))
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func goldenLines(rows [][]any) []string {
	out := make([]string, 0, len(rows))
	for _, r := range rows {
		b, _ := json.Marshal(r)
		out = append(out, string(b))
	}
	return out
}

func compareLines(t *testing.T, what string, got, want []string) {
	t.Helper()
	if strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Errorf("%s differs from Python\n got:\n%s\nwant:\n%s", what, strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
}

func goldenClock(t *testing.T, g golden) clock {
	t.Helper()
	now, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	return clock{now: now, today: today, pragueToday: deadlines.LocalNow(now).Format("2006-01-02")}
}

// TestRunMatchesPython seeds the golden rows and files, runs the sweep at the
// golden clock and compares every count, the files left, the rows in the
// snapshot and the audit table with what the Python job did.
func TestRunMatchesPython(t *testing.T) {
	g := loadGolden(t)
	c := goldenClock(t, g)
	pool := dbPool(t)
	dir := seed(t, pool, g, c.now)
	sum, err := run(context.Background(), pool, dir, c)
	if err != nil {
		t.Fatal(err)
	}
	want := Summary{Photos: g.Counts.Photos, GuideOrphans: g.Counts.GuideOrphans, Payloads: g.Counts.Payloads,
		Drafts: g.Counts.Drafts, Signup: SignupCounts{UnverifiedDeleted: g.Counts.Signup.UnverifiedDeleted,
			ClickIDsCleared: g.Counts.Signup.ClickIDsCleared, MetaEventsExpired: g.Counts.Signup.MetaEventsExpired}}
	if sum != want {
		t.Errorf("counts %+v, Python %+v", sum, want)
	}
	var left []string
	for _, f := range g.Files {
		if _, err := os.Lstat(filepath.Join(dir, f.Dir, f.Name)); err == nil {
			left = append(left, f.Dir+"/"+f.Name)
		}
	}
	sort.Strings(left)
	compareLines(t, "files left", left, g.FilesLeft)
	for _, spec := range g.Snapshot {
		got := rowLines(t, pool, "SELECT "+strings.Join(spec.Columns, ", ")+" FROM "+spec.Table+" ORDER BY id")
		compareLines(t, spec.Table, got, goldenLines(g.After[spec.Table]))
	}
	got := rowLines(t, pool, "SELECT "+strings.Join(g.AuditColumns, ", ")+" FROM audit")
	wantAudit := goldenLines(g.After["audit"])
	sort.Strings(got)
	sort.Strings(wantAudit)
	compareLines(t, "audit", got, wantAudit)
}

// TestRunFailsOnReadOnlyPhotos: the Go service mounts /data read-only today.
// The first photo that must go fails the job, and no later step runs.
func TestRunFailsOnReadOnlyPhotos(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	g := loadGolden(t)
	c := goldenClock(t, g)
	pool := dbPool(t)
	dir := seed(t, pool, g, c.now)
	photos := filepath.Join(dir, "passport_photos")
	if err := os.Chmod(photos, 0o555); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(photos, 0o755) })
	if _, err := run(context.Background(), pool, dir, c); err == nil {
		t.Fatal("run on a read-only photo directory returned nil")
	}
	var n int
	if err := pool.QueryRow(context.Background(), `SELECT count(*) FROM guest_form_draft`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 6 {
		t.Errorf("drafts left %d, want all 6: a later step ran after the failure", n)
	}
}

func TestRunNeedsDataDir(t *testing.T) {
	if _, err := Run(context.Background(), nil, "", time.Now()); err == nil {
		t.Fatal("Run with no data dir returned nil")
	}
}
