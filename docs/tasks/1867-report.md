# 1867 report

Status: review

## Files changed (`git diff --stat`)
- `App/app/billing_jobs.py` — `_unpaid_overdue` and `settle` now require `total_haler > 0`; `dunning` counts gain `settled` and, after the mail loop, settle accounts stuck `overdue` (plan set) that have no collectible invoice left.
- `go/internal/billingjob/dunning.go` — same: `unpaidOverdue` filters `total_haler > 0`; `dunningCounts.settled`; post-loop settle of overdue accounts not present in the positive-overdue list.
- `go/internal/billingjob/run.go` — `Counts.DunningSettled`, `Map["dunning_settled"]`, `Total`, assignment.
- `go/internal/web/billing/payer.go` — `settle` still-query filters `total_haler > 0`.
- `App/tests/test_billing_jobs.py` — new `test_zero_amount_invoice_is_never_dunned_and_a_stuck_overdue_settles`.
- `go/internal/billingjob/run_test.go` — Counts test covers `dunning_settled`.
- `docs/context/decisions.md` — decision line appended.

## Commands (last lines)
- Root cause repro before the fix: discount 100 → invoice `total_haler=0, paid_on=NULL` → dunning → `overdue:1`, status `overdue`, banner `{'kind': 'overdue', 'warning': True}`.
- `pytest tests/test_billing_*.py -q` → **184 passed** (incl. new test: zero invoice never duned, no mail, stuck-overdue settles to active, `settle()` clears zero-only overdue).
- `pytest tests/test_0414_billing_banner_browser.py -q` (Chromium) → 1 passed.
- `go build ./...` ok; `go vet ./internal/billingjob/ ./internal/web/billing/` ok; `go test ./internal/billingjob/... ./internal/web/billing/...` → ok (DB-gated tests skip locally, run in CI postgres shards).
- `python3 scripts/context_lint.py` → OK.

## Acceptance
- [x] Zero-amount invoices never dunned, never flip the account overdue; stuck-overdue accounts self-settle on the next daily run.
- [x] Python+Go parity kept; no schema change; `issue()` untouched so `apply_discount` reissue-if-unpaid still works.
- [x] Banner follows status, so the "Pay the invoice" line disappears once the status settles (next 06:00 run, or immediately by re-saving the discount / marking the 0 Kč invoice paid in admin).

## Deviations
- None. (Deliberately no issue-time auto-pay: it would block reissue when a 100% discount is later removed.)

## Questions
- None.

## Owner steps
1. Merge the PR via `scripts/merge-pr-on-green.sh` when green.
2. Affected zero-cost workspaces self-heal on the next 06:00 billing run; for an instant clear, re-save the discount in `/admin/customers` or mark the 0 Kč invoice paid.
