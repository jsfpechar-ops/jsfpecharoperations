# 1437 report: Leon wizard routes registered with Havel (dormant)

Status: review. Branch: worktree-agent-a800b3937a29b02c8 (one big PR mode, nothing pushed).

## Files changed (vs base c374df7a)
- go/cmd/ubyhost-web/register_web_ai_havel.go (replaces 1434 file; adds ai.LeonRoutes after ai.HavelRoutes)
- go/cmd/ubyhost-web/register_web_ai_havel_test.go (replaces 1434 file; Leon patterns)
- docs/tasks/1437-report.md (this file)
- docs/tasks/1437-go-ai-leon-register.md (Status line only)
Go diff: 2 files, 12 insertions, 3 deletions.

## Commands (last lines)
- gofmt -l, go build ./..., go vet ./internal/web/ai/ ./cmd/...: no output (clean).
- go test ./cmd/ubyhost-web/ -count=1 -v:
  --- PASS: TestHavelRoutesRegistered
  --- PASS: TestHavelRegistrationNeedsNoPool
  --- PASS: TestCleaningRoutesRegistered
  --- PASS: TestInvoiceRoutesRegistered
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.074s
- UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55437/postgres go test ./internal/web/ai/... ./cmd/ubyhost-web/... -count=1 -v:
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai 52.087s
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.069s
- python3 scripts/context_lint.py: "next free: task 1630 | goose migration 00018", "context lint: OK"

## SKIP count
0 (grep of "--- SKIP" in the ai and ubyhost-web run = 0). No Python tests run (brief §6 lists none).

## Section 7
- [x] sha256 values match (d0d69c6c... and 5a018b7c...)
- [x] gofmt, build, vet clean; TestHavelRoutesRegistered and TestHavelRegistrationNeedsNoPool PASS; ai package PASS with DB
- [x] git diff lists only §3 paths
- [x] Commits "1437 step 1", "1437 step 2", "1437 step 3"; nothing pushed

## Deviations
- PostgreSQL on port 55437 (owner rule) instead of 55432 in brief step 3; data dir /var/tmp/pg-1437, stopped after the run.
- Step 2 changed no file: recorded as an empty commit "1437 step 2: ..." so the acceptance check finds it.
- App/.venv created (owner rule); no Python tests were run because brief §6 lists only Go and context lint.
- Steps 1 and 2 commit messages lack the Co-Authored-By and Claude-Session trailers; step 3 has them.

## Questions
- None blocking. The brief assumes UBYHOST_GO_PATHS on the server holds no broad entry (not verifiable from the repo).

## Owner steps left (from the brief, after merge and deploy)
1. Check the Go container settings listed in the brief's Owner steps 1.
2. Add `/havel` `/havel/*` `/apartments/*/leon/setup` `/apartments/*/leon/setup/*` to UBYHOST_GO_PATHS in the server .env, after checking the Caddyfile path matcher.
3. docker compose up -d; open /havel and a property's Leon setup; send one test message.
4. Rollback: remove the four paths and run docker compose up -d again.
