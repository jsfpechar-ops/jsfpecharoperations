package ubyport

import (
	"context"
	"fmt"
	"testing"
)

// TestCancelledWithGuestsMailRowAndIdempotency: one queued row with the exact
// columns, the second call returns the same id, mail off writes nothing.
func TestCancelledWithGuestsMailRowAndIdempotency(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	contact := "host@example.cz"
	apt := notifyApartment(t, pool, &contact)
	res, _ := notifyStay(t, pool, apt.ID, fmt.Sprintf("uid-canc-m-%d", apt.ID), "2026-12-01", "2026-12-03")
	id, err := QueueCancelledWithGuestsMail(ctx, pool, notifyMailOn, apt.ID, res, "cancelled")
	if err != nil || id == 0 {
		t.Fatalf("first call: id=%d err=%v", id, err)
	}
	again, err := QueueCancelledWithGuestsMail(ctx, pool, notifyMailOn, apt.ID, res, "cancelled")
	if err != nil || again != id {
		t.Fatalf("second call: id=%d want %d err=%v", again, id, err)
	}
	key := fmt.Sprintf("cancelled_with_guests:%d:cancelled", res)
	if n := notifyCount(t, pool,
		`SELECT count(*) FROM email_outbox WHERE idempotency_key = $1 AND kind = 'cancelled_with_guests'
		   AND reservation_id IS NULL AND apartment_id = $2 AND owner_user_id = $3 AND to_email = $4
		   AND state = 'queued' AND subject LIKE '%cancelled in the calendar%'`,
		key, apt.ID, *apt.OwnerUserID, contact); n != 1 {
		t.Fatalf("want one row with exact columns, got %d", n)
	}
	off, err := QueueCancelledWithGuestsMail(ctx, pool, notifyEnv(map[string]string{}), apt.ID, res, "disappeared")
	if err != nil || off != 0 {
		t.Fatalf("mail off: id=%d err=%v", off, err)
	}
}

// TestCancelledWithGuestsMailNoContact: no contact address means no row and no error.
func TestCancelledWithGuestsMailNoContact(t *testing.T) {
	pool := claimTestPool(t)
	apt := notifyApartment(t, pool, nil)
	res, _ := notifyStay(t, pool, apt.ID, fmt.Sprintf("uid-canc-n-%d", apt.ID), "2026-12-01", "2026-12-03")
	id, err := QueueCancelledWithGuestsMail(context.Background(), pool, notifyMailOn, apt.ID, res, "cancelled")
	if err != nil || id != 0 {
		t.Fatalf("want 0 and nil, got %d %v", id, err)
	}
}

// TestCancelledWithGuestsPush: one row per device, second call 0, push off 0.
func TestCancelledWithGuestsPush(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	apt := notifyApartment(t, pool, nil)
	res, _ := notifyStay(t, pool, apt.ID, fmt.Sprintf("uid-canc-p-%d", apt.ID), "2026-12-01", "2026-12-03")
	notifyDevice(t, pool, *apt.OwnerUserID)
	notifyDevice(t, pool, *apt.OwnerUserID)
	n, err := QueueCancelledWithGuestsPush(ctx, pool, notifyPushOn, apt.ID, res)
	if err != nil || n != 2 {
		t.Fatalf("first call: n=%d err=%v", n, err)
	}
	if rows := notifyCount(t, pool,
		`SELECT count(*) FROM push_outbox WHERE kind = 'cancelled_with_guests' AND url = $1
		   AND params LIKE '%"date": "01.12.2026"%' AND params LIKE '%"property": "%'`,
		fmt.Sprintf("/reservations/%d", res)); rows != 2 {
		t.Fatalf("want 2 rows with the param and url, got %d", rows)
	}
	again, err := QueueCancelledWithGuestsPush(ctx, pool, notifyPushOn, apt.ID, res)
	if err != nil || again != 0 {
		t.Fatalf("second call: n=%d err=%v", again, err)
	}
	off, err := QueueCancelledWithGuestsPush(ctx, pool, notifyEnv(map[string]string{"UBYHOST_WEB_PUSH": "0"}), apt.ID, res)
	if err != nil || off != 0 {
		t.Fatalf("push off: n=%d err=%v", off, err)
	}
}
