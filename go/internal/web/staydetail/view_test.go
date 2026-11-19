package staydetail

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

func stayDetailPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_staydetail_%d", time.Now().UnixNano())
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
	migrateStayDetail(t, pool)
	return pool
}

func migrateStayDetail(t *testing.T, pool *pgxpool.Pool) {
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

func insertOwnerStay(t *testing.T, pool *pgxpool.Pool, ownerID int64, archived bool) (aptID, resID int64) {
	t.Helper()
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, now).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Flat','tok','manual',24,1,$3) RETURNING id`, ownerID, entityID, now).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var arch any
	if archived {
		arch = now
	} else {
		arch = nil
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, archived_at, created_at, updated_at)
		VALUES ($1,'uid-detail','2026-06-10','2026-06-12','active','manual',$2,$3,$3) RETURNING id`, aptID, arch, now).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	return aptID, resID
}

func TestLoadStayOwnerScope(t *testing.T) {
	pool := stayDetailPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	var ownerA, ownerB int64
	for i, name := range []string{"host-a", "host-b"} {
		var id int64
		if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
			VALUES ($1,'x','host',1,1,$2) RETURNING id`, name, now).Scan(&id); err != nil {
			t.Fatal(err)
		}
		if i == 0 {
			ownerA = id
		} else {
			ownerB = id
		}
	}
	_, resID := insertOwnerStay(t, pool, ownerA, false)

	got, ok, err := LoadStay(ctx, pool, ownerA, resID)
	if err != nil || !ok || got.ID != resID {
		t.Fatalf("owner stay: ok=%v err=%v id=%d", ok, err, got.ID)
	}
	_, ok, err = LoadStay(ctx, pool, ownerB, resID)
	if err != nil || ok {
		t.Fatalf("other owner: ok=%v err=%v", ok, err)
	}

	_, archID := insertOwnerStay(t, pool, ownerA, true)
	got, ok, err = LoadStay(ctx, pool, ownerA, archID)
	if err != nil || !ok || got.ID != archID {
		t.Fatalf("archived: ok=%v err=%v", ok, err)
	}
}

func TestBuildSubmissionsUnion(t *testing.T) {
	pool := stayDetailPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('sub-host','x','host',1,1,$1) RETURNING id`, now).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	aptID, resID := insertOwnerStay(t, pool, ownerID, false)

	var otherApt int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, active, created_at)
		SELECT owner_user_id, legal_entity_id, 'Other', 'tok2', 1, $1 FROM apartment WHERE id = $2 RETURNING id`, now, aptID).Scan(&otherApt); err != nil {
		t.Fatal(err)
	}

	var sub1, sub2, subOther int64
	ts1 := now.Add(-2 * time.Hour)
	ts2 := now.Add(-1 * time.Hour)
	for _, pair := range []struct {
		ts  *time.Time
		apt int64
		out *int64
	}{
		{&ts1, aptID, &sub1},
		{&ts2, aptID, &sub2},
		{&now, otherApt, &subOther},
	} {
		if err := pool.QueryRow(ctx, `INSERT INTO submission (apartment_id, state, created_at) VALUES ($1,'sent',$2) RETURNING id`,
			pair.apt, *pair.ts).Scan(pair.out); err != nil {
			t.Fatal(err)
		}
	}

	var guestID int64
	if err := pool.QueryRow(ctx, `INSERT INTO guest (reservation_id, is_lead, submit_state, created_at, updated_at, submission_id, receipt_submission_id)
		VALUES ($1,1,'sent',$2,$2,$3,$4) RETURNING id`, resID, now, sub1, sub2).Scan(&guestID); err != nil {
		t.Fatal(err)
	}
	_ = guestID
	_, _ = pool.Exec(ctx, `INSERT INTO guest (reservation_id, is_lead, submit_state, created_at, updated_at, submission_id)
		VALUES ($1,0,'sent',$2,$2,$3)`, resID, now, subOther)

	d := Deps{Pool: pool, Getenv: func(string) string { return "" }}
	v, ok, err := Build(ctx, d, ownerID, resID, "", now)
	if err != nil || !ok {
		t.Fatalf("Build: ok=%v err=%v", ok, err)
	}
	if len(v.Submissions) != 2 {
		t.Fatalf("submissions count=%d", len(v.Submissions))
	}
	if v.Submissions[0].ID != sub2 || v.Submissions[1].ID != sub1 {
		t.Fatalf("order: %+v", v.Submissions)
	}
}

func TestEnsureClaimRowIdempotent(t *testing.T) {
	pool := stayDetailPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('claim-host','x','host',1,1,$1) RETURNING id`, now).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	_, resID := insertOwnerStay(t, pool, ownerID, false)

	c1, err := ensureClaimRow(ctx, pool, resID)
	if err != nil || c1.State != "unclaimed" {
		t.Fatalf("first: %+v err=%v", c1, err)
	}
	c2, err := ensureClaimRow(ctx, pool, resID)
	if err != nil || c2.State != "unclaimed" {
		t.Fatalf("second: %+v err=%v", c2, err)
	}
	var n int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1`, resID).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("claim rows=%d", n)
	}
}
