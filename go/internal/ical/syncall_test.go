package ical

import (
	"context"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// seedPausedOwner makes owner 1 with a paused billing account.
func seedPausedOwner(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	_, err := pool.Exec(ctx,
		`INSERT INTO user_account (id, username, password_hash, created_at) VALUES (1, 'owner', 'x', $1)`,
		ubyport.UTCNow())
	must(t, err)
	_, err = pool.Exec(ctx,
		`INSERT INTO billing_account (owner_user_id, status, updated_at) VALUES (1, 'paused', NOW())`)
	must(t, err)
}

// seedOwnedApartment makes an apartment whose owner is owner.
func seedOwnedApartment(t *testing.T, pool *pgxpool.Pool, owner int64) int64 {
	t.Helper()
	var id int64
	must(t, pool.QueryRow(context.Background(),
		`INSERT INTO apartment (internal_name, created_at, owner_user_id) VALUES ($1, $2, $3) RETURNING id`,
		"Owned flat", ubyport.UTCNow(), owner).Scan(&id))
	return id
}

func TestSyncAllPausedSkippedAndErrorsCounted(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedPausedOwner(t, pool)
	// The URL points at a private address, which fails before any connect.
	const blocked = "http://127.0.0.1/feed.ics"
	pausedFeed := newIcalFeed(t, pool, seedOwnedApartment(t, pool, 1), blocked)
	freeFeed := newIcalFeed(t, pool, seedApartment(t, pool), blocked)

	billingOn := func(k string) string {
		if k == "UBYHOST_BILLING_ENABLED" {
			return "TRUE"
		}
		return ""
	}
	got, err := SyncAll(ctx, pool, billingOn, FetchOptions{})
	must(t, err)
	if got.Feeds != 1 || got.Errors != 1 {
		t.Fatalf("billing on: feeds=%d errors=%d, want 1 and 1", got.Feeds, got.Errors)
	}
	if f := reloadFeed(t, pool, pausedFeed.ID); f.LastStatus != nil {
		t.Fatalf("paused feed was read: last_status=%q", *f.LastStatus)
	}
	if f := reloadFeed(t, pool, freeFeed.ID); f.LastStatus == nil || *f.LastStatus != "error" {
		t.Fatalf("error feed not marked: %v", f.LastStatus)
	}

	billingOff := func(string) string { return "" }
	got, err = SyncAll(ctx, pool, billingOff, FetchOptions{})
	must(t, err)
	if got.Feeds != 2 || got.Errors != 2 {
		t.Fatalf("billing off: feeds=%d errors=%d, want 2 and 2", got.Feeds, got.Errors)
	}
	if f := reloadFeed(t, pool, pausedFeed.ID); f.LastStatus == nil || *f.LastStatus != "error" {
		t.Fatalf("unpaused feed not marked: %v", f.LastStatus)
	}

	var value string
	must(t, pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = 'last_ical_sync'`).Scan(&value))
	if value == "" {
		t.Fatal("last_ical_sync not written")
	}
}
