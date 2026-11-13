package privacy

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
)

// golden is testdata/privacy_requests_golden.json, written by
// App/scripts/privacy_requests_golden.py from the real Python routes.
type golden struct {
	Now  string `json:"now"`
	Seed []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Steps []struct {
		Name      string                      `json:"name"`
		Account   int64                       `json:"account"`
		Workspace int64                       `json:"workspace"`
		Lang      string                      `json:"lang"`
		Path      string                      `json:"path"`
		Body      string                      `json:"body"`
		Status    int                         `json:"status"`
		Location  string                      `json:"location"`
		Response  string                      `json:"response"`
		State     map[string][]map[string]any `json:"state"`
	} `json:"steps"`
	OneMonthLater [][2]string        `json:"one_month_later"`
	ListForOwner  map[string][]int64 `json:"list_for_owner"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/privacy_requests_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestOneMonthLaterMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.OneMonthLater) < 20 {
		t.Fatalf("only %d one_month_later cases", len(g.OneMonthLater))
	}
	for _, c := range g.OneMonthLater {
		got, err := OneMonthLater(c[0])
		if err != nil {
			got = "error"
		}
		if got != c[1] {
			t.Errorf("OneMonthLater(%q) = %q, Python %q", c[0], got, c[1])
		}
	}
}

func TestStamp(t *testing.T) {
	at := time.Date(2026, 11, 13, 10, 30, 0, 999, time.FixedZone("CET", 3600))
	if got := Stamp(at); got != "2026-11-13T09:30:00+00:00" {
		t.Errorf("Stamp = %q", got)
	}
}

func TestListForOwnerDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, created_at) VALUES
			(1, 'a@example.test', 'x', 'now'), (2, 'b@example.test', 'x', 'now')`,
		`INSERT INTO data_subject_request (id, owner_user_id, received_at, due_at, channel,
			request_type, subject_kind, status, outcome_note, guest_id, created_at, updated_at) VALUES
			(1, 1, 'r', '2026-03-01', 'email', 'access', 'guest', 'fulfilled', 'done', NULL, 'c', 'u'),
			(2, 1, 'r', '2026-05-01', 'email', 'access', 'guest', 'open', NULL, NULL, 'c', 'u'),
			(3, 1, 'r', '2026-04-01', 'post', 'erasure', 'guest', 'extended', NULL, NULL, 'c', 'u'),
			(4, 2, 'r', '2026-01-01', 'email', 'access', 'guest', 'open', NULL, NULL, 'c', 'u'),
			(5, NULL, 'r', '2026-01-01', 'email', 'access', 'other', 'open', NULL, NULL, 'c', 'u'),
			(6, 1, 'r', '2026-04-01', 'email', 'access', 'guest', 'open', NULL, NULL, 'c', 'u')`,
	}
	for _, q := range stmts {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	ids := func(owner *int64) []int64 {
		rows, err := ListForOwner(ctx, pool, owner)
		if err != nil {
			t.Fatal(err)
		}
		var out []int64
		for _, r := range rows {
			out = append(out, r.ID)
		}
		return out
	}
	one, two := int64(1), int64(2)
	if got := fmt.Sprint(ids(&one)); got != "[3 6 2 1]" {
		t.Errorf("owner 1: %s", got)
	}
	if got := fmt.Sprint(ids(&two)); got != "[4]" {
		t.Errorf("owner 2: %s", got)
	}
	if got := fmt.Sprint(ids(nil)); got != "[5]" {
		t.Errorf("no owner: %s", got)
	}
	rows, err := ListForOwner(ctx, pool, &one)
	if err != nil {
		t.Fatal(err)
	}
	last := rows[len(rows)-1]
	if last.ID != 1 || last.OutcomeNote != "done" || last.GuestID != 0 || last.ClosedAt != "" || last.Open() {
		t.Errorf("row 1 read as %+v", last)
	}
	if !rows[0].Open() || rows[0].Status != "extended" || rows[0].OwnerUserID != 1 {
		t.Errorf("row 3 read as %+v", rows[0])
	}
	if _, found, err := Get(ctx, pool, 999); err != nil || found {
		t.Errorf("Get(999): found %v, err %v", found, err)
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
	name := fmt.Sprintf("ubyhost_go_privacy_%d", time.Now().UnixNano())
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
