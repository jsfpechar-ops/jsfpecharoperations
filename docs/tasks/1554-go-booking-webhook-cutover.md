# 1554: Booking webhook cutover: Go stops forwarding (switch, default off)

Status: todo
Depends on: 1542, 1543 (so Go-created bookings exist before events are switched) | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (money: live Stripe webhook). Review: Opus orchestrator and the owner.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1554 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1554 step'`, not a fixed base commit.

## 1. Objective

Switch the Stripe booking-site events (`checkout.session.*` with `metadata.site_booking_id`) from "Go forwards to Python" to "Go handles them", behind the switch that already exists in the code, `UBYHOST_GO_BOOKING_WEBHOOK`. The code is merged (brief 1350) and the default stays forwarding. This brief changes no Go file: the executor proves the switch and writes the evidence; the owner flips it. It is last because a mistake here loses a paid booking.

## 2. Context

Verified facts (2026-11-14, read from `go/internal/payments/webhook.go` lines 89-157 and `booking_webhook.go`):

- Without the variable (or any value other than `1`) `webhook.go` forwards the exact raw body and the Stripe headers to `UBYHOST_PY_WEBHOOK_URL` (default `http://ubyhost:8080/webhooks/stripe`) and answers with Python's status. With `1`, `BookingWebhook.Process` handles booking events in Go; other Stripe events (Connect account updates, payment requests) are Go-handled either way.
- Go checks the Stripe signature itself before either path (`verifyEvent`), in both modes.
- Go writes what Python writes: the `paid` status, the reservation, the audit line, the two mails with Python's idempotency keys, the clash refund (idempotency key and Stripe account header) and the event row, recorded only after success so Stripe's retry runs again. It takes the same advisory lock as Python (`TestBookingWaitsForPythonLock`), so both programs can run during the switch.
- Known gaps (from the header of `booking_webhook.go`): `booking_invoice.ensure` is not ported, so Go does not issue the invoice when the booking is paid; the invoice is issued when the guest first opens `/p/{slug}/b/{id}/{token}/invoice.pdf`, which stays on Python (brief 1553 is blocked). The guest-registration link falls back to the permalink token when the apartment has no slug yet. No automatic Stripe retry (Stripe redelivers).
- Docs gap: `docs/ENVIRONMENT.md` has no row for `UBYHOST_GO_BOOKING_WEBHOOK` (count 0). The row text for the coordinator: `UBYHOST_GO_BOOKING_WEBHOOK` | unset | `1` makes the Go service handle booking-site Stripe events (`site_booking_id`) itself instead of forwarding them to `UBYHOST_PY_WEBHOOK_URL`. Unset or any other value keeps forwarding. Needs the Go container to serve `/webhooks/stripe`. Remove the line and restart the Go container to roll back.
- Stripe is in test mode in production (`docs/context/status.md`). Treat the steps as if it were live.

No new outbound request: the refund call on a clash and the forward to Python exist today.

Money table (the switch adds none; the refund amount of a clash is the paid amount, taken from the booking row, as Python): pinned by `TestBookingWebhookMatchesPython` (golden from `App/scripts/booking_webhook_golden.py`), `TestBookingRefundReplayAfterFailure`, `TestBookingConcurrentPaidEvents`.

**Paths:** `/webhooks/stripe` is the same path before and after; only the handling inside Go changes.

## 3. Files

None changed. The executor writes only `docs/tasks/1554-report.md`.

## 4. Steps

### Step 1: prove the switch in tests

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres go test -count=1 ./internal/payments/ -run 'Booking|Forward|Webhook' -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

Expected: 16 lines `--- PASS` including `TestBookingSwitchOffForwards`, `TestBookingSwitchOnHandlesInGo`, `TestBookingWebhookMatchesPython`, `TestBookingWaitsForPythonLock`, `TestForwardPythonDown`, then `ok`. Any `FAIL`: STOP. Without a local database these tests skip: say so in the report and rely on CI.

### Step 2: confirm the default

```bash
grep -n 'bookingSwitchOn(getenv)' go/internal/payments/webhook.go | tail -3
grep -n 'BookingSwitchEnv' go/internal/payments/booking_webhook.go | tail -3
```

Expected: one line each. Not found: STOP.

### Step 3: the report

Write the report with the two outputs.

## 5. Do not touch

Everything. No file is edited. Never set the variable yourself.

## 6. Commands

The commands of steps 1 and 2.

## 7. Acceptance

- [ ] Step 1 shows the listed tests passing (or the report says they skipped).
- [ ] Step 2 prints the two lines.
- [ ] `git status --short | tail -5` shows only `docs/tasks/1554-report.md`.

## Risk list (for the reviewer)

- `go/internal/payments/webhook.go` lines 89-157: the switch must leave the forward path unchanged when off.
- `go/internal/payments/booking_webhook.go`: lock key, status re-read, clash SQL, refund call and its idempotency key, event recorded only after success, mail keys.

## Owner steps

Do these only after: this PR is deployed, the Go container serves `/webhooks/stripe` (check `docs/LIGHTSAIL.md`), and brief 1550's checks for the booking pages are green.

1. Before switching, in the Stripe dashboard (test mode) open Developers, Webhooks, your endpoint, and note the last successful delivery time. This is the baseline.
2. On the server, open the Go service's env file and add the line `UBYHOST_GO_BOOKING_WEBHOOK=1`. Keep `UBYHOST_PY_WEBHOOK_URL` as it is.
3. Restart the Go container only.
4. Make one test booking on a published page (card number 4242 4242 4242 4242, any future date, any CVC). When Stripe returns to the thank-you page, open the e-mail the guest gets and its booking link: it must say paid. The host must get a mail too. In the Stripe dashboard the delivery shows status 200.
5. Make a second test booking and open `invoice.pdf` from the booking page: it must download (Python issues the invoice here).
6. Roll back at any sign of trouble: delete the line `UBYHOST_GO_BOOKING_WEBHOOK=1`, restart the Go container. Booking events go to Python again at once. Stripe retries failed deliveries for several days, so a booking whose delivery failed during the switch is confirmed by the next retry (the event row is only written after success).
7. If a paid booking shows pending after step 4: do not retry by hand; roll back (step 6), then in the Stripe dashboard use "Resend" on that event. Python then handles it.


## 8. Stop and ask

Stop, and write the report, if: a file outside section 3 needs a change; a test fails twice; a step is unclear; you reach 25 tool calls or about 50k tokens (report as `blocked`); you need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

Write `docs/tasks/1554-report.md` (600 tokens at most) and set `Status: review`: files changed (none expected), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.
