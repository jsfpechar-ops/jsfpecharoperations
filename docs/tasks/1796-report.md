# 1796 report: Go Stripe key/mode guard and webhook livemode check

Status: review
Worktree: /home/user/jsfpecharoperations/.claude/worktrees/agent-a8da8caf93391adfa (branch worktree-agent-a8da8caf93391adfa)
Brief: read from the main checkout copy (the brief is on branch claude/wonderful-fermat-pk93rs, not in this worktree).

## 1. Files changed (`git diff --stat HEAD~4 HEAD`)

- go/internal/payments/onboarder.go: +12 (keyMatchesMode, call in guard, "log" import)
- go/internal/payments/onboarder_test.go: +35 (TestStripeOnboarderKeyModeMismatch)
- go/internal/payments/webhook.go: +18 -3 (Livemode field, livemodeMatches, check after verifyEvent)
- go/internal/payments/webhook_test.go: +52 (TestLivemodeMatches, TestWebhookLivemodeMismatch)
- docs/tasks/1796-report.md: this file

Commits: 1796 step 1 (fe0ea58), step 2 (119c19b), step 3 (871edb5), step 4 (86baa20), report (see git log).

## 2. Commands (last lines)

- `go test ./internal/payments/ -run 'TestLivemodeMatches|TestWebhookLivemodeMismatch' -count=1 -v`: `--- PASS: TestLivemodeMatches`; `--- SKIP: TestWebhookLivemodeMismatch` (UBYHOST_TEST_DATABASE_URL is not set); `ok`.
- `go test ./internal/payments/ -run TestStripeOnboarderKeyModeMismatch -count=1 -v`: `--- SKIP` (same reason); `ok`.
- `go test ./internal/payments/ -count=1 -v | grep -c SKIP`: 35 (brief expects 0).
- `go test ./internal/payments/ -count=1 -v | grep -c -- '--- PASS'`: 20.
- `go test ./internal/payments/ -count=1`: `ok ... 0.023s`.
- `gofmt -l internal/payments`: no output.
- `go vet ./internal/payments/`: no output.
- `go build ./...`: no output (exit 0).
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, about other open briefs).

## 3. Section 7 ticked

- [ ] Wrong-prefix key refused, no request, no lock_api_usage row: code in place; test SKIPS here (no DB). Not verified.
- [x] Log line names mode and prefixes, never the key (only `%s` is bound to mode).
- [ ] Mismatched livemode gets 200 ignored, no row, no account change: code in place; DB test SKIPS. Not verified.
- [ ] All existing tests pass, 0 skipped: the package passes, but 35 tests skipped (no DB).
- [x] git diff lists only section 3 files.

## 4. Deviations

- The session override allows missing UBYHOST_TEST_DATABASE_URL. Brief §4 step 0 and §8 say STOP. I ran on, per the override.
- Done: steps 1 to 4 and section 6. Left: nothing in code. The DB-backed tests need CI (or a local DB) to run.
- `TestLivemodeMatches` (pure) passes. The keyMatchesMode table in `TestStripeOnboarderKeyModeMismatch` is after the DB skip, so it did not run.

## 5. Questions

- None.

## 6. Owner steps left

- Let CI run the DB tests. Confirm `TestStripeOnboarderKeyModeMismatch` and `TestWebhookLivemodeMismatch` PASS, not SKIP, before merge.
- Branch placement: the brief names `task/1796-go-stripe-key-mode-guard`. This branch is `worktree-agent-a8da8caf93391adfa`. The orchestrator integrates the commits.
