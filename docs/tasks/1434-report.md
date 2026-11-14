# 1434 report: Havel routes registered in Go (dormant)

Status: review. One big PR mode: commits on the current branch, nothing pushed, no PR opened (the orchestrator collects the commits).

## Files changed

- `go/cmd/ubyhost-web/register_web_ai_havel.go` (new, 33 lines), commit `132f89025 1434 step 1`
- `go/cmd/ubyhost-web/register_web_ai_havel_test.go` (new, 42 lines), same commit
- `docs/tasks/1434-report.md` (this file), `docs/tasks/1434-go-ai-havel-register.md` (Status line only)

Both sha256 values match §4 step 1. Test file contains no model or HTTP call.

## Commands (last 5 lines each)

- Step 0 checks: all as specified (1433 merged, `havel_handlers.go` present, no conflicting `/havel` pattern, sidecars = 2).
- Step 2, `gofmt`, `go build`, `go vet`: no output. `go test ./cmd/ubyhost-web/ -count=1 -v`: `--- PASS: TestHavelRoutesRegistered`, `--- PASS: TestHavelRegistrationNeedsNoPool`, `--- PASS: TestRoutesRegisterOnce`, `--- PASS: TestDuplicateRouteFails`, `ok github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web 0.072s`.
- Step 3, `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5632/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 -v`: `ok .../internal/web/ai 25.596s`, `ok .../cmd/ubyhost-web 0.072s`. Exit 0.
- SKIP count from `-v` output: **0** (0 FAIL). Disposable PostgreSQL 16 on port 5632 was started and stopped, data dir `/var/tmp/pg1434` removed.
- `python3 scripts/context_lint.py`: `context lint: OK`. Warnings only (pre-existing, not stop conditions).

## 7 acceptance

- [x] 2 sha256 values match
- [x] gofmt, build, vet silent; the named tests PASS; `internal/web/ai` PASS with the database
- [x] Only §3 paths in the 1434 commits; `main.go`, `registry.go`, `register_web.go` untouched
- [x] Commit `1434 step 1` present, step 3 commit present (see git log); nothing pushed; PR not opened (draft requirement applies at PR time)

## Deviations

- The task message set PostgreSQL port 5632; the brief's command text said 55432. Used 5632.
- Brief step 3 said `tail -10`; used `-v` to count SKIP lines as the task message requires.
- Brief Status line set to `review` in this commit.

## Questions

None.

## Owner steps left

None for this brief. Owner steps in the brief (paths in `UBYHOST_GO_PATHS`) apply only after 1430 to 1434 are merged and deployed.
