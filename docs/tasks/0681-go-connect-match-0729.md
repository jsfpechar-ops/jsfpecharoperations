# 0681: Go Connect routes follow 0729/0730 (flash redirects to /payments)
Status: todo
Depends on: 0676 | Base commit: claude/project-thread-iwyawc | Branch: claude/project-thread-iwyawc
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 50k tokens
## 1. Objective
Main changed `App/app/routes/stripe_connect.py` (briefs 0729, 0730). Make `go/internal/payments/connect.go` match again. Production unchanged: Go container off.
## 2. Context
See the Python change: `git diff 75d3520 origin/main -- App/app/routes/stripe_connect.py App/app/host_i18n.py`. Read `App/app/stripe_connect.py` `legal_entity_for_owner` and `handle_return` (what state it returns). Go: `connect.go`, `onboarder.go` (`HandleReturn`, the `Onboarder` interface), `hostweb.Back`, `requests.go` (how it builds a flash from `i18n.json`).
1. Start: after consent, no legal entity for the owner -> `hostweb.Back("/payments", err=payments.err.no_entity)`. Stripe off or other start failure that Python catches -> `Back("/payments", err=payments.err.stripe_start)` (today it redirects to `/`).
2. Return: `HandleReturn` must also return the mirrored onboarding state (change the interface and the fake in tests). Flash key `payments.connect.flash_complete` / `flash_action` (action_required) / `flash_pending` (anything else, including errors) and `Back("/payments", msg=...)`.
3. Add the new keys to `go/internal/payments/i18n_keys.txt`, run `App/scripts/go_host_i18n.py`.
## 3. Files
`go/internal/payments/connect.go`, `connect_test.go`, `onboarder.go`, `onboarder_test.go`, `i18n_keys.txt`, `i18n.json`. Write `docs/tasks/0681-report.md`.
## 4. Steps
Code, then tests for each new branch (no entity, start failure, three return states, return error), then commit `0681: Go Connect routes follow 0729/0730`.
## 5. Do not touch
Everything else.
## 6. Commands
From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/t0677 go test ./internal/payments/ -count=1 2>&1 | tail -20`. From `App/`: `/home/claude/wt-0677/App/.venv/bin/python scripts/go_host_i18n.py --check`. Root: `python3 scripts/context_lint.py | tail -2`.
## 7. Acceptance
payments tests pass, 0 skipped; i18n check passes.
## 8. Stop and ask
Stop if Python's `handle_return` does not return the state.
## 9. Report
`docs/tasks/0681-report.md`: tails, diff stat, decisions.
