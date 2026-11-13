package payments

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Brief 1350-fix-1: request cancellation, concurrent deliveries, the Python
// lock, and the redelivery after a failed refund. All need a database.

func bookingEvent(t *testing.T, id, typ, session, intent string) stripeEvent {
	t.Helper()
	obj := map[string]any{"id": session, "object": "checkout.session", "payment_status": "paid"}
	if intent != "" {
		obj["payment_intent"] = intent
	}
	raw, err := json.Marshal(map[string]any{"id": id, "type": typ, "data": map[string]any{"object": obj}})
	if err != nil {
		t.Fatal(err)
	}
	var ev stripeEvent
	if err := json.Unmarshal(raw, &ev); err != nil {
		t.Fatal(err)
	}
	return ev
}

func goldenBookingWebhook(t *testing.T, pool *pgxpool.Pool, g bookingGolden, stripeURL string) *BookingWebhook {
	t.Helper()
	bw := NewBookingWebhook(pool, bookingEnv(g, nil), func() time.Time { return testNow })
	bw.Stripe.APIBase = stripeURL
	return bw
}

// commitTracer calls onCommit once a "commit" statement has finished.
type commitTracer struct {
	sawCommit atomic.Bool
	onCommit  func()
}

func (c *commitTracer) TraceQueryStart(ctx context.Context, _ *pgx.Conn, d pgx.TraceQueryStartData) context.Context {
	if d.SQL == "commit" {
		c.sawCommit.Store(true)
	}
	return ctx
}

func (c *commitTracer) TraceQueryEnd(_ context.Context, _ *pgx.Conn, _ pgx.TraceQueryEndData) {
	if c.sawCommit.CompareAndSwap(true, false) && c.onCommit != nil {
		c.onCommit()
	}
}

// TestBookingSurvivesCancelAfterCommit: Stripe hangs up right after the paid
// commit (the request context is cancelled); the audit line, both mails and
// the event row are still written.
func TestBookingSurvivesCancelAfterCommit(t *testing.T) {
	g := loadBookingGolden(t)
	base := testPool(t)
	seedBookingGolden(t, base, g)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	tracer := &commitTracer{onCommit: cancel}
	cfg := base.Config()
	cfg.ConnConfig.Tracer = tracer
	pool, err := pgxpool.NewWithConfig(context.Background(), cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	_, srv := newFakeStripe(t)
	bw := goldenBookingWebhook(t, pool, g, srv.URL)
	if err := bw.Process(ctx, bookingEvent(t, "evt_cancel", "checkout.session.completed", "cs_1", "pi_1"), "test"); err != nil {
		t.Fatalf("Process after cancel: %v", err)
	}
	if ctx.Err() == nil {
		t.Fatal("the request context was never cancelled")
	}
	checks := map[string]string{
		"paid":     `SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'paid'`,
		"audit":    `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_paid' AND detail LIKE 'id=1 %'`,
		"guest":    `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:1:confirmed'`,
		"host":     `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:1:host_new'`,
		"event":    `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_cancel'`,
		"one_stay": `SELECT COUNT(*) FROM reservation WHERE uid = 'site-1'`,
	}
	for name, q := range checks {
		if n := count(t, base, q); n != 1 {
			t.Errorf("%s: %d rows, want 1", name, n)
		}
	}
}

// TestBookingSurvivesCancelDuringRefund: the request is cancelled while the
// clash refund is in flight; the refund still completes and is recorded.
func TestBookingSurvivesCancelDuringRefund(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		cancel()
		_, _ = io.WriteString(w, `{"id":"re_1","status":"succeeded"}`)
	}))
	t.Cleanup(srv.Close)
	bw := goldenBookingWebhook(t, pool, g, srv.URL)
	if err := bw.Process(ctx, bookingEvent(t, "evt_cancel_refund", "checkout.session.completed", "cs_4", "pi_4"), "test"); err != nil {
		t.Fatalf("Process with cancel during refund: %v", err)
	}
	if calls.Load() != 1 {
		t.Errorf("refund calls: %d, want 1", calls.Load())
	}
	for name, q := range map[string]string{
		"refunded": `SELECT COUNT(*) FROM site_booking WHERE id = 4 AND status = 'clash_refunded'`,
		"audit":    `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded' AND detail LIKE 'id=4 %'`,
		"guest":    `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:4:clash_refund'`,
		"host":     `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:4:host_clash'`,
		"event":    `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_cancel_refund'`,
	} {
		if n := count(t, pool, q); n != 1 {
			t.Errorf("%s: %d rows, want 1", name, n)
		}
	}
}

// TestBookingConcurrentPaidEvents: completed and async_payment_succeeded for
// one paid session, each delivered twice, all at once on separate
// connections: one stay, paid once, no refund, one set of mails.
func TestBookingConcurrentPaidEvents(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stripe, srv := newFakeStripe(t)
	evs := []stripeEvent{
		bookingEvent(t, "evt_c1", "checkout.session.completed", "cs_1", "pi_1"),
		bookingEvent(t, "evt_c2", "checkout.session.async_payment_succeeded", "cs_1", "pi_1"),
		bookingEvent(t, "evt_c1", "checkout.session.completed", "cs_1", "pi_1"),
		bookingEvent(t, "evt_c2", "checkout.session.async_payment_succeeded", "cs_1", "pi_1"),
	}
	start := make(chan struct{})
	errs := make([]error, len(evs))
	var wg sync.WaitGroup
	for i, ev := range evs {
		bw := goldenBookingWebhook(t, pool, g, srv.URL)
		wg.Add(1)
		go func(i int, ev stripeEvent) {
			defer wg.Done()
			<-start
			errs[i] = bw.Process(context.Background(), ev, "test")
		}(i, ev)
	}
	close(start)
	wg.Wait()
	for i, err := range errs {
		if err != nil {
			t.Errorf("event %d: %v", i, err)
		}
	}
	stripe.mu.Lock()
	refunds := len(stripe.calls)
	stripe.mu.Unlock()
	if refunds != 0 {
		t.Errorf("refund calls: %d, want 0", refunds)
	}
	for q, want := range map[string]int{
		`SELECT COUNT(*) FROM reservation WHERE uid = 'site-1'`:                                1,
		`SELECT COUNT(*) FROM reservation WHERE apartment_id = 10`:                             1,
		`SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'paid'`:                   1,
		`SELECT COUNT(*) FROM site_booking WHERE status = 'clash_refunded'`:                    0,
		`SELECT COUNT(*) FROM audit WHERE action = 'site_booking_paid'`:                        1,
		`SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded'`:              0,
		`SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:1:confirmed'`: 1,
		`SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:1:host_new'`:  1,
		`SELECT COUNT(*) FROM email_outbox`:                                                    2,
		`SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id IN ('evt_c1', 'evt_c2')`:     2,
	} {
		if n := count(t, pool, q); n != want {
			t.Errorf("%s: %d, want %d", q, n, want)
		}
	}
}

// TestBookingWaitsForPythonLock: while another transaction holds Python's
// db.lock_key("booking_site_dates", apartment) lock, Go waits and writes
// nothing; once it commits, Go confirms the booking.
func TestBookingWaitsForPythonLock(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	ctx := context.Background()
	holder, err := pool.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer holder.Rollback(ctx)
	if _, err := holder.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext('booking_site_dates'), 10)`); err != nil {
		t.Fatal(err)
	}
	_, srv := newFakeStripe(t)
	bw := goldenBookingWebhook(t, pool, g, srv.URL)
	ev := bookingEvent(t, "evt_lock", "checkout.session.completed", "cs_1", "pi_1")
	done := make(chan error, 1)
	go func() { done <- bw.Process(ctx, ev, "test") }()
	waiting := false
	for deadline := time.Now().Add(10 * time.Second); time.Now().Before(deadline); time.Sleep(20 * time.Millisecond) {
		if count(t, pool, `SELECT COUNT(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted`) == 1 {
			waiting = true
			break
		}
	}
	if !waiting {
		t.Fatal("Go never waited on the booking_site_dates lock")
	}
	select {
	case err := <-done:
		t.Fatalf("Process finished while the lock was held: %v", err)
	default:
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM reservation WHERE uid = 'site-1'`); n != 0 {
		t.Fatalf("stay written while the lock was held")
	}
	if err := holder.Commit(ctx); err != nil {
		t.Fatal(err)
	}
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Process after the lock: %v", err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("Process did not finish after the lock was released")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'paid'`); n != 1 {
		t.Errorf("booking 1 not paid after the lock")
	}
}

// TestBookingRefundReplayAfterFailure: the golden refund-failed event (evt_g08,
// booking 6, pi_fail) answers 500; its redelivery after Stripe recovered
// refunds once and mails once; a further redelivery is a no-op.
func TestBookingRefundReplayAfterFailure(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stripe, srv := newFakeStripe(t)
	bw := goldenBookingWebhook(t, pool, g, srv.URL)
	var ev stripeEvent
	for _, raw := range g.Events {
		var e stripeEvent
		if err := json.Unmarshal(raw, &e); err != nil {
			t.Fatal(err)
		}
		if e.ID == "evt_g08" {
			ev = e
			break
		}
	}
	if ev.ID == "" {
		t.Fatal("evt_g08 not in the golden events")
	}
	if err := bw.Process(context.Background(), ev, "test"); err == nil {
		t.Fatal("first delivery: want an error (Stripe failed)")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 6 AND status = 'pending'`); n != 1 {
		t.Fatal("booking 6 left pending after the failed refund")
	}
	for i := 0; i < 2; i++ {
		if err := bw.Process(context.Background(), ev, "test"); err != nil {
			t.Fatalf("redelivery %d: %v", i+1, err)
		}
	}
	stripe.mu.Lock()
	calls, failed := stripe.calls, stripe.failed
	stripe.mu.Unlock()
	if len(calls) != 2 || failed != 1 {
		t.Errorf("refund calls: %d (%d failed), want 2 (1 failed, 1 succeeded)", len(calls), failed)
	}
	for _, c := range calls {
		if c["idempotency_key"] != "site_booking_clash_refund_6" || c["stripe_account"] != "acct_golden1" {
			t.Errorf("refund call %v", c)
		}
	}
	for q, want := range map[string]int{
		`SELECT COUNT(*) FROM site_booking WHERE id = 6 AND status = 'clash_refunded' AND refunded_czk = 4000`:    1,
		`SELECT COUNT(*) FROM site_booking WHERE status = 'clash_refunded'`:                                       1,
		`SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded' AND detail = 'id=6 amount=4000'`: 1,
		`SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:6:clash_refund'`:                 1,
		`SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:6:host_clash'`:                   1,
		`SELECT COUNT(*) FROM email_outbox`:                                    2,
		`SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_g08'`: 1,
		`SELECT COUNT(*) FROM reservation WHERE uid = 'site-6'`:                0,
	} {
		if n := count(t, pool, q); n != want {
			t.Errorf("%s: %d, want %d", q, n, want)
		}
	}
}
