# 1792: Booking "paid" audit and confirmation mail in the same transaction

Status: todo
Depends on: 1791 (key/mode guard; also edits booking_webhook.go, so land it first). 1793 (refund_due) depends on this brief | Base commit: <sha after 1791 merges> | Branch: task/1792-booking-paid-mail-same-tx
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

In the Go booking webhook, write the "paid" audit line and the confirmation mail rows (`email_outbox`) inside the same transaction that marks the booking paid. Today they run after `Commit`, so a failure there leaves the booking `paid`, the Stripe retry sees `paid` and skips, and the guest never gets the mail.

## 2. Context

Plan: docs/plans/ai-payments-hardening.md, P1 item 2 (plan says `booking_webhook.go:322-340`; real lines before 1791 are 316-340, same code, no discrepancy beyond line drift). Line numbers move after 1791: match by text.

**No new queue job and no migration.** The repo's durable mail queue is already the `email_outbox` table (`ubyport.EnqueueMail`; Python owns the sender job, docs/context/status.md: "Python: mail"). `mailConfirmed` already only inserts outbox rows; the fault is that it runs on `b.Pool` after `tx.Commit`. The fix is to run it on `tx`. `email_outbox.idempotency_key` is UNIQUE (App/migrations_pg/00001_baseline.sql:2469), keys are `site_booking:<id>:confirmed` and `site_booking:<id>:host_new`.

**Secrets (rules.md#mail, CLAIM_SECRET_MARKER).** The `secret` passed to `mailConfirmed` is the server key from `secure.LoadSecret` (not a guest secret). `manageURL` HMACs `site_booking:<id>` with it to make a 40-hex manage-link token, and the link is written into the guest mail body text in the outbox in clear. That is how Python does it and the golden test pins it. It is NOT a `ClaimSecretMarker` case (that marker, go/internal/mail/outbox_markers.go, needs a `claim_secret_enc` payload key and send-time decrypt in the Python mail job). This brief keeps the behaviour and does not change it. The key itself is never stored. Open owner question in section 9.

Current code, go/internal/payments/booking_webhook.go (after the hold delete):
```go
	if err := tx.Commit(ctx); err != nil {
		return err
	}
	if clash {
		return b.refundClash(ctx, bk, intent)
	}
	if err := audit(ctx, b.Pool, stampAt(b.Now()), "site_booking_paid",
		fmt.Sprintf("id=%d reservation=%d", bk.id, reservationID), bk.ownerUserID); err != nil {
		return err
	}
	fresh, err := b.booking(ctx, bookingByIDSQL, bk.id)
	if err != nil {
		return err
	}
	if fresh == nil {
		fresh = bk
	}
	// booking_invoice.ensure is not ported (known gap, see the file comment).
	return b.mailConfirmed(ctx, fresh, reservationID, secret)
```
Signatures today:
```go
func (b *BookingWebhook) mailConfirmed(ctx context.Context, bk *siteBooking, reservationID int64, secret string) error {
func (b *BookingWebhook) enqueue(ctx context.Context, kind, key, to, subject, payload, replyTo string,
	guestKind bool, reservationID *int64, bk *siteBooking) {
```
`audit(ctx, q dbtx, ...)` (webhook.go:444) already accepts a tx. `ubyport.EnqueueMail` (go/internal/ubyport/notify.go:326) takes `*pgxpool.Pool` and does SELECT, then INSERT, then handles a 23505 race by re-SELECT; that last step cannot work inside a transaction (an error aborts it), so the tx variant uses ON CONFLICT.

The helper reads in `mailConfirmed` (`b.apartment`, `hostEmail`, `linkKey`, `manageURL`) use `b.Pool` and only read committed data; they stay as they are. The `fresh` re-read is dropped: the mail uses no field the paid update changes, so the `bk` already loaded is used (state this in the report).

`mailClash` also calls `b.enqueue` (clash path, refund; that is 1793's area). It must behave exactly as now: pool, failure logged, not returned.

Retry behaviour after this change: the paid update, audit and mail rows commit or roll back together. A rolled-back attempt leaves the booking `pending`, so the retry redoes everything. A committed one always has its mail rows. A redelivery of a committed event hits `live != "pending"` and returns nil, and the idempotency keys stop any duplicate rows.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/ubyport/notify.go | edit | add `MailQuerier` and `EnqueueMailTx` (do not change `EnqueueMail`) |
| go/internal/payments/booking_webhook.go | edit | move audit and mail into the tx; `enqueue` takes a querier and returns error |
| go/internal/payments/booking_webhook_test.go | edit | add `TestBookingPaidMailSameTx` |

No other file may change.

## 4. Steps

1. In go/internal/ubyport/notify.go, directly after the `EnqueueMail` function (ends `return 0, errNotifyMail\n}` before the `// QueuePush` comment), add:
```go
// MailQuerier is what EnqueueMailTx needs; pgx.Tx and *pgxpool.Pool both fit.
type MailQuerier interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// EnqueueMailTx is EnqueueMail for use inside a transaction: the insert is
// ON CONFLICT DO NOTHING, so a duplicate key never aborts the caller's tx.
// An existing key returns the existing row id.
func EnqueueMailTx(ctx context.Context, q MailQuerier, m OutboxMail) (int64, error) {
	var ccParam *string
	if m.CC != "" {
		cc := m.CC
		ccParam = &cc
	}
	ts := UTCNow()
	var id int64
	err := q.QueryRow(ctx,
		`INSERT INTO email_outbox (idempotency_key, kind, reservation_id, apartment_id, owner_user_id,
		   to_email, cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'queued', 0, $10, $10, $10)
		 ON CONFLICT (idempotency_key) DO NOTHING
		 RETURNING id`,
		m.Key, m.Kind, m.ReservationID, m.ApartmentID, m.OwnerUserID, m.To,
		ccParam, cutRunes(m.Subject, mailSubjectMax), m.payloadJSON(), ts,
	).Scan(&id)
	if err == nil {
		return id, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return 0, errNotifyMail
	}
	if err := q.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, m.Key).Scan(&id); err != nil {
		return 0, errNotifyMail
	}
	return id, nil
}
```
2. In go/internal/payments/booking_webhook.go replace the block quoted in section 2 (from `if err := tx.Commit(ctx); err != nil {` to `return b.mailConfirmed(ctx, fresh, reservationID, secret)`) with:
```go
	if !clash {
		// Audit and mail rows commit with the paid update, or not at all, so a
		// Stripe retry can never find a paid booking without its mail.
		if err := audit(ctx, tx, stampAt(b.Now()), "site_booking_paid",
			fmt.Sprintf("id=%d reservation=%d", bk.id, reservationID), bk.ownerUserID); err != nil {
			return err
		}
		// booking_invoice.ensure is not ported (known gap, see the file comment).
		if err := b.mailConfirmed(ctx, tx, bk, reservationID, secret); err != nil {
			return err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return err
	}
	if clash {
		return b.refundClash(ctx, bk, intent)
	}
	return nil
```
3. Change the `mailConfirmed` signature to `func (b *BookingWebhook) mailConfirmed(ctx context.Context, q ubyport.MailQuerier, bk *siteBooking, reservationID int64, secret string) error {`. In its body replace the two `b.enqueue(ctx, "site_booking_confirmed", ...` and `b.enqueue(ctx, "site_booking_host", ...` calls (the ones inside `mailConfirmed`, with `host_new` key) by `if err := b.enqueue(ctx, q, "site_booking_confirmed", ...); err != nil { return err }` (same remaining arguments, only `q,` inserted after `ctx,`). Same for the host one.
4. Change `enqueue` to `func (b *BookingWebhook) enqueue(ctx context.Context, q ubyport.MailQuerier, kind, key, to, subject, payload, replyTo string, guestKind bool, reservationID *int64, bk *siteBooking) error {`. Inside: the three early `return` lines become `return nil`; replace `ubyport.EnqueueMail(ctx, b.Pool, ubyport.OutboxMail{` with `ubyport.EnqueueMailTx(ctx, q, ubyport.OutboxMail{`; the final failure branch becomes `log.Printf("mail enqueue failed kind=%s key=%s", kind, key)` then `return err`; add `return nil` at the end. Change the `_, err :=` form so `err` is declared: `if _, err := ...; err != nil {`.
5. In `mailClash` change its four `b.enqueue(ctx, "...` calls to `b.enqueue(ctx, b.Pool, "...` (insert `b.Pool,` after `ctx,`). Their results stay ignored (a failure is still only logged, as now).
6. Append to go/internal/payments/booking_webhook_test.go, reusing the helpers there (`loadBookingGolden`, `testPool`, `seedBookingGolden`, `bookingPost`, `count`; mail is on via `bookingEnv`, which sets `UBYHOST_MAIL_BACKEND=console`):
```go
func TestBookingPaidMailSameTx(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	on := map[string]string{BookingSwitchEnv: "1"}
	paid := []byte(`{"id":"evt_tx_1","type":"checkout.session.completed","data":{"object":{"id":"cs_1","payment_status":"paid","payment_intent":"pi_1","metadata":{"site_booking_id":"1"}}}}`)

	// The mail table is broken: the whole event rolls back, booking stays pending.
	if _, err := pool.Exec(context.Background(), `ALTER TABLE email_outbox RENAME TO email_outbox_off`); err != nil {
		t.Fatal(err)
	}
	if code, _ := bookingPost(t, pool, g, on, paid); code != http.StatusInternalServerError {
		t.Fatalf("mail insert fails: got %d, want 500", code)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'pending'`); n != 1 {
		t.Errorf("booking left pending expected, paid despite mail failure")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_paid'`); n != 0 {
		t.Errorf("audit line written outside the rolled-back tx")
	}

	// Table back: the retry pays the booking and queues both mails once.
	if _, err := pool.Exec(context.Background(), `ALTER TABLE email_outbox_off RENAME TO email_outbox`); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ { // second post is the redelivery
		if code, out := bookingPost(t, pool, g, on, paid); code != 200 || out != "ok" {
			t.Fatalf("post %d: got %d %q", i, code, out)
		}
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'paid'`); n != 1 {
		t.Errorf("booking 1 not paid")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:1:confirmed'`); n != 1 {
		t.Errorf("guest confirmation rows: %d, want 1", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_paid'`); n != 1 {
		t.Errorf("paid audit rows: %d, want 1", n)
	}
}
```
If `context` is not imported in the test file add it. If booking 1's golden seed has no guest email (no `site_booking:1:confirmed` row in the existing golden snapshot), STOP (section 8).

## 5. Do not touch

- `EnqueueMail`, `refundClash`, `setStatus`, the clash path, the Stripe key/mode guard from 1791, the refund_due work of 1793.
- Python files, App/, migrations (none needed).
- Hard rules: 1 (UbyPort untouched), 3 (no secrets in code or tests), 4 (no dependency), 5 (SQL only in these Go paths, Postgres-portable; the new SQL is plain `ON CONFLICT`), 11 (Go only).
- No new personal-data field: the outbox rows are the same as before (App/app/retention.py needs no line).

## 6. Commands

From the repo root (the test-map has no Go row; Go tests need `UBYHOST_TEST_DATABASE_URL`, otherwise they skip and that is a failure for this brief):
```
cd go && go build ./... 2>&1 | tail -30
cd go && go vet ./internal/payments/ ./internal/ubyport/ 2>&1 | tail -30
cd go && go test ./internal/payments/ -run 'Booking' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/ubyport/ -count=1 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: build and vet silent; payments `TestBookingWebhookMatchesPython`, `TestBookingPaidMailSameTx` and the concurrency tests PASS with 0 SKIP; ubyport `ok`; lint clean.

## 7. Acceptance

- [ ] `grep -n 'audit(ctx, b.Pool' go/internal/payments/booking_webhook.go` shows no "site_booking_paid" line (audit now uses `tx`).
- [ ] `grep -n 'mailConfirmed(ctx, tx' go/internal/payments/booking_webhook.go` matches once, before `tx.Commit`.
- [ ] `TestBookingPaidMailSameTx` passes with 0 skipped (`-v` output shows `--- PASS`).
- [ ] `TestBookingWebhookMatchesPython` still passes unchanged (golden: same rows and mails).
- [ ] The `-run Booking` tests show 0 `SKIP`.
- [ ] `git diff --stat` lists only the three files in section 3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (after 1791 lands, small drift is expected: match by text, but if the structure differs, stop);
- a test fails twice, or the golden test needs its fixture changed;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- `UBYHOST_TEST_DATABASE_URL` is not set so the tests skip;
- booking 1 in the seed has no guest email so the confirmation row is not created;
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1792-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations (include: the `fresh` re-read was dropped and `bk` used).
5. Questions: owner decision wanted. The guest mail body stores the manage link with its HMAC token in clear in `email_outbox` (Python parity). Should a later brief move it to a send-time marker like `ClaimSecretMarker`? That needs a change in the Python mail job.
6. Owner steps left.

## Risk list (for the reviewer)

- go/internal/payments/booking_webhook.go: the tx block, `enqueue` error return, `mailClash` still logging only.
- go/internal/ubyport/notify.go: `EnqueueMailTx` SQL (same columns as `EnqueueMail`).

## Owner steps

1. Review and merge only with `scripts/merge-pr-on-green.sh <pr>`, after 1791 is merged. Then 1793 can start.
