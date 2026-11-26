package stays

import (
	"context"
	"net/http"
	"testing"
	"time"
)

func TestArchiveOldUnfilledHandler(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()

	at := time.Date(2026, 11, 26, 10, 0, 0, 0, time.UTC)
	var ownerID, aptID, oldEmptyID, oldWithGuestID, recentEmptyID int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
		 VALUES ('arch_old_owner', 'x', 'host', 1, 1, '2026-01-01T00:00:00Z', 'arch_old@example.test')
		 RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, at)

	if err := pool.QueryRow(ctx,
		`INSERT INTO apartment (owner_user_id, internal_name, active, created_at)
		 VALUES ($1, 'Arch Flat', 1, '2026-01-01T00:00:00Z') RETURNING id`, ownerID).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		 VALUES ($1, 'arch-old-1', '2026-11-01', '2026-11-05', 'active', 'airbnb', '2026-11-01T00:00:00Z', '2026-11-01T00:00:00Z') RETURNING id`, aptID).Scan(&oldEmptyID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		 VALUES ($1, 'arch-old-2', '2026-11-02', '2026-11-06', 'active', 'airbnb', '2026-11-01T00:00:00Z', '2026-11-01T00:00:00Z') RETURNING id`, aptID).Scan(&oldWithGuestID); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO guest (reservation_id, first_name, surname, submit_state, created_at, updated_at)
		 VALUES ($1, 'Jan', 'Novak', 'pending', '2026-11-02T00:00:00Z', '2026-11-02T00:00:00Z')`, oldWithGuestID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		 VALUES ($1, 'arch-old-3', '2026-11-22', '2026-11-25', 'active', 'airbnb', '2026-11-20T00:00:00Z', '2026-11-20T00:00:00Z') RETURNING id`, aptID).Scan(&recentEmptyID); err != nil {
		t.Fatal(err)
	}

	cnt, err := CountOldUnfilled(ctx, pool, ownerID, pragueToday(at))
	if err != nil || cnt != 1 {
		t.Fatalf("CountOldUnfilled = %d, %v; want 1", cnt, err)
	}

	d := postDeps{pool: pool, getenv: createGetenv, now: func() time.Time { return at }}
	h := ArchiveOldUnfilledHandler(d)
	rec := editCSRFPost(t, h, at, "/reservations/archive-old-unfilled", "nonce1", ownerID, nil, nil)
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status = %d, want 303", rec.Code)
	}

	var oldEmptyArch, oldGuestArch, recentArch *string
	_ = pool.QueryRow(ctx, `SELECT archived_at FROM reservation WHERE id = $1`, oldEmptyID).Scan(&oldEmptyArch)
	_ = pool.QueryRow(ctx, `SELECT archived_at FROM reservation WHERE id = $1`, oldWithGuestID).Scan(&oldGuestArch)
	_ = pool.QueryRow(ctx, `SELECT archived_at FROM reservation WHERE id = $1`, recentEmptyID).Scan(&recentArch)
	if oldEmptyArch == nil || *oldEmptyArch == "" {
		t.Fatal("old unfilled stay must be archived")
	}
	if oldGuestArch != nil {
		t.Fatal("old stay WITH guest must NOT be archived")
	}
	if recentArch != nil {
		t.Fatal("recent stay (<7d) must NOT be archived")
	}
}
