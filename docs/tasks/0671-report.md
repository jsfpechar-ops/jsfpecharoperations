# 0671 report: Go Stripe webhook matches Python after 0622/0623

Status: review

## Files changed
- go/internal/payments/webhook.go
- go/internal/payments/webhook_test.go
- docs/tasks/0671-report.md

## Changes (brief section 2, all four applied)
1. Onboarding state: top-level `disabled` check dropped. `disabled_reason` read first: `rejected*` gives rejected; `platform_paused`, `under_review`, `listed`, `other` give disabled. The errors/reject-code check and the rest are unchanged.
2. Mirror: `mirrorSQL` always updates the row. The owner lookup reads `onboarding_state`; the `stripe_account_state` audit is written only when the state changes. Same detail string.
3. Paid events: dispatch on `checkout.session.completed` and `checkout.session.async_payment_succeeded`. `payment_status` must be `"paid"`. Link id is `object.payment_link` only. The `object.id` fallback is gone.
4. Late payment: `expired` and `cancelled` go straight to `paid` (audit `id=N expired->paid`, then `payment_request_paid`). `draft` still walks through `sent`. Other statuses write nothing.

The single transaction with the event insert first is unchanged.

## Commands
- `gofmt -l .` and `go vet ./...` (from go/): clean, no output.
- `UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ -count=1 -v`:
  ```
  --- PASS: TestSweepExpiresAndPrunes (0.44s)
  --- PASS: TestVerifySignature (0.00s)
  --- PASS: TestOnboardingState (0.00s)
  --- PASS: TestRequirementsJSON (0.00s)
  --- PASS: TestWebhookDatabase (0.49s)
  --- PASS: TestWebhookRateLimit (0.81s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments	1.745s
  ```
  Pass 6, skip 0.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK`.

## Section 7
- [x] All payments tests pass with the database URL set (0 skipped).
- [x] Diff touches only the three files above (checked before commit).

## Deviations
- Header comment: the Python line numbers it named were stale, so they were removed and the functions are named without line numbers. Only the header and the comments on the changed functions were edited.
- `disabled_reason` is read with a string type assertion. A non-string value counts as "" (no state from it), which matches Python's `or ""` for normal Stripe values.
- The brief's executor doc asks for an open PR. Not done: the task says do not push. The branch is committed locally only.

## Questions
None.

## Owner steps left
1. Review the local commit on branch task/0671-local in /tmp/wt0671 (`git -C /tmp/wt0671 log -1`).
2. Push and open the PR when ready. Route stays off in production; no deploy needed for this change.
