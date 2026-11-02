# 0671: Go Stripe webhook catches up with the Python changes of 0622/0623
Status: todo
Depends on: 0670 (re-land, PR #669) | Base commit: branch claude/project-thread-erdcp1 | Branch: claude/project-thread-erdcp1
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens
## 1. Objective
`go/internal/payments/webhook.go` was written against the Python webhook before #656 (0623) and 0622 changed it. Make the Go database effect match current Python again. Route stays off in production; no Python change.
## 2. Context
Python source of truth (read only these ranges): `App/app/stripe_connect.py` `_DISABLED_REASONS` (top), `_onboarding_state` 222-242, `_mirror` 252-283, `process_event` 391-409; `App/app/payment_links.py` `PAID_EVENTS` line 23 and `on_paid`; `App/app/payment_request.py` `_TRANSITIONS` 22-31. The four differences, and only these:
1. **Onboarding state.** Drop the top-level `disabled` check. First: `reason := requirements.disabled_reason` (string, "" if absent); `strings.HasPrefix(reason, "rejected")` gives `rejected`; reason in `platform_paused, under_review, listed, other` gives `disabled`. Then the existing errors/reject-codes check and the rest, unchanged.
2. **Mirror.** Always update the row (drop `AND onboarding_state != $8` from `mirrorSQL`). Read the current `onboarding_state` first (extend `ownerByAccountSQL` to `SELECT owner_user_id, onboarding_state ...`) and write the `stripe_account_state` audit only when the old state differs from the new one. Same detail string as today.
3. **Paid events.** Event types are `checkout.session.completed` and `checkout.session.async_payment_succeeded` (not `payment_link.paid`). Return without writing unless `object.payment_status == "paid"`. Link id is `object.payment_link` only (no `object.id` fallback).
4. **Late payment.** `expired` and `cancelled` rows may now go straight to `paid` (audit `id=N expired->paid` / `cancelled->paid`, then the `payment_request_paid` audit). `draft` still walks through `sent` first. Any other status still writes nothing.
Keep the single transaction with the event insert first: a handler error rolls the insert back too, which gives the same effect as Python recording the id last.
## 3. Files
Edit: `go/internal/payments/webhook.go`, `go/internal/payments/webhook_test.go`. Write `docs/tasks/0671-report.md`. Nothing else.
## 4. Steps
1. Make the four changes in `webhook.go`; update the comments that name Python lines or the old behaviour (`onPaid` comment says "or object.id": fix it).
2. Tests: `onboardingState` table gains `disabled_reason` cases (`rejected.fraud` gives rejected, `under_review` gives disabled, `requirements.past_due` gives action_required, top-level `disabled: true` alone no longer gives disabled). Database tests (skip without `UBYHOST_TEST_DATABASE_URL`): same state twice updates `requirements_json` and `updated_at` but writes no second audit; `payment_status: "unpaid"` writes nothing; `async_payment_succeeded` pays; an `expired` row goes to paid with two audits; old `payment_link.paid` type is recorded only. Adjust existing tests that used `payment_link.paid` or the `object.id` fallback.
3. Commit: `0671: Go Stripe webhook matches Python after 0622/0623`.
## 5. Do not touch
`App/`, everything outside `go/internal/payments/` (except the report), `go.mod`/`go.sum`, CI, compose, Caddy.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ -count=1 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All payments tests pass with the database URL set (0 skipped in the report's tail); diff touches only the three files above.
## 8. Stop and ask
Stop if the Python ranges above no longer say what section 2 describes, or if a test needs a schema change.
## 9. Report
`docs/tasks/0671-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
