package stays

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"sort"
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
	// Minimal tables for the list query (not full goose migrate).
	ctx := context.Background()
	stmts := []string{
		`CREATE TABLE user_account (id BIGSERIAL PRIMARY KEY, username TEXT)`,
		`CREATE TABLE legal_entity (id BIGSERIAL PRIMARY KEY, owner_user_id BIGINT)`,
		`CREATE TABLE apartment (id BIGSERIAL PRIMARY KEY, owner_user_id BIGINT, legal_entity_id BIGINT,
			internal_name TEXT, permalink_token TEXT, automation_mode TEXT, submit_after_hours INT,
			active INT, archived_at TIMESTAMPTZ)`,
		`CREATE TABLE apartment_slug (id BIGSERIAL PRIMARY KEY, apartment_id BIGINT, slug TEXT, is_current INT)`,
		`CREATE TABLE reservation (id BIGSERIAL PRIMARY KEY, apartment_id BIGINT, uid TEXT,
			date_from TEXT, date_to TEXT, status TEXT, source TEXT, archived_at TIMESTAMPTZ,
			created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)`,
		`CREATE TABLE guest (id BIGSERIAL PRIMARY KEY, reservation_id BIGINT, submit_state TEXT,
			created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)`,
	}
	for _, s := range stmts {
		if _, err := pool.Exec(ctx, s); err != nil {
			t.Fatal(err)
		}
	}
}

func TestListPaginationAndOrder(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	stamp := now
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username) VALUES ('stays-host') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id) VALUES ($1) RETURNING id`, ownerID).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active)
		VALUES ($1,$2,'Flat','tok','manual',24,1) RETURNING id`, ownerID, entityID).Scan(&aptID); err != nil {
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
	wantOrder := append([]int64(nil), ids...)
	sort.SliceStable(wantOrder, func(i, j int) bool {
		gi, gj := groupRank(dates[i].from, dates[i].to, "2026-06-15"), groupRank(dates[j].from, dates[j].to, "2026-06-15")
		if gi != gj {
			return gi < gj
		}
		return dates[i].from < dates[j].from || (dates[i].from == dates[j].from && ids[i] < ids[j])
	})
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
