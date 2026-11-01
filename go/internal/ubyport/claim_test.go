package ubyport

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

// claimTestPool is a copy of payments.testPool: a fresh database with the
// PostgreSQL migrations applied. It skips without UBYHOST_TEST_DATABASE_URL.
func claimTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_ubyport_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		_ = admin.Close(ctx)
		t.Fatal(err)
	}
	_ = admin.Close(ctx)
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
	applyClaimMigrations(t, pool)
	return pool
}

func applyClaimMigrations(t *testing.T, pool *pgxpool.Pool) {
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

// seedGuest inserts one pending guest with the columns that are NOT NULL
// without a default; everything else takes its default.
func seedGuest(t *testing.T, pool *pgxpool.Pool) int64 {
	t.Helper()
	ctx := context.Background()
	const ts = "2026-11-01T00:00:00+00:00"
	var apt, res, guest int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO apartment (internal_name, created_at) VALUES ($1, $2) RETURNING id`,
		"Test flat", ts).Scan(&apt); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $5) RETURNING id`,
		apt, "uid-"+ts, "2026-12-01", "2026-12-03", ts).Scan(&res); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, created_at, updated_at) VALUES ($1, $2, $2) RETURNING id`,
		res, ts).Scan(&guest); err != nil {
		t.Fatal(err)
	}
	return guest
}

func claimCount(t *testing.T, pool *pgxpool.Pool, id int64) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(),
		`SELECT count(*) FROM submission_claim WHERE guest_id = $1`, id).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestClaimOnlyOnce(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending"}}

	tok, got, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || tok == "" {
		t.Fatalf("first claim: got %d pairs, token %q", len(got), tok)
	}
	_, again, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	if len(again) != 0 {
		t.Fatalf("second claim of a leased guest returned %d pairs", len(again))
	}
	if err := ReleaseSendableClaim(ctx, pool, tok); err != nil {
		t.Fatal(err)
	}
}

func TestClaimReplacesStaleLease(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	if _, err := pool.Exec(ctx,
		`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'old', $2)`,
		id, nowSeconds()-400); err != nil {
		t.Fatal(err)
	}
	_, got, err := ClaimSendable(ctx, pool, []ClaimPair{{GuestID: id, SubmitState: "pending"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("stale lease was not replaced: got %d pairs", len(got))
	}
}

func TestClaimSkipsRowsThatMovedOn(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	const ts = "2026-11-02T00:00:00+00:00"

	changed := seedGuest(t, pool)
	archived := seedGuest(t, pool)
	filed := seedGuest(t, pool)
	if _, err := pool.Exec(ctx, `UPDATE guest SET archived_at = $2 WHERE id = $1`, archived, ts); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET manual_filed_at = $2 WHERE id = $1`, filed, ts); err != nil {
		t.Fatal(err)
	}
	pairs := []ClaimPair{
		{GuestID: changed, SubmitState: "sent"}, // row is pending, the list said sent
		{GuestID: archived, SubmitState: "pending"},
		{GuestID: filed, SubmitState: "pending"},
		{GuestID: 9999999, SubmitState: "pending"}, // row is gone
	}
	_, got, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 0 {
		t.Fatalf("claimed %d pairs that should have been skipped", len(got))
	}
	for _, id := range []int64{changed, archived, filed} {
		if n := claimCount(t, pool, id); n != 0 {
			t.Fatalf("guest %d holds %d claims after being skipped", id, n)
		}
	}
}

func TestReleaseFreesGuest(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending"}}
	tok, _, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	if err := ReleaseSendableClaim(ctx, pool, tok); err != nil {
		t.Fatal(err)
	}
	_, got, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("guest was not freed by release: got %d pairs", len(got))
	}
}
