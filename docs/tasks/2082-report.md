# 2082 report

Status: review

Files changed: `go/internal/anthropic/ai.go`, `go/internal/anthropic/ai_test.go`, `go/internal/mail/ai_budget.go`, `go/internal/mail/ai_budget_test.go`.

Verification:

- `cd go && go test ./internal/anthropic/ ./internal/mail/ -run 'AIBudgetWarning|AIBudgetMailGolden|BudgetMatchesPython' -count=1 -v`: PASS, 3 tests, no skips.

Acceptance:

- [x] AI warning is queued at 80% and uses `ai-budget-<feature>-<YYYY-MM>` with ownerless outbox fields and the generic outbox's persistent idempotency.
- [x] The synthetic English subject, text, action link, footer and HTML shell match the Python builder conventions.
- [x] 79% does not queue; 80%, repeated call, new month and another feature are covered. Invalid recipient skips queueing; failed enqueue retries on the next warning.
- [x] A queue failure does not alter a successful fake provider response. No model provider request or live mail was used.

Owner steps: review the warning example and dedupe/retry test. No deployment or live configuration changes.
