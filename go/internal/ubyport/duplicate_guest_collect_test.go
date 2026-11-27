package ubyport

import (
	"context"
	"testing"
	"time"
)

func TestCollectSendable_HoldsDuplicateGuestOnAutoSend(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()

	aptID := collectNewApt(t, pool, map[string]any{
		"automation_mode":    "immediate",
		"submit_after_hours": 24,
		"checkin_hour":       15,
	})
	g1ID := collectAddStay(t, pool, aptID,
		map[string]any{"date_from": "2026-06-01", "date_to": "2026-06-05"},
		map[string]any{"surname": "Novak", "first_name": "Jan", "filled_at": "2026-06-01T14:00:00Z"},
	)
	var resID int64
	if err := pool.QueryRow(ctx, `SELECT reservation_id FROM guest WHERE id = $1`, g1ID).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	var g2ID int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, filled_at, created_at, updated_at) VALUES ($1, '2026-06-01T14:05:00Z', '2026-06-01T14:05:00Z', '2026-06-01T14:05:00Z') RETURNING id`,
		resID).Scan(&g2ID); err != nil {
		t.Fatal(err)
	}
	dup := collectValidGuest(t)
	dup["surname"] = "novak"
	dup["first_name"] = "JAN"
	collectSet(t, pool, "guest", g2ID, dup)

	// 16:30 Prague = 14:30 UTC (past 15:00 check-in hour) so immediate mode is due.
	now := func() time.Time { return time.Date(2026, 6, 1, 14, 30, 0, 0, time.UTC) }
	dec, _ := collectDecrypter(t)

	autoPairs, err := CollectSendable(ctx, pool, aptID, CollectOptions{Now: now, Decrypt: dec})
	if err != nil {
		t.Fatalf("auto collect: %v", err)
	}
	if len(autoPairs) != 1 || autoPairs[0].Outcome.ID != g1ID {
		t.Fatalf("expected only lowest-ID guest %d on auto send, got %d pairs (g2=%d)", g1ID, len(autoPairs), g2ID)
	}

	manualPairs, err := CollectSendable(ctx, pool, aptID, CollectOptions{IgnoreAutomation: true, Now: now, Decrypt: dec})
	if err != nil {
		t.Fatalf("manual collect: %v", err)
	}
	if len(manualPairs) != 2 {
		t.Fatalf("expected both guests returned on manual IgnoreAutomation send, got %d", len(manualPairs))
	}
}
