package mailjob

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

var holdTestNow = time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC)

func holdTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_mailjob_%d", time.Now().UnixNano())
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
	// Seed rows without building their parent apartments, users and reservations.
	cfg.AfterConnect = func(ctx context.Context, c *pgx.Conn) error {
		_, err := c.Exec(ctx, "SET session_replication_role = replica")
		return err
	}
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	holdTestMigrate(t, pool)
	return pool
}

// holdTestMigrate applies App/migrations_pg in order, as jobs/queue_test.go does.
func holdTestMigrate(t *testing.T, pool *pgxpool.Pool) {
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

func TestParseHoldDeadline(t *testing.T) {
	cases := map[string]time.Time{
		"2026-11-15T10:30:00+00:00": time.Date(2026, 11, 15, 10, 30, 0, 0, time.UTC),
		"2026-11-15T10:30:00Z":      time.Date(2026, 11, 15, 10, 30, 0, 0, time.UTC),
		// Naive values are Prague local time: CET (UTC+1) in November.
		"2026-11-15T10:30:00": time.Date(2026, 11, 15, 9, 30, 0, 0, time.UTC),
	}
	for in, want := range cases {
		got, err := parseHoldDeadline(in)
		if err != nil || !got.Equal(want) {
			t.Errorf("parseHoldDeadline(%q) = %v, %v; want %v", in, got, err, want)
		}
	}
	if _, err := parseHoldDeadline("not a time"); err == nil {
		t.Error("expected error for garbage input")
	}
}

func TestExpireHoldsFlipsOnlyDueProvisional(t *testing.T) {
	pool := holdTestPool(t)
	ctx := context.Background()
	stamp := "2026-11-01T00:00:00+00:00"
	seed := []struct {
		id    int64
		state string
		hash  *string
		until string
	}{
		{1, "provisional", holdPtr("hash-due"), "2026-11-15T09:30:00+00:00"},
		{2, "provisional", holdPtr("hash-future"), "2026-11-15T10:30:00+00:00"},
		{3, "provisional", holdPtr("hash-boundary"), "2026-11-15T10:00:00Z"},
		{4, "claimed", holdPtr("hash-claimed"), "2026-11-15T09:00:00+00:00"},
		{5, "provisional", holdPtr("hash-naive"), "2026-11-15T10:30:00"},
	}
	for _, s := range seed {
		if _, err := pool.Exec(ctx,
			`INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version,
			 provisional_until, created_at, updated_at)
			 VALUES ($1, $2, $3, 1, $4, $5, $5)`,
			s.id, s.state, s.hash, s.until, stamp); err != nil {
			t.Fatal(err)
		}
	}

	n, err := ExpireHolds(ctx, pool, holdTestNow)
	if err != nil {
		t.Fatal(err)
	}
	if n != 3 {
		t.Fatalf("expired %d, want 3 (ids 1, 3, 5)", n)
	}

	type row struct {
		state, updated string
		hash, until    *string
	}
	get := func(id int64) row {
		var r row
		if err := pool.QueryRow(ctx,
			`SELECT state, token_hash, provisional_until, updated_at FROM reservation_claim
			 WHERE reservation_id = $1`, id).Scan(&r.state, &r.hash, &r.until, &r.updated); err != nil {
			t.Fatal(err)
		}
		return r
	}
	for _, id := range []int64{1, 3, 5} {
		r := get(id)
		if r.state != "unclaimed" || r.hash != nil || r.until != nil || r.updated != utcStamp(holdTestNow) {
			t.Errorf("reservation %d: got %+v, want unclaimed with cleared token and deadline", id, r)
		}
	}
	if r := get(2); r.state != "provisional" || r.hash == nil || *r.hash != "hash-future" || r.until == nil {
		t.Errorf("not-yet-due hold changed: %+v", r)
	}
	if r := get(4); r.state != "claimed" || r.hash == nil || *r.hash != "hash-claimed" {
		t.Errorf("claimed row changed: %+v", r)
	}

	if again, err := ExpireHolds(ctx, pool, holdTestNow); err != nil || again != 0 {
		t.Fatalf("second run: %d, %v; want 0, nil", again, err)
	}
}

func TestExpireRequestsExpiresAndFreesHold(t *testing.T) {
	pool := holdTestPool(t)
	ctx := context.Background()
	stamp := "2026-11-01T00:00:00+00:00"

	insertHold := func() int64 {
		var id int64
		if err := pool.QueryRow(ctx,
			`INSERT INTO booking_hold (apartment_id, date_from, date_to, expires_at, created_at)
			 VALUES (1, '2026-12-01', '2026-12-03', '2026-11-16T10:00:00+00:00', $1) RETURNING id`,
			stamp).Scan(&id); err != nil {
			t.Fatal(err)
		}
		return id
	}
	insertBooking := func(status, expires string, holdID *int64) int64 {
		var id int64
		if err := pool.QueryRow(ctx,
			`INSERT INTO site_booking (apartment_id, owner_user_id, hold_id, pay_method,
			 request_expires_at, status, date_from, date_to, guests, nights, nightly_czk,
			 total_czk, cancellation_policy, terms_version, created_at, updated_at)
			 VALUES (1, 1, $1, 'direct', $2, $3, '2026-12-01', '2026-12-03', 2, 2, 1000,
			 2000, 'flexible', 'test-v1', $4, $4) RETURNING id`,
			holdID, expires, status, stamp).Scan(&id); err != nil {
			t.Fatal(err)
		}
		return id
	}

	holdExpired := insertHold()
	reqExpired := insertBooking("requested", "2026-11-14T10:00:00Z", &holdExpired)
	holdFuture := insertHold()
	bookingFuture := insertBooking("requested", "2026-11-16T10:00:00Z", &holdFuture)
	bookingPaid := insertBooking("paid", "2026-11-14T10:00:00Z", nil)
	bookingNoHold := insertBooking("requested", "2026-11-15T09:00:00Z", nil)

	n, err := ExpireRequests(ctx, pool, holdTestNow)
	if err != nil {
		t.Fatal(err)
	}
	if n != 2 {
		t.Fatalf("expired %d bookings, want 2", n)
	}

	status := func(id int64) string {
		var s string
		if err := pool.QueryRow(ctx, `SELECT status FROM site_booking WHERE id = $1`, id).Scan(&s); err != nil {
			t.Fatal(err)
		}
		return s
	}
	holdCount := func(id int64) int {
		var c int
		if err := pool.QueryRow(ctx, `SELECT count(*) FROM booking_hold WHERE id = $1`, id).Scan(&c); err != nil {
			t.Fatal(err)
		}
		return c
	}

	if s := status(reqExpired); s != "expired" {
		t.Errorf("expired request has status %q", s)
	}
	if c := holdCount(holdExpired); c != 0 {
		t.Errorf("hold of expired request still present (%d rows)", c)
	}
	if s := status(bookingFuture); s != "requested" {
		t.Errorf("non-expired request changed to %q", s)
	}
	if c := holdCount(holdFuture); c != 1 {
		t.Errorf("hold of non-expired request removed")
	}
	if s := status(bookingPaid); s != "paid" {
		t.Errorf("paid booking changed to %q", s)
	}
	if s := status(bookingNoHold); s != "expired" {
		t.Errorf("expired request without hold has status %q", s)
	}
	if again, err := ExpireRequests(ctx, pool, holdTestNow); err != nil || again != 0 {
		t.Fatalf("second run: %d, %v; want 0, nil", again, err)
	}
}

func holdPtr(s string) *string { return &s }
