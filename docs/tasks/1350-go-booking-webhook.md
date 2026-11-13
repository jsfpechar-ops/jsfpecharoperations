# 1350: Go booking webhook (switched off)

Status: todo
Depends on: none | Base commit: a83df54 | Branch: task/1350-go-booking-webhook
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (money path) | Brief writer: Opus 5.5 | Review: Opus (reads the whole diff against this brief)

## 1. Objective

Port the booking-site Stripe webhook (App/app/booking_webhook.py and what it calls) to Go, so Go can stop forwarding booking events to Python. The port is **off by default**: only `UBYHOST_GO_BOOKING_WEBHOOK=1` makes Go handle booking events; any other value (or unset) keeps today's forward to Python byte for byte.

## 2. Context

The code was written and dry-run by the brief writer. It is committed next to this brief as `docs/tasks/1350-go-booking-webhook.patch` (all five code files, against a83df54); you apply it with `git apply` and check sha256 values. Do not read the patch beyond what a failure needs.

What the Go handler does (mirrors Python exactly, golden-tested):

- Dedupe as `stripe_connect.process_event`: a seen `event_id` is a no-op (200 ok); the id is recorded **after** the handler returns, so a handler error answers 500, leaves the event unrecorded, and Stripe retries.
- Paid session (`payment_status == "paid"`, booking `pending` or `expired`): one transaction with `pg_advisory_xact_lock(hashtext('booking_site_dates'), apartment_id::int4)` (the same key Python's `db.lock_key` takes, so Python and Go writers exclude each other), status re-read, clash check, `reservation` insert (source `site`, uid `site-<id>`), `site_booking` -> paid, hold deleted. Then audit `site_booking_paid` and the outbox mails (`site_booking_confirmed` to the guest, `site_booking_host` to the host) with the same keys, subjects and payload JSON as Python.
- Clash: refund on the connected account (`POST /v1/refunds`, `Stripe-Account`, `Idempotency-Key: site_booking_clash_refund_<id>`, through the `StripeOnboarder.guard` call budget), status `clash_refunded`, audit, clash mails. No account / no payment intent / Stripe error: return an error (500, Stripe retries), as Python raises.
- Expired / async failed: pending -> expired, hold deleted. Unpaid, already handled, unknown session: no-op.

Known gaps (written in the file comment of booking_webhook.go):

- `booking_invoice.ensure` is **not ported**. Verified in App/app/booking_invoice.py and App/app/routes/property_page.py:414-440: the Python route `/p/{slug}/b/{id}/{token}/invoice.pdf` calls `booking_invoice.ensure`, so the invoice is issued when the guest first opens that link. What is lost: the invoice's issue date is the day of first opening, not the payment day (`today=claim.prague_today()`); a guest who never opens it gets no invoice row; and the `invoice_issued` / `site_invoice_skipped` audit lines appear then, not at payment.
- `guest_slug.ensure` minting: if an apartment has a permalink token but no current `apartment_slug`, Go links `/l/<permalink_token>/<reservation>` (the token works for ever); Python would mint a slug first.
- No Stripe network retries in Go (as onboarder.go); Stripe redelivers the event.
- Go loads the secret key before any write (Python reads it later, in the mail step), so a missing key fails before the booking is confirmed.

Translations: `go/internal/payments/booking_i18n.json` holds only the 16 keys the handler reads (cs, en), generated from App/app/host_i18n.py by the golden script; `App/tests/test_go_booking_webhook_golden.py` fails when it or the golden fixture is stale.

New env var: `UBYHOST_GO_BOOKING_WEBHOOK` — `1` (trimmed) = Go handles booking events; anything else = forward to `UBYHOST_PY_WEBHOOK_URL` as today. It is read once, when the handler is built. (Documenting it in docs/ENVIRONMENT.md is left to the orchestrator: not in this brief's files.)

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/payments/booking_webhook.go | create | the Go handler (step 1) |
| go/internal/payments/booking_webhook_test.go | create | golden parity test + switch tests (step 1) |
| go/internal/payments/webhook.go | edit | switch branch only (step 1) |
| App/scripts/booking_webhook_golden.py | create | golden generator (step 1) |
| App/tests/test_go_booking_webhook_golden.py | create | staleness test (step 1) |
| go/internal/payments/booking_i18n.json | create (generated) | step 2 |
| go/internal/payments/testdata/booking_webhook/golden.json | create (generated) | step 2 |
| docs/tasks/1350-go-booking-webhook.patch | keep unchanged | the code, applied in step 1 |
| docs/tasks/1350-report.md | create | report |

No other file may change.

## 4. Steps


### Step 0: environment

```bash
cd App && test -x .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt) 2>&1 | tail -3
```

Postgres for the Go tests: the orchestrator gives you `UBYHOST_TEST_DATABASE_URL`. Without one, start a local Postgres 16 as the postgres user (pg_ctl refuses root):

```bash
mkdir -p /var/tmp/pg1350x && chown postgres /var/tmp/pg1350x && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1350x/data -A trust -U postgres" 2>&1 | tail -1 && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1350x/data -o '-p 55451 -k /var/tmp/pg1350x' -l /var/tmp/pg1350x/log start" 2>&1 | tail -1
export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55451/postgres
```

### Step 1: apply the code patch

```bash
sha256sum docs/tasks/1350-go-booking-webhook.patch 2>&1 | tail -1
```

Expected: `169099ddeaf8126e88055abb66c4ec3e266bef29c995ec4adb7f51cd836bbedb`. Then:

```bash
git apply --check docs/tasks/1350-go-booking-webhook.patch 2>&1 | tail -5 && git apply docs/tasks/1350-go-booking-webhook.patch 2>&1 | tail -5
sha256sum App/scripts/booking_webhook_golden.py App/tests/test_go_booking_webhook_golden.py go/internal/payments/booking_webhook.go go/internal/payments/booking_webhook_test.go go/internal/payments/webhook.go 2>&1 | tail -5
```

`git apply --check` must print nothing (else STOP). Expected sha256 lines:

```
6201746433ec0e1d491124f6de246b5f2553c2a8f586e46276b4e00876bba703  App/scripts/booking_webhook_golden.py
9a0394e989e6e2a008f520eb8dd936539a71f88b03302328db6893800952713a  App/tests/test_go_booking_webhook_golden.py
09028686d8250f0c95164d1160d875ab1a7f220f83418e0c0e8ca8754244f918  go/internal/payments/booking_webhook.go
616789b0cc4960b63a8989bcf5e95e1501b01eb793a6fb05294d668bc71aea89  go/internal/payments/booking_webhook_test.go
91cb11d0903e8e16779a801e604d137d9c8898b9a6c6644455f3555a585c2d9e  go/internal/payments/webhook.go
```

Anchors this patch relies on in webhook.go (each found once before applying): `grep -nF "forwardToPython(w, r, client, pyURL, raw)" go/internal/payments/webhook.go` and `grep -nF "Such events go to Python only." go/internal/payments/webhook.go`.

Commit: `1350 step 1`.

### Step 2: generate the fixtures

The golden script writes both JSON files from the real Python handler:

```bash
cd App && .venv/bin/python scripts/booking_webhook_golden.py 2>&1 | tail -3 && cd .. && sha256sum go/internal/payments/testdata/booking_webhook/golden.json go/internal/payments/booking_i18n.json 2>&1 | tail -2
```

Expected:

```
7498406994c983bd1bf18779bb4a752424d6abaa4b0a1a9aa6de40c0c90af713  go/internal/payments/testdata/booking_webhook/golden.json
731df02b9f9ad055d781fe5ddad4a9907c99301a1f3ccd2b1d1b6921e533bbf6  go/internal/payments/booking_i18n.json
```

A mismatch: STOP (do not edit the JSON by hand). Commit: `1350 step 2`.

## 5. Do not touch

go/internal/hostweb/, go/internal/jobs/, go/internal/mail/, go/internal/ubyport/, go/cmd/ubyhost-web/main.go, any register_*.go, App/app/, App/tests/conftest.py, docs/ENVIRONMENT.md, docs/context/*, any other file in go/internal/payments/ (onboarder.go, webhook_forward_test.go and webhook_test.go must stay unchanged). An untracked `go/internal/web/` directory, if present in your checkout, is not yours: do not add or commit it.

Hard rules: no new dependency (rule 4); never push to main, never merge (rule 8); no secrets (rule 3; the golden secret and `sk_test_golden` are fake test values). New outbound request: the Stripe refund (`POST https://api.stripe.com/v1/refunds`), only on a double booking and only with the switch on. Reason for the PR: the guest paid for nights already sold and must get the money back, as Python does today (rule 2).

## 6. Commands

Run from the repo root unless noted, each ending `2>&1 | tail -30`:

```bash
cd go && gofmt -l ./internal/payments && go build ./... && go vet ./internal/payments 2>&1 | tail -30
```

Expected: no output.

```bash
cd go && go test -count=1 ./internal/payments/... 2>&1 | tail -30
```

Expected: `ok` (with `UBYHOST_TEST_DATABASE_URL` set; the DB tests skip without it, which does not count as passing).

```bash
cd go && go test -count=1 -v ./internal/payments/ -run 'Booking|Forward' 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -30
```

Expected: `--- PASS` for TestBookingWebhookMatchesPython, TestBookingSwitchOffForwards, TestBookingSwitchOnHandlesInGo, TestBookingDatesAndToken, TestForwardBookingEventTypes, TestForwardPassesPythonStatus and the other Forward tests; no SKIP, no FAIL.

```bash
cd App && .venv/bin/python -m pytest tests/test_booking_site.py tests/test_booking_webhook.py tests/test_stripe_connect.py tests/test_go_booking_webhook_golden.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `69 passed`.

```bash
git status --short 2>&1 | tail -30
```

Expected: only the §3 paths (and the report).

## 7. Acceptance

- [ ] The patch sha256 and all seven file sha256 values match (steps 1-2).
- [ ] `go test ./internal/payments/...` ok with a database; the Booking and Forward tests PASS, none skipped.
- [ ] pytest: 69 passed.
- [ ] `git diff --stat a83df54` lists only the §3 files.
- [ ] webhook_forward_test.go and webhook_test.go unchanged (`git diff a83df54 -- go/internal/payments/webhook_forward_test.go go/internal/payments/webhook_test.go` is empty).

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 does not match, or the patch in step 1 does not apply;
- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1350-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- go/internal/payments/booking_webhook.go (whole file): lock key, status re-read, clash SQL, refund call and its idempotency key, event recorded only after success, mail keys and payload JSON.
- go/internal/payments/webhook.go: the switch must leave the forward path unchanged when off.
- App/scripts/booking_webhook_golden.py: the fakes (Stripe at `_client`, `booking_invoice.ensure` no-op) and the event list.

Points where Go may differ from Python (reviewer, check these):

- `ubyport.NormaliseEmail` accepts only `addr` and `Name <addr>`; Python's `parseaddr` is more lenient (an odd stored address may get no mail in Go).
- Python's mail.enqueue raises when its first SELECT fails; Go logs every enqueue failure and goes on.
- `UBYHOST_PUBLIC_BASE_URL` set to an empty string: Python uses "", Go uses the default `http://127.0.0.1:8080`.
- Refund form keys are sent in sorted order (`metadata[site_booking_id]` before `payment_intent`); stripe-python's order differs, same content.
- A Stripe account row with an empty `stripe_account_id` counts as "no account" in Go.

## Owner steps

Nothing to do for this PR: the switch is off, so production behaviour does not change when it merges.

Later, to turn Go booking handling on (only after the Go container serves `/webhooks/stripe` in production and this PR is merged):

1. On the server, open the Go service's env file and add the line `UBYHOST_GO_BOOKING_WEBHOOK=1`.
2. Restart the Go container.
3. Make one test-mode booking on the booking site and check that the booking page says paid and both mails arrive.
4. To switch back, delete the line and restart the Go container: booking events go to Python again.
