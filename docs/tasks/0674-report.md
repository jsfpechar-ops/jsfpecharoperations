# 0674 report: Go Stripe Connect onboarder and route wiring
Status: review

## Files changed
- Created `go/internal/payments/onboarder.go`: `StripeOnboarder` (Pool, Getenv, Now, Client, APIBase), `NewStripeOnboarder`, guard (mode, key, budget, count), v2 account create, v1 account link, return.
- Created `go/internal/payments/onboarder_test.go`: fake Stripe via httptest, cases from brief section 4 step 3.
- Edited `go/cmd/ubyhost-web/main.go`: three routes next to the webhook line (GET and POST start, GET return), all via `m.wrap`.
- Edited `docs/tasks/0674-go-connect-onboarder.md`: Status line to `review`.
- Created `docs/tasks/0674-report.md`.

## Commands
- `gofmt -l .` (from `go/`): empty after `gofmt -w` on the two new files.
- `go vet ./internal/payments/ ./cmd/...`: clean. `go build ./...`: clean.
- `UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ ./cmd/... -count=1 -v | grep -E "^(---|ok|FAIL|PASS)"` (tail):
  ```
  --- PASS: TestConnectDatabase (0.57s)
  --- PASS: TestStripeOnboarderOffMakesNoCall (0.37s)
  --- PASS: TestStripeOnboarderNoEntity (0.38s)
  --- PASS: TestStripeOnboarderLinksAndReturn (0.35s)
  --- PASS: TestSweepExpiresAndPrunes (0.38s)
  --- PASS: TestWebhookDatabase (0.40s)
  --- PASS: TestWebhookRateLimit (0.83s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments	3.286s
  ```
  0 skipped (no SKIP lines).
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Section 7 ticked
- [x] Payments tests pass with the DB URL set, 0 skipped.
- [x] Build and vet clean.
- [x] Diff touches only section 3 files plus the Status line.

## Deviations and decisions beyond the brief
- One commit, not one per step, as the owner's instruction asked.
- Commit trailer uses `Co-Authored-By: Claude Opus 5.5` as the owner's instruction gave, not the Haiku line in the session reminder.
- Account lookup follows Python order: mirror row for the current mode, then the legal entity, then the guard. So mode off with no entity gives `ErrNoEntity`; mode off with an entity gives `ErrStripeOff`.
- Unparsable or empty `UBYHOST_STRIPE_MONTHLY_API_CALLS` falls back to 50000, as the brief says.
- The budget test uses month `2026-09`, the month of the fixed test clock `testNow`.
- The v2 request body is built from Go maps, so JSON keys are sorted. The test compares decoded content, not bytes.
- No Postgres changes and no new dependency.
- `status.md` lint warning (30 App commits since last status update) is orchestrator work, not touched here.

## Owner steps left
- Review and merge the PR through `scripts/merge-pr-on-green.sh`. Production stays off: `UBYHOST_GO_PATHS` stays `/__go_off__` until the owner switches it.
