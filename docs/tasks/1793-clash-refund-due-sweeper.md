# 1793: Failed clash refund: `refund_due` state, daily retry, operator alert

Status: todo
Depends on: 1792 | Base commit: `main` after 1792 merged | Branch: task/1793-clash-refund-due
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (money path). No migration (see §2).

## 1. Objective

When the Stripe refund after a calendar clash fails, the Go webhook parks the booking as `refund_due` (with the payment intent), opens an operator-only alert and still answers 500. Stripe's redeliveries and the daily `stripe_sweep` job then retry the refund with the same idempotency key until it goes through (`clash_refunded`), so the guest gets a refund or the operator gets a visible alert. Today, once Stripe stops retrying, the guest has paid and has neither a booking nor a refund.

## 2. Context

Plan: docs/plans/ai-payments-hardening.md, P1 item 3. **Plan differs:** the plan cites `booking_webhook.go:345-366`; `refundClash` is at lines 343-373 on base `5f411a9` (1792 may shift lines; the excerpts below are what counts).

Rules that apply ([rules: state machines](../context/rules.md#state-machines)): every status column has one `TRANSITIONS` table and a pin test; a Go writer has a twin in `go/internal/statemachine/tables.go` (checked by `test_sm_go_parity.py`); writes are one atomic `UPDATE ... WHERE id = ? AND status IN (...)`; a column written in both languages changes in both in one PR.

Decisions taken in this brief (do not redesign):
- **No migration.** `site_booking.status` is `TEXT ... NOT NULL DEFAULT 'pending'` with no CHECK (`App/migrations_pg/00004_site_booking.sql:10`); `stripe_payment_intent_id` already exists. No new column, no new personal data, so no `retention.py` line.
- **Moves:** `pending -> refund_due`, `expired -> refund_due` (refund failed after a clash; atomic SQL `bookingRefundDueSQL`), `refund_due -> clash_refunded` (a retry succeeded; existing `setStatus`, which is `UPDATE ... WHERE id = $n AND status = $cur`). Nothing else leaves `refund_due`.
- **Retries and backoff:** (1) Stripe redelivers the event (we still return the error); `handle` now sends a `refund_due` booking straight to `refundClash`. (2) `stripe_sweep` (daily 04:15, existing job kind, so `TestLaneKindsDisjoint` and `UBYHOST_JOB_QUEUE_KINDS` are unchanged) calls `RetryRefundDue`: one try per day per booking, at most 50 bookings per run, only while `updated_at` (stamp of the first failure; a failed retry does not change it) is younger than 14 days. After that the alert stays open for a refund by hand.
- **No double refund:** every try sends `Idempotency-Key: site_booking_clash_refund_<id>` and refunds the whole payment intent. Stripe forgets a key after 24 h; a later try against an already refunded charge gets Stripe error code `charge_already_refunded`, which `tryRefund` treats as success.
- **Operator alert:** reuses the `alert` table the way `jobs.RaiseFailed` (go/internal/jobs/queue.go:141-165) does: update-then-insert by `dedupe_key`. Kind `site_booking_refund_due`, level `critical`, key `site_booking_refund_due:<id>`, `owner_user_id` and `apartment_id` NULL, so host pages never show it (they show `owner_user_id = $1 OR kind IN ('job_failed', 'turnstile_unavailable', 'ttlock_budget')`, go/internal/web/properties/lists.go:169) and the ops page lists it (go/internal/web/auth/opspage/data.go:437-440 counts every open alert). Resolved on success. A failed retry is not a job error, so no `job_failed` alert reaches hosts.
- **Guest sees nothing new:** the clash mail is still sent only after a refund went through; `refund_due` is not in `VisibleStatuses` (go/internal/web/booking/manage.go:26) or Python `VISIBLE`, as `pending`/`expired` were not.
- **No new outbound request:** the only call is the existing `POST /v1/refunds` on the connected account, made only when a `refund_due` row exists.
- **Python (go-first rule 1, parity plumbing):** `App/app/booking_site.py` gets `refund_due` in `STATUSES` and `_TRANSITIONS` only so the twin and pin tests agree; no Python code writes it. Rule 3 does not apply (not a filing, security or data-loss bug; Stripe is in test mode). Python still serves booking events until the owner sets `UBYHOST_GO_BOOKING_WEBHOOK=1` (brief 1554): owner step 1.
- **Golden test:** Python leaves bookings 5 and 7 `pending`; Go now parks them `refund_due`. The Go golden test patches exactly those two expected rows (step 8). Do not regenerate the golden file.

Excerpts (must be found verbatim; if not, STOP, §8):

`go/internal/payments/booking_webhook.go`, constants block:
```go
	bookingHoldDeleteSQL = `DELETE FROM booking_hold WHERE id = $1`
```
transition table:
```go
var bookingTransitions = map[string]map[string]bool{
	"pending":        {"paid": true, "expired": true, "clash_refunded": true},
	"requested":      {"paid": true, "expired": true, "cancelled": true},
	"paid":           {"cancelled": true, "refunded": true, "clash_refunded": true},
	"cancelled":      {"refunded": true},
	"expired":        {"paid": true, "clash_refunded": true, "cancelled": true},
	"refunded":       {},
	"clash_refunded": {},
}
```
`handle`:
```go
	if bk.status != "pending" && bk.status != "expired" {
		return nil // already handled
	}
	intent, _ := obj["payment_intent"].(string)
	return b.confirm(ctx, bk, intent)
}
```
`refundClash` head (the audit line and `return b.mailClash(ctx, bk)` after it stay as 1792 left them):
```go
// refundClash is _refund_clash: a full refund on the host's connected account.
// Any failure is returned, so the webhook answers 500 and Stripe retries.
func (b *BookingWebhook) refundClash(ctx context.Context, bk *siteBooking, intent string) error {
	account, err := b.Stripe.existingAccount(ctx, bk.ownerUserID)
	if err != nil {
		return err
	}
	if account == "" || intent == "" {
		return fmt.Errorf("site booking %d: cannot refund (no account or intent)", bk.id)
	}
	key, _, err := b.Stripe.guard(ctx)
	if err != nil {
		return err
	}
	form := url.Values{}
	form.Set("payment_intent", intent)
	form.Set("metadata[site_booking_id]", strconv.FormatInt(bk.id, 10))
	if err := b.refund(ctx, key, account, fmt.Sprintf("site_booking_clash_refund_%d", bk.id), form); err != nil {
		return err
	}
	if _, err := b.setStatus(ctx, bk.id, "clash_refunded", []bookingField{
		{"refunded_czk", bk.totalCZK}, {"stripe_payment_intent_id", intent},
	}); err != nil {
		return err
	}
```
and the comment line `// refund posts /v1/refunds on the connected account with an idempotency key.`

`go/internal/statemachine/tables.go` (lines 111-119), `App/app/booking_site.py` (line 26 `STATUSES = (...)` and lines 337-345 `_TRANSITIONS`), `go/internal/web/booking/site.go:50`, `go/cmd/ubyhost-web/register_jobs.go:35-38`, `App/tests/test_sm_site_booking.py` (lines 45, 68-73, 261-265), `go/internal/payments/booking_webhook_test.go` (`snap := bookingSnapshot(t, pool, g.Stamp)` and `func TestBookingDatesAndToken`): the "old" side of each diff in §4 is the excerpt.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/payments/booking_webhook.go | edit | SQL constants, table, `handle`, `refundClash`, new `tryRefund`, `parkRefundDue`, `RetryRefundDue` |
| go/internal/statemachine/tables.go | edit | `site_booking.status` twin |
| go/internal/web/booking/site.go | edit | `Statuses` twin of `STATUSES` |
| go/cmd/ubyhost-web/register_jobs.go | edit | `stripe_sweep` also calls `RetryRefundDue` |
| go/internal/payments/booking_webhook_test.go | edit | golden deviation for rows 5, 7; new `TestRetryRefundDue` |
| App/app/booking_site.py | edit | go-first rule 1: `refund_due` in `STATUSES` and `_TRANSITIONS` |
| App/tests/test_sm_site_booking.py | edit | Go-only moves and the new SQL anchor |
| docs/tasks/1793-report.md | create | report |

No other file may change.

## 4. Steps

### Step 1: SQL constants (booking_webhook.go)

```diff
 	bookingHoldDeleteSQL = `DELETE FROM booking_hold WHERE id = $1`
+	// Brief 1793: a clash refund that failed. A row already refund_due keeps
+	// its updated_at, the stamp of the first failure.
+	bookingRefundDueSQL = `UPDATE site_booking SET status = 'refund_due', stripe_payment_intent_id = $2,
+		updated_at = $1 WHERE id = $3 AND status IN ('pending', 'expired')`
+	bookingRefundDueListSQL = `SELECT ` + bookingColumns + `, COALESCE(stripe_payment_intent_id, '')
+		FROM site_booking WHERE status = 'refund_due' AND updated_at >= $1 ORDER BY id LIMIT 50`
+	refundAlertUpdateSQL = `UPDATE alert SET level = 'critical', message = $1, detail = $2, created_at = $3
+		WHERE dedupe_key = $4 AND resolved_at IS NULL`
+	refundAlertInsertSQL = `INSERT INTO alert (level, kind, dedupe_key, message, detail, created_at)
+		VALUES ('critical', 'site_booking_refund_due', $4, $1, $2, $3)`
+	refundAlertResolveSQL = `UPDATE alert SET resolved_at = $1 WHERE dedupe_key = $2 AND resolved_at IS NULL`
```

### Step 2: transition table (booking_webhook.go)

```diff
 var bookingTransitions = map[string]map[string]bool{
-	"pending":        {"paid": true, "expired": true, "clash_refunded": true},
+	"pending":        {"paid": true, "expired": true, "clash_refunded": true, "refund_due": true},
 	"requested":      {"paid": true, "expired": true, "cancelled": true},
 	"paid":           {"cancelled": true, "refunded": true, "clash_refunded": true},
 	"cancelled":      {"refunded": true},
-	"expired":        {"paid": true, "clash_refunded": true, "cancelled": true},
+	"expired":        {"paid": true, "clash_refunded": true, "cancelled": true, "refund_due": true},
 	"refunded":       {},
 	"clash_refunded": {},
+	"refund_due":     {"clash_refunded": true},
 }
```

### Step 3: `handle` (booking_webhook.go)

```diff
+	intent, _ := obj["payment_intent"].(string)
+	if bk.status == "refund_due" {
+		return b.refundClash(ctx, bk, intent) // a redelivery is a retry too (brief 1793)
+	}
 	if bk.status != "pending" && bk.status != "expired" {
 		return nil // already handled
 	}
-	intent, _ := obj["payment_intent"].(string)
 	return b.confirm(ctx, bk, intent)
 }
```

### Step 4: `refundClash` head (booking_webhook.go)

Replace the whole `refundClash` head excerpt of §2 (from its comment to the closing `}` of the `setStatus` call) with:

```go
// refundClash is _refund_clash: a full refund on the host's connected account.
// A failure parks the booking as refund_due (parkRefundDue) and is returned,
// so the webhook answers 500 and Stripe retries; RetryRefundDue retries daily
// too. Every try sends the same idempotency key (brief 1793).
func (b *BookingWebhook) refundClash(ctx context.Context, bk *siteBooking, intent string) error {
	if err := b.tryRefund(ctx, bk, intent); err != nil {
		if perr := b.parkRefundDue(ctx, bk, intent, err); perr != nil {
			return errors.Join(err, perr)
		}
		return err
	}
	changed, err := b.setStatus(ctx, bk.id, "clash_refunded", []bookingField{
		{"refunded_czk", bk.totalCZK}, {"stripe_payment_intent_id", intent},
	})
	if err != nil {
		return err
	}
	if !changed {
		return nil // a concurrent try recorded it, with its audit line and mails
	}
	if _, err := b.Pool.Exec(ctx, refundAlertResolveSQL, stampAt(b.Now()), refundAlertKey(bk.id)); err != nil {
		return err
	}
```

The lines after it (`if err := audit(ctx, b.Pool, ... "site_booking_clash_refunded", ...` and `return b.mailClash(ctx, bk)` and `}`) stay unchanged.

### Step 5: new functions (booking_webhook.go)

Insert directly above the line `// refund posts /v1/refunds on the connected account with an idempotency key.`:

```go
// refundDueDays is how long RetryRefundDue keeps trying, counted from the
// first failure (updated_at). Run daily by stripe_sweep: at most 14 tries.
const refundDueDays = 14

func refundAlertKey(id int64) string {
	return fmt.Sprintf("site_booking_refund_due:%d", id)
}

// tryRefund posts the clash refund. Stripe keeps an idempotency key for 24 h;
// a later try on a charge an earlier try already refunded answers
// charge_already_refunded, which counts as done.
func (b *BookingWebhook) tryRefund(ctx context.Context, bk *siteBooking, intent string) error {
	account, err := b.Stripe.existingAccount(ctx, bk.ownerUserID)
	if err != nil {
		return err
	}
	if account == "" || intent == "" {
		return fmt.Errorf("site booking %d: cannot refund (no account or intent)", bk.id)
	}
	key, _, err := b.Stripe.guard(ctx)
	if err != nil {
		return err
	}
	form := url.Values{}
	form.Set("payment_intent", intent)
	form.Set("metadata[site_booking_id]", strconv.FormatInt(bk.id, 10))
	err = b.refund(ctx, key, account, fmt.Sprintf("site_booking_clash_refund_%d", bk.id), form)
	if err != nil && strings.Contains(err.Error(), "(charge_already_refunded)") {
		return nil
	}
	return err
}

// parkRefundDue moves a pending or expired booking to refund_due with the
// event's intent and opens (or refreshes) the operator-only alert. The alert
// has no owner and no apartment, so host pages do not show it.
func (b *BookingWebhook) parkRefundDue(ctx context.Context, bk *siteBooking, intent string, cause error) error {
	stamp := stampAt(b.Now())
	var pi *string
	if intent != "" {
		pi = &intent
	}
	if _, err := b.Pool.Exec(ctx, bookingRefundDueSQL, stamp, pi, bk.id); err != nil {
		return err
	}
	detail := []rune(cause.Error())
	if len(detail) > 300 {
		detail = detail[:300]
	}
	message := fmt.Sprintf("Clash refund failed for site booking %d (%d CZK). Retried daily for %d days; refund it by hand in Stripe if this stays open.",
		bk.id, bk.totalCZK, refundDueDays)
	key := refundAlertKey(bk.id)
	tag, err := b.Pool.Exec(ctx, refundAlertUpdateSQL, message, string(detail), stamp, key)
	if err != nil {
		return err
	}
	if tag.RowsAffected() > 0 {
		return nil
	}
	_, err = b.Pool.Exec(ctx, refundAlertInsertSQL, message, string(detail), stamp, key)
	return err
}

// RetryRefundDue retries the clash refund of each refund_due booking younger
// than refundDueDays (brief 1793). A failed try is logged and keeps the row
// refund_due with its alert; it is not an error of the job. It returns the
// number of bookings refunded.
func (b *BookingWebhook) RetryRefundDue(ctx context.Context) (int, error) {
	cutoff := stampAt(b.Now().AddDate(0, 0, -refundDueDays))
	rows, err := b.Pool.Query(ctx, bookingRefundDueListSQL, cutoff)
	if err != nil {
		return 0, err
	}
	type due struct {
		bk     siteBooking
		intent string
	}
	var list []due
	for rows.Next() {
		var d due
		bk := &d.bk
		if err := rows.Scan(&bk.id, &bk.apartmentID, &bk.ownerUserID, &bk.holdID,
			&bk.status, &bk.dateFrom, &bk.dateTo, &bk.guests, &bk.guestName, &bk.guestEmail, &bk.totalCZK,
			&bk.lang, &bk.policy, &bk.payMethod, &d.intent); err != nil {
			rows.Close()
			return 0, err
		}
		list = append(list, d)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	done := 0
	for i := range list {
		if err := b.refundClash(ctx, &list[i].bk, list[i].intent); err != nil {
			log.Printf("site booking %d: clash refund retry failed: %v", list[i].bk.id, err)
			continue
		}
		done++
	}
	return done, nil
}

```

`errors`, `log`, `strings`, `strconv`, `url`, `fmt` are already imported.

### Step 6: twins

`go/internal/statemachine/tables.go`:
```diff
 	"site_booking.status": {
 		"cancelled":      {"refunded"},
 		"clash_refunded": {},
-		"expired":        {"cancelled", "clash_refunded", "paid"},
+		"expired":        {"cancelled", "clash_refunded", "paid", "refund_due"},
 		"paid":           {"cancelled", "clash_refunded", "refunded"},
-		"pending":        {"clash_refunded", "expired", "paid"},
+		"pending":        {"clash_refunded", "expired", "paid", "refund_due"},
+		"refund_due":     {"clash_refunded"},
 		"refunded":       {},
 		"requested":      {"cancelled", "expired", "paid"},
 	},
```

`go/internal/web/booking/site.go:50`:
```diff
-	Statuses   = []string{"pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded"}
+	Statuses   = []string{"pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded", "refund_due"}
```

`App/app/booking_site.py` line 26:
```diff
-STATUSES = ("pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded")
+STATUSES = ("pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded",
+            "refund_due")
```
and `_TRANSITIONS`:
```diff
 _TRANSITIONS = {
-    "pending": {"paid", "expired", "clash_refunded"},
+    "pending": {"paid", "expired", "clash_refunded", "refund_due"},
     "requested": {"paid", "expired", "cancelled"},
     "paid": {"cancelled", "refunded", "clash_refunded"},
     "cancelled": {"refunded"},
-    "expired": {"paid", "clash_refunded", "cancelled"},
+    "expired": {"paid", "clash_refunded", "cancelled", "refund_due"},
     "refunded": set(),
     "clash_refunded": set(),
+    # Go only (brief 1793): a clash refund that failed, retried by stripe_sweep.
+    "refund_due": {"clash_refunded"},
 }
```

### Step 7: pin test (App/tests/test_sm_site_booking.py)

```diff
 UNUSED_TABLE_MOVES = {("paid", "refunded"), ("paid", "clash_refunded")}
+
+# 3c. Moves only Go makes (brief 1793): booking_webhook.go parks a failed clash
+#     refund as refund_due (bookingRefundDueSQL); a retry ends in clash_refunded.
+PINNED_GO_MOVES = {("pending", "refund_due"), ("expired", "refund_due"), ("refund_due", "clash_refunded")}
```
```diff
 PINNED_GO_STATUS_ANCHORS = [
     "UPDATE site_booking SET status = 'paid'",
+    "UPDATE site_booking SET status = 'refund_due'",
     "UPDATE site_booking SET status = $1",
```
```diff
     used = {(frm, to) for _f, froms, to in PINNED_SQL + PINNED_CALLS for frm in froms}
     table = {(frm, to) for frm, tos in booking_site._TRANSITIONS.items() for to in tos}
+    assert PINNED_GO_MOVES <= table
+    used |= PINNED_GO_MOVES
     assert table - used == UNUSED_TABLE_MOVES
```

### Step 8: Go tests (booking_webhook_test.go)

Golden deviation, in `TestBookingWebhookMatchesPython`:
```diff
 	snap := bookingSnapshot(t, pool, g.Stamp)
+	// Brief 1793: Go parks a failed clash refund as refund_due with the event's
+	// intent; Python leaves it pending. Only bookings 5 and 7 differ.
+	for _, row := range g.After["site_booking"].([]any) {
+		m := row.(map[string]any)
+		switch fmt.Sprint(m["id"]) {
+		case "5":
+			m["status"], m["stripe_payment_intent_id"], m["updated_at"] = "refund_due", "pi_5", "run"
+		case "7":
+			m["status"], m["updated_at"] = "refund_due", "run"
+		}
+	}
 	for key, want := range g.After {
```

New test, inserted directly above `func TestBookingDatesAndToken(t *testing.T) {`:
```go
// TestRetryRefundDue: a failed clash refund parks the booking as refund_due
// with an operator alert; the retry refunds it with the same idempotency key
// and resolves the alert. A booking that cannot be refunded stays parked.
func TestRetryRefundDue(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stripe, srv := newFakeStripe(t)
	bw := NewBookingWebhook(pool, bookingEnv(g, nil), func() time.Time { return testNow })
	bw.Stripe.APIBase = srv.URL
	ctx := context.Background()
	for _, raw := range []string{
		`{"id":"evt_rd5","type":"checkout.session.completed","data":{"object":{"id":"cs_5","payment_status":"paid","payment_intent":"pi_5","metadata":{"site_booking_id":"5"}}}}`,
		`{"id":"evt_rd6","type":"checkout.session.completed","data":{"object":{"id":"cs_6","payment_status":"paid","payment_intent":"pi_fail","metadata":{"site_booking_id":"6"}}}}`,
	} {
		var ev stripeEvent
		if err := json.Unmarshal([]byte(raw), &ev); err != nil {
			t.Fatal(err)
		}
		if err := bw.Process(ctx, ev, "test"); err == nil {
			t.Fatalf("%s: want the refund to fail", ev.ID)
		}
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id IN (5, 6) AND status = 'refund_due'`); n != 2 {
		t.Fatalf("%d bookings refund_due, want 2", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM alert WHERE kind = 'site_booking_refund_due' AND level = 'critical'
		AND owner_user_id IS NULL AND apartment_id IS NULL AND resolved_at IS NULL`); n != 2 {
		t.Fatalf("%d open refund alerts, want 2", n)
	}
	n, err := bw.RetryRefundDue(ctx)
	if err != nil || n != 1 {
		t.Fatalf("retry: got %d, %v; want 1, nil", n, err)
	}
	if c := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 6 AND status = 'clash_refunded'
		AND refunded_czk = total_czk AND stripe_payment_intent_id = 'pi_fail'`); c != 1 {
		t.Errorf("booking 6 not clash_refunded")
	}
	if c := count(t, pool, `SELECT COUNT(*) FROM alert WHERE dedupe_key = 'site_booking_refund_due:6' AND resolved_at IS NOT NULL`); c != 1 {
		t.Errorf("alert for booking 6 not resolved")
	}
	if c := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 5 AND status = 'refund_due'`); c != 1 {
		t.Errorf("booking 5 left refund_due")
	}
	if c := count(t, pool, `SELECT COUNT(*) FROM alert WHERE dedupe_key = 'site_booking_refund_due:5' AND resolved_at IS NULL`); c != 1 {
		t.Errorf("alert for booking 5 not open")
	}
	stripe.mu.Lock()
	keys := 0
	for _, c := range stripe.calls {
		if c["idempotency_key"] == "site_booking_clash_refund_6" {
			keys++
		}
	}
	calls := len(stripe.calls)
	stripe.mu.Unlock()
	if keys != 2 || calls != 2 {
		t.Errorf("stripe calls %d (key 6: %d), want 2 and 2", calls, keys)
	}
	if n, err := bw.RetryRefundDue(ctx); err != nil || n != 0 {
		t.Errorf("second retry: got %d, %v; want 0, nil", n, err)
	}
	stripe.mu.Lock()
	defer stripe.mu.Unlock()
	if len(stripe.calls) != 2 {
		t.Errorf("second retry called Stripe")
	}
}

```

### Step 9: job wiring (register_jobs.go)

```diff
 		"stripe_sweep": func(ctx context.Context) (int, error) {
 			expired, deleted, err := payments.Sweep(ctx, pool, time.Now().UTC(), jobs.Now(0))
-			return expired + deleted, err
+			if err != nil {
+				return expired + deleted, err
+			}
+			// Brief 1793: retry failed clash refunds (refund_due), once a day.
+			refunded, err := payments.NewBookingWebhook(pool, os.Getenv, time.Now).RetryRefundDue(ctx)
+			return expired + deleted + refunded, err
 		},
```

### Step 10: format, build, test (§6), then write the report.

## 5. Do not touch

- `go/internal/payments/sweep.go`, `webhook.go`, `onboarder.go`, `confirm` and `mailClash`/`mailConfirmed` in booking_webhook.go (1792's area), the audit line and `return b.mailClash(ctx, bk)` at the end of `refundClash`.
- `go/internal/payments/testdata/booking_webhook/golden.json` and `App/scripts/booking_webhook_golden.py`: do not regenerate.
- `App/app/booking_webhook.py` and any other Python behaviour; `go/internal/scheduler/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/register_filing.go`.
- No migration, no new dependency, no new job kind, no env var. Never push to `main`; no merge.

## 6. Commands

From the repo root:

```bash
cd go && gofmt -l ./internal/payments ./internal/statemachine ./internal/web/booking ./cmd/ubyhost-web 2>&1 | tail -30
```
Expected: no output (if files are listed, run `gofmt -w` on them once, then re-run).

```bash
cd go && go vet ./internal/payments/ ./internal/statemachine/ ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -30
```
Expected: no output.

```bash
cd go && go test -count=1 ./internal/statemachine/ ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -30
```
Expected: `ok` lines only.

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres go test -count=1 ./internal/payments/ -run 'Booking|RetryRefundDue|Sweep|Webhook' -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```
Expected: `--- PASS` for `TestBookingWebhookMatchesPython`, `TestBookingSwitchOnHandlesInGo`, `TestRetryRefundDue`, then `ok`. Without a local Postgres these tests skip: say so in the report; CI runs them.

From `App/` (test-map row "State/status columns, transitions", plus "Booking site"):

```bash
.venv/bin/python -m pytest tests/test_sm_site_booking.py tests/test_sm_go_parity.py tests/test_sm_registry.py tests/test_booking_site.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30
```
Expected: all passed.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`, expected no errors.

## 7. Acceptance

- [ ] `grep -c 'refund_due' go/internal/payments/booking_webhook.go` is at least 8.
- [ ] `grep -n '"refund_due":' go/internal/statemachine/tables.go App/app/booking_site.py go/internal/payments/booking_webhook.go` shows one line per file.
- [ ] `grep -n 'RetryRefundDue' go/cmd/ubyhost-web/register_jobs.go` shows one line.
- [ ] `git diff --stat` lists only the §3 files; `git diff --name-only | grep -c migrations` is 0.
- [ ] gofmt and go vet print nothing; the Go and pytest commands in §6 pass (or the Postgres tests are reported as skipped).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (1792 changed `handle` or the `refundClash` head: report what you found, do not merge the two by hand);
- `TestBookingWebhookMatchesPython` fails on anything other than rows 5 and 7 of `site_booking`;
- a test fails twice;
- a test elsewhere pins the list of alert kinds and fails on `site_booking_refund_due`;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, migration, job kind or env var seems needed;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1793-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- go/internal/payments/booking_webhook.go: `refundClash` (`!changed` early return; alert resolve), `tryRefund` (`charge_already_refunded` as success), `bookingRefundDueSQL` (atomic `status IN ('pending', 'expired')`).
- go/internal/payments/booking_webhook_test.go: the golden deviation touches rows 5 and 7 only.
- App/tests/test_sm_site_booking.py: `PINNED_GO_MOVES` cannot hide an unpinned Python move.
- PR text must say: outbound request unchanged (existing `POST /v1/refunds`, now also from `stripe_sweep` when a `refund_due` row exists).

## Owner steps

1. The fix works only where Go handles booking events. To turn it on (Stripe is in test mode): on the server, open `.env`, set `UBYHOST_GO_BOOKING_WEBHOOK=1`, save, then restart the Go service as in brief 1554 (`docs/tasks/1554-go-booking-webhook-cutover.md`, owner steps).
2. After a clash with a failed refund, the ops page shows an open `site_booking_refund_due` alert (level critical). The daily job stops retrying 14 days after the first failure. If the alert is still open then: (a) open the Stripe dashboard, switch to the host's connected account, find the payment by the booking id in the metadata, click Refund, refund the full amount; (b) the alert then stays open as a record; ask for a follow-up brief if you want a "mark refunded by hand" button. The booking stays `refund_due` in the database.
