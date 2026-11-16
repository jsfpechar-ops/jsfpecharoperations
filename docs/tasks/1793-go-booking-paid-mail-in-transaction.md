# 1793: Booking "paid" and its confirmation mail commit together (Go webhook)

Status: todo
Depends on: none | Base commit: a6c1990 | Branch: task/1793-go-booking-paid-mail-in-transaction
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (money path; Opus or the owner reviews the diff)

## 1. Objective

In `confirm` the audit line and the confirmation mails are written after the "paid" commit. If one fails, Stripe retries, the retry sees `paid` and returns "already handled": the guest has paid and never gets the mail or the manage link. Write the audit line and both mails inside the same transaction as the status change, so they commit with "paid" or not at all.

## 2. Context

Source: [ai-payments-hardening](../plans/ai-payments-hardening.md), P1 item 2. Hard rules (AGENTS.md): 1 filing correctness first (this brief does not touch filing); 2 privacy (no new personal-data field, no new outbound request); 3 no secrets or real data; 4 no new dependency; 5 SQL only through existing helpers and constants, Postgres-portable; 11 Go first.

**Design chosen: enqueue inside the transaction.** The outbox write is one INSERT into `email_outbox`; the only reason it cannot join the transaction is that `ubyport.EnqueueMail` takes a `*pgxpool.Pool`. It only calls `QueryRow`, so widening the parameter to a one-method interface lets a `pgx.Tx` pass. The fallback (check on retry whether the mail exists) is not needed. The mail reads (apartment, host contact, link key, page slug) are plain SELECTs and also run on the transaction.

**Python twin:** `App/app/booking_webhook.py` is still the live path for booking events today. `docs/ENVIRONMENT.md` says Go forwards events with `site_booking_id` to Python (`UBYHOST_PY_WEBHOOK_URL`) unless `UBYHOST_GO_BOOKING_WEBHOOK=1`, and `/webhooks/stripe` is not on `UBYHOST_GO_PATHS`. So this fix reaches production only once the owner switches the Go booking webhook on. Python is not changed here ([go-first](../context/go-first.md): not one of the three allowed exceptions). The owner decides the Python side (see Owner steps).

Excerpts (anchors; if one is not found verbatim, STOP, §8).

`go/internal/payments/booking_webhook.go`, end of `confirm`:
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
}
```

`go/internal/ubyport/notify.go`: `func EnqueueMail(ctx context.Context, pool *pgxpool.Pool, m OutboxMail) (int64, error) {` (body uses only `pool.QueryRow`).

`booking_webhook.go`: `enqueue` logs and swallows an error (`log.Printf("mail enqueue failed kind=%s key=%s", kind, key)`). `apartment`, `hostEmail`, `linkKey`, `manageURL`, `booking` read through `b.Pool`. `dbtx` (in `webhook.go`) already has `Exec` and `QueryRow`, and `audit` already takes a `dbtx`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ubyport/notify.go` | edit | `EnqueueMail` takes a `MailDB` interface instead of `*pgxpool.Pool` |
| `go/internal/payments/booking_webhook.go` | edit | `confirm` writes audit and mails on `tx` before commit; helpers take a `dbtx`; `enqueue` returns its error |
| `go/internal/payments/booking_webhook_test.go` | edit | add two test cases |
| `docs/tasks/1793-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

1. `notify.go`: above `EnqueueMail` add
   ```go
   // MailDB is the part of pgxpool.Pool and pgx.Tx that EnqueueMail uses.
   type MailDB interface {
   	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
   }
   ```
   and change the signature to `func EnqueueMail(ctx context.Context, q MailDB, m OutboxMail) (int64, error)`; rename `pool` to `q` in its body. Do not change any caller (a `*pgxpool.Pool` still satisfies it). Run `cd go && go build ./... 2>&1 | tail -30`: expect no output.
2. `booking_webhook.go`: add a first parameter `q dbtx` (after `ctx`) to `apartment`, `hostEmail`, `linkKey`, `manageURL`, `booking` and `enqueue`, and `mailConfirmed`, `mailClash`; inside each, use `q` instead of `b.Pool` for the reads and the enqueue call (`ubyport.EnqueueMail(ctx, q, ...)`). Update every caller: `handle` and `expire` and any other `b.booking(...)` call pass `b.Pool`; `mailClash` and `refundClash` pass `b.Pool`.
3. `enqueue` now returns `error`. Mail off or an address that does not normalise still returns nil (queue nothing). On an `EnqueueMail` error return it wrapped: `fmt.Errorf("enqueue %s: %w", kind, err)`. Do not log the address or key text beyond `kind`.
4. `mailClash` (refund path, out of scope for behaviour): keep today's behaviour by logging instead of returning: `if err := b.enqueue(ctx, b.Pool, ...); err != nil { log.Printf("%v", err) }` at its two call sites.
5. `mailConfirmed`: return the error from both `enqueue` calls (`if err := b.enqueue(...); err != nil { return err }`).
6. `confirm`: replace everything from `if err := tx.Commit(ctx)` to the end of the function with: first `if !clash { ... }` doing, on `tx`: `audit(ctx, tx, stampAt(b.Now()), "site_booking_paid", fmt.Sprintf("id=%d reservation=%d", bk.id, reservationID), bk.ownerUserID)`; then `fresh, err := b.booking(ctx, tx, bookingByIDSQL, bk.id)` (fall back to `bk` when nil); then `b.mailConfirmed(ctx, tx, fresh, reservationID, secret)`. Any error returns (the deferred `tx.Rollback` undoes "paid"). Place this block after the hold delete and before `tx.Commit`. After `tx.Commit` keep only `if clash { return b.refundClash(ctx, bk, intent) }` and `return nil`. Keep the `booking_invoice.ensure` comment.
7. Tests in `booking_webhook_test.go` (reuse `loadBookingGolden`, `seedBookingGolden`, `goldenBookingWebhook`, `newFakeStripe`, `bookingEvent`, `testPool`, `count`):
   - `TestBookingMailEnqueueFailsLeavesNotPaid`: seed; `ALTER TABLE email_outbox ADD CONSTRAINT t_no_confirm CHECK (kind <> 'site_booking_confirmed')`; `Process` a `checkout.session.completed` for the golden pending booking; want an error, then counts: booking still `pending` (not `paid`), no `reservation` with uid `site-<id>`, no `audit` row `site_booking_paid`, no `email_outbox` row for the booking.
   - `TestBookingRetryAfterPartialFailureOneMail`: same failing first delivery; `ALTER TABLE email_outbox DROP CONSTRAINT t_no_confirm`; `Process` the same event twice; want no error, booking `paid`, exactly one `site_booking:<id>:confirmed` row, exactly one `site_booking:<id>:host_new` row, exactly one `site_booking_paid` audit row, exactly one reservation.
   Use the same booking and session ids as the existing `TestBookingSurvivesCancelAfterCommit` (booking 1, session `cs_1`, intent `pi_1`; check its SQL strings).
8. Run the commands of §6.

## 5. Do not touch

`App/` (no Python change, rule 11), `App/migrations_pg/` (no schema change: `email_outbox` and its unique `idempotency_key` already exist), `go.mod`/`go.sum` (no dependency), `refundClash` and the clash flow (that is P1 item 3), `ubyport` filing code and every other file in `ubyport` except the one signature in `notify.go`, `webhook.go`, `i18n` files. SQL only through the existing constants and `ubyport.EnqueueMail`; the only new SQL is inside the tests.

## 6. Commands

From `go/` with `UBYHOST_TEST_DATABASE_URL` set (the Go tests skip without it; 0 skipped is required):

- `go build ./... 2>&1 | tail -30` expect no output.
- `go test ./internal/payments/ -run 'Booking' -count=1 -v 2>&1 | tail -30` expect PASS for all, including the two new tests and `TestBookingWebhookMatchesPython`, `TestBookingSurvivesCancelAfterCommit`, `TestBookingConcurrentPaidEvents`, no SKIP.
- `go test ./internal/payments/ ./internal/ubyport/ ./internal/mailnotify/ -count=1 2>&1 | tail -30` expect ok for each (the other test-map rows are Python; this is the Go row for the changed packages).
- `go vet ./internal/payments/ ./internal/ubyport/ 2>&1 | tail -30` expect no output.

## 7. Acceptance

- [ ] `grep -n 'audit(ctx, b.Pool' go/internal/payments/booking_webhook.go | tail -5` shows no `site_booking_paid` line.
- [ ] In `confirm`, the `site_booking_paid` audit, the `booking(` re-read and `mailConfirmed` all appear above `tx.Commit` (`grep -n 'tx.Commit\|mailConfirmed\|site_booking_paid' go/internal/payments/booking_webhook.go | tail -10`).
- [ ] Both new tests pass; the existing booking tests still pass; no SKIP.
- [ ] `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a new dependency or schema change seems needed; a file outside §3 needs a change (including any other caller of `EnqueueMail` that fails to compile); `UBYHOST_TEST_DATABASE_URL` is missing so the tests skip; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1793-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines of output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`booking_webhook.go` (`confirm`, `enqueue`, `mailConfirmed`) and the one-line signature change in `notify.go`. Check: a mail error now rolls back "paid" and answers 500 so Stripe retries the whole event; the clash path is unchanged.

## Owner steps

1. After merge and deploy, nothing changes in production while `UBYHOST_GO_BOOKING_WEBHOOK` is off, because Python still handles booking events.
2. Decide: keep Python on booking events (the same bug stays live in `App/app/booking_webhook.py`) or switch the Go booking webhook on (`UBYHOST_GO_BOOKING_WEBHOOK=1`, see ENVIRONMENT.md). If Python stays live for money, ask for a separate brief with the smallest Python fix (go-first exception 3).
3. Bookings already stuck at `paid` without a mail before this fix are not repaired here; ask for a one-off backfill brief if any exist.

## Plan differences

- The plan says "make the mail a queued job"; the mail is already an `email_outbox` row, so the change is only to write it inside the transaction.
- `enqueue` swallows errors today, so in the current code only an audit or read failure causes the lost mail; a failed outbox insert was silently dropped. Both are fixed by this brief.
- The audit line moves into the transaction as well (plan names only the mail).
- The live booking path is still Python unless the Go switch is on.
