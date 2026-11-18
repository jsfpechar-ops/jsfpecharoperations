package stays

import (
	"context"
	"fmt"
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

func fixedToday() time.Time {
	return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
}

func TestParseParamsRangeRules(t *testing.T) {
	today := fixedToday()
	cases := []struct {
		name             string
		q                url.Values
		wantRange        string
		wantFrom, wantTo string
	}{
		{"default upcoming", url.Values{}, "upcoming", "2026-06-15", ""},
		{"upcoming explicit", url.Values{"range": {"upcoming"}}, "upcoming", "2026-06-15", ""},
		{"past", url.Values{"range": {"past"}}, "past", "", "2026-06-14"},
		{"current", url.Values{"range": {"current"}}, "current", "2026-06-15", "2026-06-15"},
		{"all clears dates", url.Values{"range": {"all"}}, "all", "", ""},
		{"archive clears dates", url.Values{"range": {"archive"}}, "archive", "", ""},
		{"custom keeps from", url.Values{"range": {"custom"}, "from": {"2026-07-01"}}, "custom", "2026-07-01", ""},
		{"invalid status", url.Values{"status": {"bogus"}}, "upcoming", "2026-06-15", ""},
		{"archive scope", url.Values{"archive_scope": {"1"}}, "upcoming", "2026-06-15", ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			p := ParseParams(tc.q, today)
			if p.DateRange != tc.wantRange || p.DateFrom != tc.wantFrom || p.DateTo != tc.wantTo {
				t.Fatalf("range/from/to = %q/%q/%q, want %q/%q/%q", p.DateRange, p.DateFrom, p.DateTo, tc.wantRange, tc.wantFrom, tc.wantTo)
			}
		})
	}
}

func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_stays_" + fmt.Sprintf("%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			return
		}
		defer c.Close(context.Background())
		_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	migratePool(t, pool)
	return pool
}

func migratePool(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
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
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
}

func TestListPaginationAndOrder(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	stamp := now
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('stays-host', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Stay Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Flat','tok','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	dates := []struct{ from, to string }{
		{"2026-06-10", "2026-06-12"},
		{"2026-06-13", "2026-06-14"},
		{"2026-06-15", "2026-06-17"},
		{"2026-06-18", "2026-06-20"},
		{"2026-06-21", "2026-06-23"},
		{"2026-06-24", "2026-06-26"},
	}
	var ids []int64
	for i, d := range dates {
		var id int64
		err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
			VALUES ($1,$2,$3,$4,'active','manual',$5,$5) RETURNING id`,
			aptID, fmt.Sprintf("uid-%d", i), d.from, d.to, stamp).Scan(&id)
		if err != nil {
			t.Fatal(err)
		}
		ids = append(ids, id)
	}
	p := ParseParams(url.Values{"range": {"all"}}, now)
	v, err := List(ctx, pool, func(string) string { return "" }, ownerID, p, now)
	if err != nil {
		t.Fatal(err)
	}
	if len(v.Rows) != 5 || v.Total != 6 || v.Page != 1 || v.PageCount != 2 {
		t.Fatalf("page1: rows=%d total=%d page=%d pageCount=%d", len(v.Rows), v.Total, v.Page, v.PageCount)
	}
	today := "2026-06-15"
	type row struct {
		id       int64
		from, to string
		rank     int
	}
	rows := make([]row, len(ids))
	for i := range ids {
		rows[i] = row{id: ids[i], from: dates[i].from, to: dates[i].to, rank: groupRank(dates[i].from, dates[i].to, today)}
	}
	sort.SliceStable(rows, func(i, j int) bool {
		if rows[i].rank != rows[j].rank {
			return rows[i].rank < rows[j].rank
		}
		switch rows[i].rank {
		case 0:
			if rows[i].to != rows[j].to {
				return rows[i].to < rows[j].to
			}
		case 1:
			if rows[i].from != rows[j].from {
				return rows[i].from < rows[j].from
			}
		case 2:
			if rows[i].to != rows[j].to {
				return rows[i].to > rows[j].to
			}
		}
		if rows[i].from != rows[j].from {
			return rows[i].from < rows[j].from
		}
		return rows[i].id < rows[j].id
	})
	wantOrder := make([]int64, len(rows))
	for i := range rows {
		wantOrder[i] = rows[i].id
	}
	for i := range v.Rows {
		if v.Rows[i].Reservation.ID != wantOrder[i] {
			t.Fatalf("row %d id=%d want=%d", i, v.Rows[i].Reservation.ID, wantOrder[i])
		}
	}
	p.Page = 2
	p.Raw = url.Values{"range": {"all"}, "page": {"2"}}
	v2, err := List(ctx, pool, func(string) string { return "" }, ownerID, p, now)
	if err != nil {
		t.Fatal(err)
	}
	if len(v2.Rows) != 1 {
		t.Fatalf("page2 rows=%d", len(v2.Rows))
	}
}

func groupRank(from, to, today string) int {
	if from <= today && to >= today {
		return 0
	}
	if from > today {
		return 1
	}
	return 2
}
