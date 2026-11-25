# 2082: Restore the operator AI budget warning email

Status: todo
Depends on: none | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2082-go-ai-budget-operator-mail
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Queue the existing operator warning at 80% of a feature's monthly budget. Keep provider behavior and caps unchanged.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/ai.py:310`

  ```text
  if budget_fraction(feature) < 0.8:
  ```
- `App/app/mail_notify.py:3043`

  ```text
  def build_ai_budget(*, feature: str, month: str, spent: float, cap: float) -> Dict[str, str]:
  ```
- `App/app/mail_notify.py:3062`

  ```text
  idempotency_key=f"ai-budget-{feature}-{month}",
  ```
- `go/internal/anthropic/ai.go:333`

  ```text
  func (s *Service) warnBudget(ctx context.Context, feature string) {
  ```
- `go/internal/anthropic/ai.go:233`

  ```text
  func (s *Service) MonthSpendUSD(ctx context.Context, feature string, day time.Time) (float64, error) {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/anthropic/ai.go` | edit | Queue notice from the shared budget warning path. |
| `go/internal/anthropic/ai_test.go` | edit | Threshold, duplicate, enqueue failure and spend tests. |
| `go/internal/mail/ai_budget.go` | add | Build and enqueue the existing operator message. |
| `go/internal/mail/ai_budget_test.go` | add | Compare to synthetic Python content. |

The executor report and brief status follow section 9.

## 4. Steps

1. In `mail`, add the operator `ai_budget` builder to match `App/app/mail_notify.py:3043–3065`. Reuse the existing shell/subject conventions. Queue for the configured operator using `ai-budget-<feature>-<YYYY-MM>`, the correct language and the exact Python subject, text and HTML. Use the existing generic outbox insert from the caller, with a nil owner and the persistent key. Keep the mail package responsible for rendering only, to preserve the current package dependency direction. Leave account mail handling unchanged.
2. In `warnBudget`, once the existing fraction is at least 0.80, use the same `Today`, `MonthSpendUSD` and `MonthlyUSD` scopes for feature, month, spend and cap. Replace the current log-only path with the shared enqueue. Keep the operation best effort. A queue or recipient failure logs minimal diagnostics, leaves the model result alone and is eligible for a later retry. Keep the same branches for both providers.
3. Add `TestAIBudgetWarning` and `TestAIBudgetMailGolden`. Cover 79%, 80%, repeat in a month, another feature or month, a missing recipient, failed enqueue and successful provider response. Use recorded test senders and synthetic spend. Run section 6.

## 5. Do not touch

Keep model prompts, providers, thresholds, configuration, call quotas and other mail kinds. No provider requests or live mail in verification.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/anthropic/ ./internal/mail/ -run 'AIBudgetWarning|AIBudgetMailGolden|BudgetMatchesPython' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] At most one message per feature/month is queued to the operator, including across processes.
- [ ] Python and Go sample copy, recipient and key match.
- [ ] Model responses and budget caps remain unaffected by queue results.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2082-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/anthropic/ai.go`, `go/internal/mail/ai_budget.go`

## Owner steps

1. Review the warning example and the dedupe test.
