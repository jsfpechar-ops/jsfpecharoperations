# 1631 report: Go paused-plan exemptions in hostweb.Login

Status: review

## 1. Files changed (vs base feb56dc)

- `go/internal/hostweb/gate.go`: `ReadOnlyOpen` plus the exemption in `Login` (step 1)
- `go/internal/hostweb/gate_paused_test.go` (new): parity test against `App/app/auth.py`, and a table test of `ReadOnlyOpen` (step 2)
- `go/internal/web/auth/auth.go`: mask, vars and `regexp` import removed (step 3)
- `go/internal/web/billing/routes.go`, `plan_page.go`, `host_actions.go`: `open` field and mask removed, callers `gate{}` (step 4)
- `go/internal/web/billing/paused_exempt_test.go` (new): PostgreSQL tests of `hostweb.Login` (step 5)
- `docs/tasks/1631-report.md` (this file), brief status line

No mask was kept.

## 2. Commands

Env: PostgreSQL 16 on port 55931, `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55931/postgres`.

- `cd go && go build ./...`: no output
- `cd go && go vet ./internal/... ./cmd/...`: no output
- `cd go && go test ./internal/hostweb/ -run ReadOnlyOpen -count=1 -v`: PASS (TestReadOnlyOpenMatchesPython, TestReadOnlyOpen)
- `cd go && go test ./internal/web/billing/ -run 'TestLoginPausedExemptions|TestPausedHostStillPostsToPlanPage' -count=1 -v`: all 12 subtests and both tests PASS
- `cd go && go test ./internal/hostweb/... ./internal/web/... ./internal/session/... -count=1 -v`: exit 0, all 17 packages `ok`, 0 FAIL, 407 PASS lines. Last lines of the package list:
  ```
  ok  github.com/.../internal/web/stayfees 3.696s
  ok  github.com/.../internal/session 4.637s
  ok  github.com/.../internal/session/admingate 0.009s
  ```
- `python3 scripts/context_lint.py`: `context lint: OK`

SKIP count: **3** (the brief expected 2):
- `TestServePagesForScreenshots` (`web/public`): needs `PUBLIC_PAGES_SHOTS_ADDR`
- `TestServeForScreenshots` (`web/public`): needs `PUBLIC_LEGAL_SHOTS_ADDR`
- `TestServeUnsubscribeForScreenshots` (`web/public`): needs `PUBLIC_UNSUB_SHOTS_ADDR`

The third one is an existing screenshot test in a package this brief does not change. It was not in the brief's list.

## 3. Section 7 acceptance

- [x] Steps 1 to 5 committed as `1631 step k`; report as `1631 report`
- [x] `openPost|g.open|gate{open` in `go/internal`: 0 matches
- [x] `_READ_ONLY_OPEN` in `gate_paused_test.go`: 4 matches
- [x] Step 2 and step 5 tests pass; paused POST `/apartments` gives 303 to `/predplatne?paused=1`; the 7 exempt POSTs give 204; impersonating admin gives 204
- [~] Section 6 skip count: 3, not 2 (see above)
- [x] Diff lists only section 3 files

## 4. Deviations

- **Base moved.** `go-wave3` advanced from feb56dc to fafb0d5 (1592 and 1593 merged) after my reset. My branch is still based on feb56dc, so `git diff go-wave3..HEAD` shows their files as deleted. Against my base the diff is only the seven files above. I did not rebase; the orchestrator should rebase or merge with current go-wave3 before merging.
- **Skip count** 3, not 2 (third screenshot test, see above).

## 5. Questions

None.

## 6. Owner steps left

None (dormant until a path is switched to Go).
