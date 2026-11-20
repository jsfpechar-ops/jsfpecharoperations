package doorwire

import (
	"context"
	"testing"
	"time"
)

// TestLiveBillingReservationProgress is reporting.reservation_progress on a stay with a
// declared head count and no guests yet: nothing filled, the declared count expected.
func TestLiveBillingReservationProgress(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedStay(t, pool, "desk@example.test")
	exec(t, pool, `UPDATE reservation SET declared_guests = 2 WHERE id = 501`)
	b := LiveBilling{Pool: pool, Keys: keys(t), GuestPay: false,
		Now: func() time.Time { return time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC) }}

	filled, expected, err := b.ReservationProgress(ctx, 501)
	if err != nil {
		t.Fatal(err)
	}
	if filled != 0 || expected == nil || *expected != 2 {
		t.Fatalf("progress: filled=%d expected=%v", filled, expected)
	}
	if _, _, err := b.ReservationProgress(ctx, 999); err != errStayNotFound {
		t.Fatalf("missing stay: %v", err)
	}
}

// TestLiveBillingCompletionFeeOff is claim._completion_fee with the guest-pay switch off:
// no fee, so no fee block and no baseline.
func TestLiveBillingCompletionFeeOff(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedStay(t, pool, "desk@example.test")
	b := LiveBilling{Pool: pool, Keys: keys(t), GuestPay: false}
	fee, err := b.CompletionFee(ctx, 21, 501)
	if err != nil || fee != nil {
		t.Fatalf("fee with switch off: %v %v", fee, err)
	}
}
