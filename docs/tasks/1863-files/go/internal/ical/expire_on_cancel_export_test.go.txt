package ical

import (
	"context"
	"testing"
)

func TestExpireOnCancelWrapsUnexported(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)
	viaWrapper := seedReservation(t, pool, apt, "export-wrapper", "2026-12-01", "2026-12-03")
	viaOriginal := seedReservation(t, pool, apt, "export-original", "2026-12-01", "2026-12-03")
	noClaim := seedReservation(t, pool, apt, "export-none", "2026-12-01", "2026-12-03")
	seedClaim(t, pool, viaWrapper, false)
	seedClaim(t, pool, viaOriginal, false)
	must(t, ExpireOnCancel(ctx, pool, viaWrapper))
	must(t, expireOnCancel(ctx, pool, viaOriginal))
	locked := `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1
		AND guest_access_locked_at IS NOT NULL AND token_hash IS NULL AND guest_access_reopened_at IS NULL`
	if w, o := scalarInt(t, pool, locked, viaWrapper), scalarInt(t, pool, locked, viaOriginal); w != 1 || o != 1 {
		t.Fatalf("locked claim rows: wrapper %d, unexported %d", w, o)
	}
	must(t, ExpireOnCancel(ctx, pool, noClaim))
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1`, noClaim); n != 0 {
		t.Fatalf("a claim row appeared for a stay without one: %d", n)
	}
}
