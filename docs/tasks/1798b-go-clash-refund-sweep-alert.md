# 1798b: stripe_sweep retries due clash refunds and alerts the operator once (Go)

Status: todo
Depends on: 1798a (its code is the anchor here), 1797 (`b.booking` takes a `dbtx`; committed) | Base commit: the tip of the working branch after 1798a | Branch: task/1798b-go-clash-refund-sweep
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (money path; exact diffs only; a fresh reviewer reads the full diff of every file in section 3)
First half: [1798a](1798a-go-clash-refund-due-state.md). Plan: `docs/plans/ai-payments-hardening.md`, "P1 Fix before Stripe goes live", item 3.

## 1. Objective

The daily `stripe_sweep` job retries every due `site_booking_refund_due` row (1798a) with the same Stripe idempotency key, removes rows whose booking was refunded or paid meanwhile, and raises one operator alert per booking after 5 failed tries or 24 hours. A guest who paid for nights someone else got is then either refunded or known to the operator, even after Stripe stops retrying the webhook.

## 2. Context

**Rules that apply (pasted).**
- AGENTS.md 2: privacy first. The alert text holds a booking id, a count, a Stripe error code and the payment intent id; never the guest's name or e-mail. Logs: same.
- AGENTS.md 4: no new dependency. AGENTS.md 11 / go-first and owner decision 2026-11-16: Go only; no change under `App/app/`.
- rules.md "State machines": no status value changes (see 1798a section 2).

**Design choices (verified against the code).**
- **Job: extend `stripe_sweep`, no new kind.** A new kind needs the Go scheduler plan (`go/internal/scheduler/scheduler.go` `Plan`), its Python twin (`App/app/scheduler.py` `CRON_TIMES`, the worker fallback, `test_scheduler_go_switch`), `UBYHOST_JOB_QUEUE_KINDS`/`UBYHOST_GO_JOB_KINDS`, `jobNames` in `go/internal/jobs/queue.go` and the `notification.job_name.*` strings in `App/app/host_i18n.py`: Python changes the owner ruled out. `stripe_sweep` runs once a day at 04:15 Europe/Prague (`scheduler.go` line 125, `jobIntervals` 24*60 in `register_jobs.go`); a failed job run is retried by the queue with backoff and raises the existing `job_failed` "payment check" alert.
- **Backoff:** the row's `next_attempt_at` after the n-th failed try is +1 h, 2 h, 4 h, 8 h, 16 h, then 24 h (`refundBackoff`, 1798a). Stripe drives the webhook retries (it ignores `next_attempt_at`); the sweep tries only rows that are due, so in practice once a day. A day apart also matters because Stripe replays a cached result for the same key for about 24 hours (Stripe docs; not verifiable offline).
- **Alert: N = 5 failed tries or X = 24 hours since the clash**, whichever comes first, once per booking. "Once" is an atomic `UPDATE ... SET alerted_at ... WHERE alerted_at IS NULL ... RETURNING`: only the run whose UPDATE returns a row raises it. A Stripe-closed run (off, or the call cap reached) is not a try, so only the 24 h rule can fire then.
- **Alert path: `ubyport.RaiseAlert`** (`go/internal/ubyport/effects.go`), level `critical`, kind `site_booking_refund_stuck`, dedupe key `site_booking_refund_stuck:<id>`, no apartment, stay or owner (a system alert: the host does not see it; the admin Operations page lists every open alert by kind, `go/internal/web/auth/opspage/data.go` `loadAlerts`). Resolved with `ubyport.ResolveAlert` when the refund goes through. Not an operator mail: Go's only operator mail (`deadline_digest`, `go/internal/calendar/filing_watchdog_run.go`) is a filing digest, and a new mail kind must be listed in `App/app/mail.py` `KINDS`/`HOST_KINDS` (Python). See the open questions.
- **Guest mail:** the existing `site_booking_refunded` guest mail and `site_booking_host` host mail (`mailClash`) already go out after a successful refund, now from the sweep too, once (the mail keys are `site_booking:<id>:clash_refund` and `:host_clash`; 1798a writes them only on the run that moves the booking). No new mail kind.
- **Race (webhook retry and sweep at once):** both send `Idempotency-Key: site_booking_clash_refund_<id>`, so Stripe makes one refund; `setStatus` moves the booking once; only that run writes the audit line and the mails; every successful run deletes the row.
- **Call cap:** each try passes `guard` (`onboarder.go`), which counts it in `lock_api_usage` before the request; at most 20 rows per sweep (`refundDueSweepLimit`; 20 x 30 s client timeout stays far under the job lease of 60 minutes, `jobs.LeaseMinutes`).

**Production.** The rows exist only when the Go booking webhook runs (`UBYHOST_GO_BOOKING_WEBHOOK=1`, brief 1554, after 1796, 1797, 1798a and 1798b) and the retry runs only when `stripe_sweep` is in `UBYHOST_GO_JOB_KINDS` on the server (owner step 2). Until then Python handles booking events with the old behaviour (owner: not patched; Stripe is in test mode).

**Excerpts (anchors; if one is not found verbatim, STOP, section 8).**

A. `go/internal/payments/booking_refund_due.go` (from 1798a), end of the import block:
```go
	"github.com/jackc/pgx/v5"
)
```
B. Same file, end of `refundFailed`:
```go
	if _, err := b.Pool.Exec(ctx, refundDueNextSQL, bookingID, stampAt(now.Add(refundBackoff(n)))); err != nil {
		log.Printf("clash refund: set next try for site booking %d: %v", bookingID, err)
	}
}
```
C. Same file, the whole `refundDone` (the last function of the file):
```go
// refundDone removes the row once the booking is clash_refunded (or paid).
func (b *BookingWebhook) refundDone(ctx context.Context, bookingID int64) error {
	_, err := b.Pool.Exec(ctx, refundDueDeleteSQL, bookingID)
	return err
}
```
D. `go/cmd/ubyhost-web/register_jobs.go`:
```go
		"stripe_sweep": func(ctx context.Context) (int, error) {
			expired, deleted, err := payments.Sweep(ctx, pool, time.Now().UTC(), jobs.Now(0))
			return expired + deleted, err
		},
```
E. `go/internal/payments/booking_webhook.go` (unchanged here, must exist): `func (b *BookingWebhook) booking(ctx context.Context, q dbtx, sql string, arg any) (*siteBooking, error) {`
F. `go/internal/ubyport/effects.go` (unchanged here, must exist): `func RaiseAlert(ctx context.Context, pool *pgxpool.Pool, level, kind, message, detail, dedupeKey string,` and `func ResolveAlert(ctx context.Context, pool *pgxpool.Pool, dedupeKey string) error {`
G. `go/internal/payments/booking_refund_due_test.go` (from 1798a) exists and ends with `func TestClashGoneClearsDue`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/payments/booking_refund_due.go` | edit | anchors A, B, C (steps 1 to 3) |
| `go/cmd/ubyhost-web/register_jobs.go` | edit | anchor D (step 4) |
| `go/internal/payments/booking_refund_due_test.go` | edit | append four tests (step 5) |
| `docs/tasks/1798b-report.md` | create | report (section 9) |

No other file may change.

## 4. Steps

First check anchors E, F and G: `grep -nF 'func (b *BookingWebhook) booking(ctx context.Context, q dbtx, sql string, arg any)' go/internal/payments/booking_webhook.go; grep -nF 'func ResolveAlert(ctx context.Context, pool *pgxpool.Pool, dedupeKey string) error {' go/internal/ubyport/effects.go; grep -n 'func TestClashGoneClearsDue' go/internal/payments/booking_refund_due_test.go`: three hits, else STOP. Run each step's command and the commit in one Bash call: `<command> 2>&1 | tail -30; git add -A && git commit -qm "1798b step k"`.

1. `booking_refund_due.go`, anchor A. Replace it with
```go
	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)
```
   No command (the import is unused until step 3); commit with step 3.

2. Anchor B. Replace it with
```go
	if _, err := b.Pool.Exec(ctx, refundDueNextSQL, bookingID, stampAt(now.Add(refundBackoff(n)))); err != nil {
		log.Printf("clash refund: set next try for site booking %d: %v", bookingID, err)
	}
	if _, err := b.alertIfStuck(ctx, bookingID); err != nil {
		log.Printf("clash refund: operator alert for site booking %d: %v", bookingID, err)
	}
}
```
   No command; commit with step 3.

3. Anchor C. Replace it with
```go
// refundDone removes the row once the booking is clash_refunded (or paid) and
// resolves its operator alert, if one was raised.
func (b *BookingWebhook) refundDone(ctx context.Context, bookingID int64) error {
	if _, err := b.Pool.Exec(ctx, refundDueDeleteSQL, bookingID); err != nil {
		return err
	}
	return ubyport.ResolveAlert(ctx, b.Pool, refundStuckAlertKey(bookingID))
}

// --- stripe_sweep retry and operator alert (brief 1798b) ----------------------

const (
	// The operator alert goes out once per booking, after refundDueAlertAttempts
	// failed tries or refundDueAlertAge since the clash, whichever comes first.
	refundDueAlertAttempts = 5
	refundDueAlertAge      = 24 * time.Hour
	// refundDueSweepLimit bounds one stripe_sweep pass (each try may take the
	// 30 s Stripe timeout; the job lease is 60 minutes).
	refundDueSweepLimit  = 20
	refundStuckAlertKind = "site_booking_refund_stuck"

	refundDueClaimAlertSQL = `UPDATE site_booking_refund_due SET alerted_at = $2, updated_at = $2
		WHERE site_booking_id = $1 AND alerted_at IS NULL AND (attempts >= $3 OR created_at <= $4)
		RETURNING attempts, COALESCE(payment_intent_id, ''), COALESCE(last_error, '')`
	refundDueUnclaimSQL = `UPDATE site_booking_refund_due SET alerted_at = NULL WHERE site_booking_id = $1`
	refundDueListSQL    = `SELECT site_booking_id, COALESCE(payment_intent_id, '') FROM site_booking_refund_due
		WHERE next_attempt_at <= $1 ORDER BY site_booking_id LIMIT $2`
)

// refundStuckAlertKey is the dedupe key of the operator alert for one booking.
func refundStuckAlertKey(bookingID int64) string {
	return fmt.Sprintf("%s:%d", refundStuckAlertKind, bookingID)
}

// alertIfStuck raises the operator alert for one booking, once. The UPDATE that
// sets alerted_at is the claim, so two runs at once raise one alert; if raising
// fails, the claim is given back for the next run. It is a system alert (no
// owner, apartment or stay): the admin Operations page lists it, the host does
// not see it. The text holds ids, a count and a Stripe error code only.
func (b *BookingWebhook) alertIfStuck(ctx context.Context, bookingID int64) (bool, error) {
	now := b.Now()
	var attempts int64
	var intent, lastErr string
	err := b.Pool.QueryRow(ctx, refundDueClaimAlertSQL, bookingID, stampAt(now),
		int64(refundDueAlertAttempts), stampAt(now.Add(-refundDueAlertAge))).Scan(&attempts, &intent, &lastErr)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if intent == "" {
		intent = "unknown"
	}
	if lastErr == "" {
		lastErr = "none (Stripe closed: off, or the monthly call cap reached)"
	}
	message := fmt.Sprintf("Clash refund for site booking %d has not gone through.", bookingID)
	detail := fmt.Sprintf("The guest paid and has no booking. Failed tries: %d. Last error: %s. "+
		"Payment intent: %s (host's connected account). The payment check job tries again once a day.",
		attempts, lastErr, intent)
	if err := ubyport.RaiseAlert(ctx, b.Pool, "critical", refundStuckAlertKind, message, detail,
		refundStuckAlertKey(bookingID), nil, nil, nil, nil); err != nil {
		if _, uerr := b.Pool.Exec(ctx, refundDueUnclaimSQL, bookingID); uerr != nil {
			log.Printf("clash refund: give back alert claim for site booking %d: %v", bookingID, uerr)
		}
		return false, err
	}
	return true, nil
}

// RefundSweep counts one RetryClashRefunds pass.
type RefundSweep struct {
	Due, Refunded, Alerted int
}

// RetryClashRefunds is the stripe_sweep step for clash refunds that have not
// gone through: each due row gets one more try with the same Idempotency-Key.
// A row whose booking was refunded or paid meanwhile is removed. A row still
// open after its turn is checked for the operator alert. Only a database error
// fails the pass; a failed try is counted on its row and logged without guest
// data.
func (b *BookingWebhook) RetryClashRefunds(ctx context.Context) (RefundSweep, error) {
	var out RefundSweep
	type due struct {
		id     int64
		intent string
	}
	rows, err := b.Pool.Query(ctx, refundDueListSQL, stampAt(b.Now()), refundDueSweepLimit)
	if err != nil {
		return out, err
	}
	var list []due
	for rows.Next() {
		var d due
		if err := rows.Scan(&d.id, &d.intent); err != nil {
			rows.Close()
			return out, err
		}
		list = append(list, d)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	out.Due = len(list)
	for _, d := range list {
		bk, err := b.booking(ctx, b.Pool, bookingByIDSQL, d.id)
		if err != nil {
			return out, err
		}
		if bk == nil {
			continue // the booking is gone; the foreign key removed its row
		}
		switch bk.status {
		case "clash_refunded", "paid":
			if err := b.refundDone(ctx, d.id); err != nil {
				return out, err
			}
			continue
		case "pending", "expired":
			err := b.refundClash(ctx, bk, d.intent)
			if err == nil {
				out.Refunded++
				continue
			}
			log.Printf("stripe_sweep: clash refund for site booking %d not done: %v", d.id, err)
		}
		alerted, err := b.alertIfStuck(ctx, d.id)
		if err != nil {
			return out, err
		}
		if alerted {
			out.Alerted++
		}
	}
	return out, nil
}
```
   Command: `gofmt -w go/internal/payments/booking_refund_due.go && cd go && go build ./internal/payments/ && go vet ./internal/payments/` : no output.

4. `register_jobs.go`, anchor D. Replace it with
```go
		"stripe_sweep": func(ctx context.Context) (int, error) {
			expired, deleted, err := payments.Sweep(ctx, pool, time.Now().UTC(), jobs.Now(0))
			if err != nil {
				return expired + deleted, err
			}
			// 1798b: retry clash refunds that have not gone through; alert the operator once.
			refunds, err := payments.NewBookingWebhook(pool, os.Getenv, time.Now).RetryClashRefunds(ctx)
			if refunds != (payments.RefundSweep{}) {
				slog.Info("clash refunds", "due", refunds.Due, "refunded", refunds.Refunded, "alerted", refunds.Alerted)
			}
			return expired + deleted + refunds.Refunded, err
		},
```
   (`os`, `slog` and `time` are already imported.) Command: `gofmt -l go/cmd/ubyhost-web/ | head -50; cd go && go build ./... && go vet ./cmd/ubyhost-web/` : no output.

5. Append exactly this to the end of `go/internal/payments/booking_refund_due_test.go` (for example `cat >> go/internal/payments/booking_refund_due_test.go <<'EOF'` ... `EOF`); no import changes are needed:
```go

// --- 1798b: stripe_sweep retry and operator alert ---------------------------

func alertCount(t *testing.T, pool *pgxpool.Pool) int {
	t.Helper()
	return count(t, pool, `SELECT COUNT(*) FROM alert WHERE kind = 'site_booking_refund_stuck'`)
}

// The sweep leaves a row alone until it is due, then makes exactly one call
// with the same key; the refund is made once and the row goes.
func TestClashRefundSweepRetries(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stub, srv := newRefundStub(t, 1)
	ctx := context.Background()
	ev := clashEvent4(t)
	if err := refundDueHandler(pool, g, srv.URL, testNow, nil).Process(ctx, ev, "test"); err == nil {
		t.Fatal("first try should fail")
	}
	early := refundDueHandler(pool, g, srv.URL, testNow.Add(30*time.Minute), nil)
	if sum, err := early.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{}) {
		t.Fatalf("sweep before the next try: %+v, %v", sum, err)
	}
	sweep := refundDueHandler(pool, g, srv.URL, testNow.Add(2*time.Hour), nil)
	if sum, err := sweep.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{Due: 1, Refunded: 1}) {
		t.Fatalf("sweep: %+v, %v", sum, err)
	}
	calls, refunds := stub.seen()
	if len(calls) != 2 || refunds != 1 || calls[0] != "site_booking_clash_refund_4" || calls[1] != calls[0] {
		t.Errorf("Stripe calls %v, refunds %d: want one sweep call with the same key", calls, refunds)
	}
	if _, ok := readDue(t, pool, 4); ok {
		t.Error("due row kept after the sweep refunded")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 4 AND status = 'clash_refunded' AND refunded_czk = 4000`); n != 1 {
		t.Errorf("booking 4 not clash_refunded")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded'`); n != 1 {
		t.Errorf("%d refund audit lines, want 1", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:4:clash_refund'`); n != 1 {
		t.Errorf("%d guest refund mails, want 1", n)
	}
	if sum, err := sweep.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{}) {
		t.Errorf("second sweep: %+v, %v", sum, err)
	}
	if err := refundDueHandler(pool, g, srv.URL, testNow.Add(3*time.Hour), nil).Process(ctx, ev, "test"); err != nil {
		t.Errorf("Stripe redelivery after the sweep: %v", err)
	}
	if calls, _ := stub.seen(); len(calls) != 2 {
		t.Errorf("Stripe called again after the refund: %v", calls)
	}
	if n := alertCount(t, pool); n != 0 {
		t.Errorf("%d operator alerts, want 0", n)
	}
}

// After 5 failed tries exactly one operator alert exists, whatever runs after;
// it holds no guest data and is resolved when the refund finally goes through.
func TestClashRefundAlertOnce(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stub, srv := newRefundStub(t, 1000)
	ctx := context.Background()
	ev := clashEvent4(t)
	hook := refundDueHandler(pool, g, srv.URL, testNow, nil)
	for i := 1; i <= refundDueAlertAttempts; i++ {
		if err := hook.Process(ctx, ev, "test"); err == nil {
			t.Fatalf("try %d should fail", i)
		}
		want := 0
		if i == refundDueAlertAttempts {
			want = 1
		}
		if n := alertCount(t, pool); n != want {
			t.Errorf("after try %d: %d alerts, want %d", i, n, want)
		}
	}
	for i := 0; i < 2; i++ {
		if err := hook.Process(ctx, ev, "test"); err == nil {
			t.Fatal("retry should fail")
		}
	}
	late := refundDueHandler(pool, g, srv.URL, testNow.Add(25*time.Hour), nil)
	if sum, err := late.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{Due: 1}) {
		t.Fatalf("late sweep: %+v, %v", sum, err)
	}
	if n := alertCount(t, pool); n != 1 {
		t.Errorf("%d alerts, want exactly 1", n)
	}
	d, _ := readDue(t, pool, 4)
	if d.Attempts != 8 || d.AlertedAt != stampAt(testNow) {
		t.Errorf("due row %+v, want 8 tries and alerted at the fifth", d)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM alert WHERE kind = 'site_booking_refund_stuck'
		AND level = 'critical' AND owner_user_id IS NULL AND apartment_id IS NULL AND reservation_id IS NULL
		AND dedupe_key = 'site_booking_refund_stuck:4' AND resolved_at IS NULL
		AND message || COALESCE(detail, '') NOT LIKE '%example.test%'
		AND message || COALESCE(detail, '') NOT LIKE '%Test Guest%'`); n != 1 {
		t.Errorf("alert row not as expected (critical, system, open, no guest data)")
	}
	stub.mu.Lock()
	stub.fail = 0
	stub.mu.Unlock()
	fixed := refundDueHandler(pool, g, srv.URL, testNow.Add(50*time.Hour), nil)
	if sum, err := fixed.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{Due: 1, Refunded: 1}) {
		t.Fatalf("sweep after Stripe recovered: %+v, %v", sum, err)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM alert WHERE dedupe_key = 'site_booking_refund_stuck:4' AND resolved_at IS NOT NULL`); n != 1 {
		t.Errorf("alert not resolved after the refund")
	}
	if _, refunds := stub.seen(); refunds != 1 {
		t.Errorf("%d refunds, want 1", refunds)
	}
}

// With the call cap reached nothing is counted and Stripe is not called; only
// the 24 hour rule raises the alert, once.
func TestClashRefundCapAlertsByAge(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	capReached(t, pool)
	stub, srv := newRefundStub(t, 0)
	ctx := context.Background()
	if err := refundDueHandler(pool, g, srv.URL, testNow, refundCapEnv).Process(ctx, clashEvent4(t), "test"); !errors.Is(err, ErrStripeOff) {
		t.Fatalf("Process = %v, want ErrStripeOff", err)
	}
	soon := refundDueHandler(pool, g, srv.URL, testNow.Add(2*time.Hour), refundCapEnv)
	if sum, err := soon.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{Due: 1}) {
		t.Fatalf("sweep at +2 h: %+v, %v", sum, err)
	}
	if n := alertCount(t, pool); n != 0 {
		t.Errorf("alert before 24 h without a failed try")
	}
	late := refundDueHandler(pool, g, srv.URL, testNow.Add(25*time.Hour), refundCapEnv)
	if sum, err := late.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{Due: 1, Alerted: 1}) {
		t.Fatalf("sweep at +25 h: %+v, %v", sum, err)
	}
	later := refundDueHandler(pool, g, srv.URL, testNow.Add(26*time.Hour), refundCapEnv)
	if sum, err := later.RetryClashRefunds(ctx); err != nil || sum != (RefundSweep{Due: 1}) {
		t.Fatalf("sweep at +26 h: %+v, %v", sum, err)
	}
	if n := alertCount(t, pool); n != 1 {
		t.Errorf("%d alerts, want 1", n)
	}
	if d, ok := readDue(t, pool, 4); !ok || d.Attempts != 0 {
		t.Errorf("due row %+v (found %v), want 0 tries", d, ok)
	}
	if calls, _ := stub.seen(); len(calls) != 0 {
		t.Errorf("Stripe called %d times with the cap reached", len(calls))
	}
}

// A Stripe redelivery and the sweep running at once make one refund, one audit
// line and one guest mail.
func TestClashRefundSweepRaceOneRefund(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stub, srv := newRefundStub(t, 1)
	ctx := context.Background()
	ev := clashEvent4(t)
	hook := refundDueHandler(pool, g, srv.URL, testNow, nil)
	if err := hook.Process(ctx, ev, "test"); err == nil {
		t.Fatal("first try should fail")
	}
	sweep := refundDueHandler(pool, g, srv.URL, testNow.Add(2*time.Hour), nil)
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		if err := hook.Process(ctx, ev, "test"); err != nil {
			t.Errorf("webhook retry: %v", err)
		}
	}()
	go func() {
		defer wg.Done()
		if _, err := sweep.RetryClashRefunds(ctx); err != nil {
			t.Errorf("sweep: %v", err)
		}
	}()
	wg.Wait()
	calls, refunds := stub.seen()
	if refunds != 1 {
		t.Errorf("%d refunds made, want 1", refunds)
	}
	for _, k := range calls {
		if k != "site_booking_clash_refund_4" {
			t.Errorf("idempotency key %q", k)
		}
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 4 AND status = 'clash_refunded'`); n != 1 {
		t.Errorf("booking 4 not clash_refunded")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded'`); n != 1 {
		t.Errorf("%d refund audit lines, want 1", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:4:clash_refund'`); n != 1 {
		t.Errorf("%d guest refund mails, want 1", n)
	}
	if _, ok := readDue(t, pool, 4); ok {
		t.Error("due row kept")
	}
}
```
   Command: `gofmt -l go/internal/payments/ | head -50` prints nothing (if it lists a section 3 file, `gofmt -w` that file only), then `cd go && go test ./internal/payments/ -run 'TestRefundDue|TestClashRefund|TestClashGone' -count=1 -race -v 2>&1 | tail -30`: every test `PASS`, none `SKIP` (needs `UBYHOST_TEST_DATABASE_URL`; without it they SKIP: say so in the report).

6. Run all of section 6. Commit only if a command changed a file.

## 5. Do not touch

- Every file not in section 3; especially `App/app/` (owner: Go only), `go/internal/scheduler/`, `go/internal/jobs/`, `booking_webhook.go`, `onboarder.go`, the golden files and `booking_webhook_test.go`.
- Do not add a job kind, a mail kind, a status value or an i18n string.
- No new dependency. No live Stripe call in a test. Never log or store guest name or e-mail. Never push to `main`; merge only with `scripts/merge-pr-on-green.sh` (owner).

## 6. Commands

- `cd go && go build ./... 2>&1 | tail -30` : no output.
- `cd go && go vet ./internal/payments/ ./cmd/ubyhost-web/ 2>&1 | tail -30` : no output.
- `gofmt -l go/internal/payments/ go/cmd/ubyhost-web/ | head -50` : no output.
- `cd go && go test ./internal/payments/ -count=1 2>&1 | tail -30` : `ok` (includes the golden test and all 1798a tests).
- `cd go && go test ./internal/payments/ -count=1 -v 2>&1 | grep -c -- '--- SKIP'` : `0` with `UBYHOST_TEST_DATABASE_URL` set.
- `cd go && go test ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30` : `ok`.
- `python3 scripts/context_lint.py 2>&1 | tail -3` : `context lint: OK`.

## 7. Acceptance

- [ ] `grep -c 'RetryClashRefunds(ctx)' go/cmd/ubyhost-web/register_jobs.go` prints `1`; `grep -c '"stripe_sweep"' go/cmd/ubyhost-web/register_jobs.go` still prints `2` (interval and handler).
- [ ] `grep -c 'alertIfStuck(ctx, bookingID)' go/internal/payments/booking_refund_due.go` prints `1`; `grep -c 'ResolveAlert' go/internal/payments/booking_refund_due.go` prints `1`.
- [ ] The four new tests and the five 1798a tests PASS, not SKIP, with a test database (in CI at least), also under `-race`.
- [ ] All section 6 commands as expected; `git diff --stat` lists only section 3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt (A to G) is not found verbatim;
- `TestBookingWebhookMatchesPython` or a 1798a test fails;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1798b-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

Open one draft PR. Its body says: outbound requests: retries of the existing `POST /v1/refunds` on the host's connected account from the daily `stripe_sweep` job, at most 20 a day, each counted against `UBYHOST_STRIPE_MONTHLY_API_CALLS`, reason: refund a guest whose clash refund failed; retention: no personal data stored, no `retention.py` line; Python unchanged (owner: Go only).

## Risk list (for the reviewer)

Full diff of `booking_refund_due.go` (alert claim, sweep loop, refundDone), `register_jobs.go`.

## Owner steps

1. Wait for the fresh Tier A review of the full diff, then merge with `scripts/merge-pr-on-green.sh` when CI is green (the new tests must show as run, not skipped).
2. Before switching the Go booking webhook on (brief 1554): on the server, open the `.env` the deploy uses, find the line `UBYHOST_GO_JOB_KINDS=` and check that `stripe_sweep` is in its comma list (and in `UBYHOST_JOB_QUEUE_KINDS=`). If it is missing, add it to both, save, and run `./scripts/deploy.sh`. Without this the Python worker runs `stripe_sweep` and no refund is retried.
3. When the alert "Clash refund for site booking N has not gone through" shows on the admin Operations page: open the host's connected account in the Stripe dashboard, find the payment intent named in the alert, and refund it or fix the cause. The job keeps trying once a day; the alert clears itself when a try succeeds.

## Plan differences

- The plan says "retry from a sweeper job": `stripe_sweep` runs once a day, so retries after Stripe stops are daily, not on a finer backoff (a new frequent kind needs Python scheduler changes; see section 2).
- The plan says "alert the operator": done as a critical system alert on the admin Operations page, not a mail (a new mail kind needs `App/app/mail.py`).
- Guest mail on success already existed (`site_booking_refunded`), now sent from the sweep too; no new kind.

## Open questions for the owner

1. Should the operator also get a mail or push for this alert? That needs a new mail kind in `App/app/mail.py` (Python) or a Go operator-mail helper; not built. Not verified here: whether a critical system alert already triggers any push or mail to the operator.
2. Is a daily retry fast enough once Stripe stops redelivering the webhook (Stripe retries for up to 3 days in live mode)? A faster retry means a new job kind with Python scheduler changes.
3. Not verified: how the Python admin alert list shows a kind that is not in `SYSTEM_ALERT_KINDS` (`App/app/alerts.py`) and has no `notification.<kind>.title` string; it falls back to the stored English message (`_localised`), and the Go Operations page lists it by kind.
