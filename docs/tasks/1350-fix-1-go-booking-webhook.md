# 1350-fix-1: booking webhook context, concurrency and replay tests

Status: todo
Depends on: 1350 | Base commit: 2bd8956 | Branch: task/1350-fix-1
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (money path) | Brief writer: Opus 5.5 | Review: orchestrator reads the diff of the risk-listed files

## 1. Objective

Fix three findings of the independent review of 1350: the Go booking handler must finish its work when Stripe hangs up mid-request, and new tests prove concurrent deliveries, the shared Python lock and the redelivery after a failed refund. The switch `UBYHOST_GO_BOOKING_WEBHOOK` stays off; production does not change.

## 2. Context

The code was written and dry-run by the brief writer. It is committed next to this brief as `docs/tasks/1350-fix-1-go-booking-webhook.patch` (against 2bd8956); you apply it with `git apply` and check sha256 values. Do not read the patch beyond what a failure needs.

What the patch does:

- **Cancellation (go/internal/payments/booking_webhook.go, `Process`).** Before: `Process` used `r.Context()`. If Stripe disconnected after the paid commit, the audit row, the mails and the event row failed with `context canceled`; Stripe's retry then found the booking `paid` ("already handled"), so the guest never got a confirmation. After: `Process` runs on `context.WithTimeout(context.WithoutCancel(ctx), bookingProcessTimeout)` with `bookingProcessTimeout = 2 * stripeTimeout` (60 s, longer than the 30 s Stripe client timeout). go.mod is `go 1.25.0`, so `context.WithoutCancel` (Go 1.21+) is available. webhook.go is not changed.
- **New tests (go/internal/payments/booking_webhook_concurrency_test.go):**
  - `TestBookingSurvivesCancelAfterCommit`: a pgx query tracer cancels the request context right after the `commit`; audit, both mails and the event row are still written. Fails without the fix (`context canceled`), checked by the brief writer.
  - `TestBookingSurvivesCancelDuringRefund`: a fake Stripe cancels the request context while answering the clash refund; the refund is recorded with its audit line and clash mails. Fails without the fix.
  - `TestBookingConcurrentPaidEvents`: `checkout.session.completed` and `checkout.session.async_payment_succeeded` for the same paid session, each delivered twice, four goroutines at once, separate pool connections: one reservation, paid once, no refund call, one guest and one host mail, two event rows.
  - `TestBookingWaitsForPythonLock`: another transaction holds `pg_advisory_xact_lock(hashtext('booking_site_dates'), 10)` (Python's `db.lock_key`); Go waits (seen in `pg_locks` as an ungranted advisory lock), writes no stay; after the holder commits, the booking is paid.
  - `TestBookingRefundReplayAfterFailure`: the golden `evt_g08` (booking 6, `pi_fail`) answers an error; its redelivery after Stripe recovered refunds once and mails once; a further redelivery is a no-op. Two refund calls in all (one failed, one succeeded), both with `Idempotency-Key: site_booking_clash_refund_6`.
- **Golden (App/scripts/booking_webhook_golden.py and the Go fake in booking_webhook_test.go):** both fakes now fail `pi_fail` on its **first** call only (Stripe recovers), and `evt_g08` is appended once more at the end of EVENTS. Python gives the same outcome as Go: results end `"ok"`, booking 6 `clash_refunded` with `refunded_czk` 4000, one `site_booking_clash_refunded` audit line, keys `site_booking:6:clash_refund` and `site_booking:6:host_clash`. golden.json is regenerated (step 2); booking_i18n.json does not change.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/payments/booking_webhook.go | edit | `Process` context and the timeout constant (step 1) |
| go/internal/payments/booking_webhook_test.go | edit | fake Stripe fails `pi_fail` once (step 1) |
| go/internal/payments/booking_webhook_concurrency_test.go | create | the five tests above (step 1) |
| App/scripts/booking_webhook_golden.py | edit | fake fails once, `evt_g08` replay (step 1) |
| go/internal/payments/testdata/booking_webhook/golden.json | regenerate | step 2 |
| docs/tasks/1350-fix-1-go-booking-webhook.patch | keep unchanged | the code, applied in step 1 |
| docs/tasks/1350-fix-1-report.md | create | report |

No other file may change.

## 4. Steps

### Step 0: environment

```bash
cd App && test -x .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt) 2>&1 | tail -3
```

Postgres for the Go tests: use `UBYHOST_TEST_DATABASE_URL` from the orchestrator. Without one, start a local Postgres 16 as the postgres user (pg_ctl refuses root):

```bash
mkdir -p /var/tmp/pg1350f && chown postgres /var/tmp/pg1350f && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1350f/data -A trust -U postgres" 2>&1 | tail -1 && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1350f/data -o '-p 55460 -k /var/tmp/pg1350f' -l /var/tmp/pg1350f/log start" 2>&1 | tail -1
export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55460/postgres
```

### Step 1: apply the code patch

```bash
sha256sum docs/tasks/1350-fix-1-go-booking-webhook.patch 2>&1 | tail -1
```

Expected: `5af4c846f14cae342d5048ba6c2d5bbb9e097aba0516b57a1b079b03a6b8e091`. Then:

```bash
git apply --check docs/tasks/1350-fix-1-go-booking-webhook.patch 2>&1 | tail -5 && git apply docs/tasks/1350-fix-1-go-booking-webhook.patch 2>&1 | tail -5
sha256sum App/scripts/booking_webhook_golden.py go/internal/payments/booking_webhook.go go/internal/payments/booking_webhook_test.go go/internal/payments/booking_webhook_concurrency_test.go 2>&1 | tail -5
```

`git apply --check` must print nothing (else STOP). Expected:

```
580ed1e74d686340adae28121cf2efd93a7346e21550e19be245d2078f5f423d  App/scripts/booking_webhook_golden.py
32ae87493cbf9b5a81fa3a448cc02166afc510b7e3ae759baaa50151b6ec0ec9  go/internal/payments/booking_webhook.go
009c6c90ade2dbfd40b107d871c06ba8402af6bb858dac4dee17eecbf81376e8  go/internal/payments/booking_webhook_test.go
c968b031b0b4229e020e3e9d53bfe458834f5c8db65c00dd984b82df97bcca10  go/internal/payments/booking_webhook_concurrency_test.go
```

Anchors the patch relies on (each found once before applying): `grep -nF "func (b *BookingWebhook) Process(ctx context.Context" go/internal/payments/booking_webhook.go`, `grep -nF 'payment intent pi_fail gets a 402.' go/internal/payments/booking_webhook_test.go`, `grep -nF '_event("evt_g17", DONE, 4),' App/scripts/booking_webhook_golden.py`.

Commit: `1350-fix-1 step 1`.

### Step 2: regenerate the golden fixture

```bash
cd App && .venv/bin/python scripts/booking_webhook_golden.py 2>&1 | tail -3 && cd .. && sha256sum go/internal/payments/testdata/booking_webhook/golden.json go/internal/payments/booking_i18n.json 2>&1 | tail -2
```

Expected:

```
134b4d1216170a173a1075650e5ca2d5cc2d93b50906d395730ee7706057f48a  go/internal/payments/testdata/booking_webhook/golden.json
731df02b9f9ad055d781fe5ddad4a9907c99301a1f3ccd2b1d1b6921e533bbf6  go/internal/payments/booking_i18n.json
```

A mismatch: STOP (never edit the JSON by hand). booking_i18n.json must stay unchanged. Commit: `1350-fix-1 step 2`.

## 5. Do not touch

go/internal/payments/webhook.go, every other file in go/internal/payments/, go/internal/hostweb/, go/internal/jobs/, go/internal/mail/, go/internal/ubyport/, App/app/, App/tests/, docs/ENVIRONMENT.md, docs/context/*, docs/tasks/1350-go-booking-webhook.md and its patch. An untracked `go/internal/web/` directory, if present, is not yours.

Hard rules: no new dependency (rule 4; `pgx` tracer is already in the module); never push to main, never merge (rule 8); no secrets (rule 3; `sk_test_golden` and the golden secret are fake). No new outbound request: the refund call is unchanged from 1350.

## 6. Commands

From the repo root, each ending `2>&1 | tail -30`:

```bash
cd go && gofmt -l ./internal/payments && go build ./... && go vet ./internal/payments 2>&1 | tail -30
```

Expected: no output.

```bash
cd go && go test -count=1 -race -v ./internal/payments/ 2>&1 | grep -E "^(--- (FAIL|SKIP)|ok|FAIL)" | tail -30
```

Expected: only `ok  github.com/.../internal/payments` (with `UBYHOST_TEST_DATABASE_URL` set; no SKIP, no FAIL). Brief writer's run: 47 top-level tests PASS with `-race`.

```bash
cd go && go test -count=1 -v ./internal/payments/ -run 'Booking' 2>&1 | grep -E "^--- " | tail -30
```

Expected: `--- PASS` for TestBookingSurvivesCancelAfterCommit, TestBookingSurvivesCancelDuringRefund, TestBookingConcurrentPaidEvents, TestBookingWaitsForPythonLock, TestBookingRefundReplayAfterFailure, TestBookingWebhookMatchesPython, TestBookingSwitchOffForwards, TestBookingSwitchOnHandlesInGo, TestBookingDatesAndToken.

```bash
cd App && .venv/bin/python -m pytest tests/test_go_booking_webhook_golden.py tests/test_booking_webhook.py tests/test_booking_site.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `69 passed`.

```bash
python3 scripts/context_lint.py 2>&1 | tail -5 && git status --short 2>&1 | tail -30
```

Expected: `context lint: OK`; only the §3 paths.

## 7. Acceptance

- [ ] The patch sha256 and all five code/fixture sha256 values match; booking_i18n.json unchanged.
- [ ] `go test -race ./internal/payments/` ok with a database; the nine Booking tests PASS, none skipped.
- [ ] pytest: 69 passed.
- [ ] `git diff --stat 2bd8956` lists only §3 files; `git diff 2bd8956 -- go/internal/payments/webhook.go` is empty.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 does not match, or the patch does not apply;
- an anchor is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1350-fix-1-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

- go/internal/payments/booking_webhook.go: `Process` must derive from `context.WithoutCancel` with the timeout and `defer cancel()`; nothing else changed.
- App/scripts/booking_webhook_golden.py: one shared `_FakeClient` (the counter must survive across calls), `pi_fail` fails once, `evt_g08` appended last.
- booking_webhook_concurrency_test.go: the tracer cancels only after a `commit`; the lock test uses the literal Python key.

Not fixed here, for the reviewer and the owner:

- Real Stripe stores the result of the first request per `Idempotency-Key` (also errors) for 24 h. A redelivery within 24 h of a refund that Stripe itself rejected gets the same stored error, in Python and in Go alike; the tests model a failure that Stripe did not store (an outage). Stripe redelivers events for up to 3 days, so a later redelivery gets a fresh answer.
- A webhook that has already returned keeps working up to 60 s in the background after Stripe hung up; a container stop in that window still loses the tail (as before).

## Before the switch

- `UBYHOST_GO_BOOKING_WEBHOOK` must stay off until Go can issue the booking invoice at payment time. Today Python's `booking_invoice.ensure` runs in the webhook; Go skips it, so invoices would be issued late (dated the download day), numbered out of order, or never. This needs the billing-PDF thread's `go/internal/pdf` and is a separate, later brief.

## Owner steps

Nothing for this PR: the switch stays off, production does not change when it merges.
