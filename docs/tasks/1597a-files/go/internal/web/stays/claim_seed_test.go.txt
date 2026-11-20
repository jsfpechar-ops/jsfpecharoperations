package stays

import (
	"context"
	"encoding/json"
	"os"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type demoClaimGolden struct {
	Now   string `json:"now"`
	Cases []struct {
		Name   string `json:"name"`
		State  string `json:"state"`
		Email  string `json:"email"`
		Locked bool   `json:"locked"`
		Decl   *int64 `json:"declared_guests"`
		Kind   string `json:"outbox_kind"`
	} `json:"cases"`
}

func loadDemoClaimGolden(t *testing.T) demoClaimGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/demo_claim_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g demoClaimGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestDemoClaimGoldenFile(t *testing.T) {
	g := loadDemoClaimGolden(t)
	if len(g.Cases) < 3 {
		t.Fatalf("cases=%d", len(g.Cases))
	}
}

func TestClaimSeedParity(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 14, 0, 0, 0, time.UTC)
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('demo-claim-host','x','host',1,1,$1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, internal_name, active, permalink_token, created_at)
		VALUES ($1,'Demo',1,'tokdemo',$2) RETURNING id`, ownerID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1,'d1','2026-06-20','2026-06-22','active','demo',$2,$2) RETURNING id`, aptID, stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	getenv := func(k string) string {
		if k == "PUBLIC_BASE_URL" {
			return "https://ubyhost.example"
		}
		return os.Getenv(k)
	}
	d := ClaimSeedDeps{Pool: pool, Getenv: getenv, Now: func() time.Time { return now }}
	res := SeedReservation{ID: resID, ApartmentID: aptID, Status: "active"}
	apt := SeedApartment{ID: aptID, OwnerUserID: ownerID, Name: "Demo", PermalinkToken: "tokdemo"}
	if _, err := EnsureClaimRow(ctx, pool, resID, now); err != nil {
		t.Fatal(err)
	}
	ok, code, secret, err := StartClaim(ctx, d, res, apt, "guest@example.test", 2, "en", false)
	if err != nil || !ok || code != "" || secret == "" {
		t.Fatalf("start: ok=%v code=%q secret=%q err=%v", ok, code, secret, err)
	}
	row, _ := EnsureClaimRow(ctx, pool, resID, now)
	if row.State != claimStateProvisional {
		t.Fatalf("state=%s", row.State)
	}
	if !ConfirmClaimOK(ctx, d, res, secret, t, pool) {
		t.Fatal("confirm failed")
	}
	row, _ = EnsureClaimRow(ctx, pool, resID, now)
	if row.State != claimStateClaimed {
		t.Fatalf("after confirm state=%s", row.State)
	}
	if err := LockGuestAccess(ctx, pool, resID, now); err != nil {
		t.Fatal(err)
	}
	row, _ = EnsureClaimRow(ctx, pool, resID, now)
	if !row.GuestAccessLocked {
		t.Fatal("not locked")
	}
}

func ConfirmClaimOK(ctx context.Context, d ClaimSeedDeps, res SeedReservation, secret string, t *testing.T, pool *pgxpool.Pool) bool {
	t.Helper()
	ok, err := ConfirmClaim(ctx, d, res, secret)
	if err != nil || !ok {
		t.Fatalf("confirm: ok=%v err=%v", ok, err)
	}
	return true
}
