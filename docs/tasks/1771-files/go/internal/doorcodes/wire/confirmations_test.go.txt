package doorwire

import (
	"context"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// fakeDoors answers completion_door_code with a fixed action (the door-code service is not
// built in these tests).
type fakeDoors struct{ res doorcodes.CompletionResult }

func (f fakeDoors) CompletionDoorCode(context.Context, doorcodes.Reservation, doorcodes.Apartment) (doorcodes.CompletionResult, error) {
	return f.res, nil
}

// fakeBilling stands in for reporting.reservation_progress and claim._completion_fee, so the
// send path does not need guests with complete, encrypted records.
type fakeBilling struct {
	filled   int
	expected *int
	fee      *stayfee.CompletionFee
}

func (f fakeBilling) ReservationProgress(context.Context, int64) (int, *int, error) {
	return f.filled, f.expected, nil
}

func (f fakeBilling) completionFee(context.Context, int64, int64) (*stayfee.CompletionFee, error) {
	return f.fee, nil
}

func intPtr(v int) *int { return &v }

// newConfirmations seeds one legal entity, apartment and stay, and returns the confirmation
// with a fixed clock and a counter of email_outbox rows per idempotency key.
func newConfirmations(t *testing.T, doors fakeDoors, billing fakeBilling) (LiveConfirmations, func(string) int) {
	t.Helper()
	pool := testPool(t)
	seedStay(t, pool, "desk@example.test")
	clock := func() time.Time { return time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC) }
	c := LiveConfirmations{
		Pool:    pool,
		Mailer:  &Mailer{Pool: pool, Env: testEnv, Keys: keys(t), Getenv: consoleEnv, Now: clock},
		Billing: billing,
		Doors:   doors,
		Now:     clock,
	}
	count := func(key string) int {
		var n int
		if err := pool.QueryRow(context.Background(),
			"SELECT count(*) FROM email_outbox WHERE idempotency_key = $1", key).Scan(&n); err != nil {
			t.Fatal(err)
		}
		return n
	}
	return c, count
}

const claimedRow = `INSERT INTO reservation_claim (reservation_id, state, email, lang, completion_notified_at, created_at, updated_at)
	VALUES (501, 'claimed', 'guest@example.test', 'en', NULL, '2026-11-15T10:00:00', '2026-11-15T10:00:00')`

// TestMaybeNotifyCompletionSendsOnce: a claimed stay with its expected count met gets one
// completion mail, keyed completion:<res>:<filled>, and completion_notified_at is set. A second
// call sends nothing.
func TestMaybeNotifyCompletionSendsOnce(t *testing.T) {
	ctx := context.Background()
	c, count := newConfirmations(t, fakeDoors{res: doorcodes.CompletionResult{Action: doorcodes.CompletionWithout}},
		fakeBilling{filled: 1, expected: intPtr(1)})
	exec(t, c.Pool, claimedRow)

	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	if n := count("completion:501:1"); n != 1 {
		t.Fatalf("completion mails: %d", n)
	}
	var stamp *string
	if err := c.Pool.QueryRow(ctx, "SELECT completion_notified_at FROM reservation_claim WHERE reservation_id = 501").Scan(&stamp); err != nil {
		t.Fatal(err)
	}
	if stamp == nil || *stamp == "" {
		t.Fatal("completion_notified_at not set")
	}
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	if n := count("completion:501:1"); n != 1 {
		t.Fatalf("second call sent again: %d", n)
	}
}

// TestMaybeNotifyCompletionFeeBaseline: a stay with a fee sends the bill and records the fee
// total the mail states as the baseline (fee_update.record_baseline).
func TestMaybeNotifyCompletionFeeBaseline(t *testing.T) {
	ctx := context.Background()
	fee := &stayfee.CompletionFee{Total: 1700, Lines: [][2]int{{2, 850}}, Rate: 850, VS: "501",
		Ways: []stayfee.CompletionWay{{Key: "cash", Note: "Pay at the desk"}}}
	c, count := newConfirmations(t, fakeDoors{res: doorcodes.CompletionResult{Action: doorcodes.CompletionWithout}},
		fakeBilling{filled: 1, expected: intPtr(1), fee: fee})
	exec(t, c.Pool, claimedRow)
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	if n := count("completion:501:1"); n != 1 {
		t.Fatalf("completion mails: %d", n)
	}
	var baseline *int
	if err := c.Pool.QueryRow(ctx, "SELECT fee_mailed_total FROM reservation_claim WHERE reservation_id = 501").Scan(&baseline); err != nil {
		t.Fatal(err)
	}
	if baseline == nil || *baseline != 1700 {
		t.Fatalf("fee baseline: %v", baseline)
	}
}

// TestMaybeNotifyCompletionGuards: an unclaimed or provisional claim, and a stay short of its
// expected count, send nothing.
func TestMaybeNotifyCompletionGuards(t *testing.T) {
	ctx := context.Background()
	c, count := newConfirmations(t, fakeDoors{res: doorcodes.CompletionResult{Action: doorcodes.CompletionWithout}},
		fakeBilling{filled: 1, expected: intPtr(2)})
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	exec(t, c.Pool, `INSERT INTO reservation_claim (reservation_id, state, email, lang, completion_notified_at, created_at, updated_at)
		VALUES (501, 'provisional', 'guest@example.test', 'en', NULL, '2026-11-15T10:00:00', '2026-11-15T10:00:00')`)
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	exec(t, c.Pool, `UPDATE reservation_claim SET state = 'claimed' WHERE reservation_id = 501`)
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	if n := count("completion:501:1"); n != 0 {
		t.Fatalf("guarded call sent a mail: %d", n)
	}
}

// TestMaybeNotifyCompletionHoldWaitsUnlessForced: a held door code waits, and force sends the
// receipt without the code block.
func TestMaybeNotifyCompletionHoldWaitsUnlessForced(t *testing.T) {
	ctx := context.Background()
	c, count := newConfirmations(t, fakeDoors{res: doorcodes.CompletionResult{Action: doorcodes.CompletionHold}},
		fakeBilling{filled: 1, expected: intPtr(1)})
	exec(t, c.Pool, claimedRow)
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, false); err != nil {
		t.Fatal(err)
	}
	if n := count("completion:501:1"); n != 0 {
		t.Fatalf("held confirmation was sent: %d", n)
	}
	if err := c.MaybeNotifyCompletion(ctx, 501, 21, true); err != nil {
		t.Fatal(err)
	}
	if n := count("completion:501:1"); n != 1 {
		t.Fatalf("forced confirmation not sent: %d", n)
	}
}

// TestEncodeCompletionPayloadWritesIntegersAndNull: the receipt's integer and None values are
// written as json.dumps writes them, in the payload order encodePayload uses.
func TestEncodeCompletionPayloadWritesIntegersAndNull(t *testing.T) {
	got, err := encodeCompletionPayload(map[string]any{
		"receipt_details_reservation_id": int64(501),
		"door_code_enc":                  nil,
		"lang":                           "en",
		"text":                           "a",
	})
	if err != nil {
		t.Fatal(err)
	}
	want := `{"text": "a", "lang": "en", "door_code_enc": null, "receipt_details_reservation_id": 501}`
	if got != want {
		t.Fatalf("got  %s\nwant %s", got, want)
	}
}
