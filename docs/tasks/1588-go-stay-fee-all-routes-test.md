# 1588: Go stay fee pages: all 16 routes registered (test only)

Status: review
Depends on: 1581, 1582, 1583, 1584, 1585, 1586, 1587 (and the routes that were already in Go from 1330) | Base commit: current tip of the working branch | Branch: task/1588-go-stay-fee-all-routes-test
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier C

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1588 step k` (`k` is the step number). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1588 step'`.

## 1. Objective

Add one test that proves all 16 routes of `App/app/routes/stay_fees.py` are registered in `newMux` with the expected Go pattern. It is the gate for the rollout plan of brief 1589: until it passes, `/stay-fees` must not be routed to Go. No production code changes.

## 2. Context

Rules (AGENTS.md): 3 made-up data only (none used); 4 no dependency; 11 Go first. The test needs no database.

**The code is pre-written, compiled and tested.** Sidecar: `docs/tasks/1588-files/go/cmd/ubyhost-web/register_web_stayfees_all_test.go.txt`. Step 1 copies it; never retype or edit it.

| sha256 | file | action | lines |
|---|---|---|---|
| `0708f110e27de287c3c56c52d4fda6c75a9182dc3374282d07c8e525299e19ac` | `go/cmd/ubyhost-web/register_web_stayfees_all_test.go` | create | 42 |

**Verified by the brief writer** (in a throwaway copy of the branch with the steps of briefs 1580 to 1587 applied in order, then this one): `gofmt -l` printed nothing, `go build ./...` and `go vet` on the stay fee packages and `./cmd/...` were silent, and `go test ./internal/web/stayfees/... ./internal/stayfeepdf/... ./internal/pdf/... ./internal/stayfee/... ./internal/stayfeemail/... ./cmd/ubyhost-web/... -count=1` printed `ok` for all six packages on PostgreSQL 16 with no `--- SKIP` and no `--- FAIL`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_all_test.go` | create | the route table test |
| `docs/tasks/1588-files/**` | keep | sidecar (do not edit) |
| `docs/tasks/1588-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (section 8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/stayfees/page_detail.go go/internal/web/stayfees/download.go go/internal/web/stayfees/adjust.go go/internal/web/stayfees/finalize.go go/internal/web/stayfees/confirm.go go/internal/web/stayfees/guestpay_preview.go 2>&1 | grep -c "No such file" | tail -1` prints `0` (briefs 1581 to 1587 are on this branch). `ls go/internal/stayfeepdf/*.go 2>&1 | grep -c "No such file" | tail -1` prints `0` (brief 1580).
   - `ls go/cmd/ubyhost-web/register_web_stayfees_all_test.go 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1588-files -name '*.txt' | wc -l | tail -1` prints `1`.

1. Copy the sidecar and check it (repo root):

   ```bash
   cp docs/tasks/1588-files/go/cmd/ubyhost-web/register_web_stayfees_all_test.go.txt go/cmd/ubyhost-web/register_web_stayfees_all_test.go && sha256sum -c - <<'EOT' 2>&1 | tail -3
   0708f110e27de287c3c56c52d4fda6c75a9182dc3374282d07c8e525299e19ac  go/cmd/ubyhost-web/register_web_stayfees_all_test.go
   EOT
   ```

   The line must end with `: OK`. Then commit "1588 step 1".

2. Format, build, vet and test (one call, from `go/`):

   ```bash
   cd go && gofmt -l cmd/ubyhost-web 2>&1 | tail -5; go vet ./cmd/... 2>&1 | tail -30; go test ./cmd/ubyhost-web/ -count=1 -v -run '^TestStayFeesAllRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10
   ```

   Expected: no output from gofmt and vet, then `--- PASS: TestStayFeesAllRoutesRegistered (0.NNs)` and an `ok` line. Any `pattern ... want` line means a route of 1581 to 1587 is missing or shadowed: STOP (section 8); do not edit the test.

3. Write the report (section 9), set `Status: review` in this file and commit "1588 step 3".

## 5. Do not touch

`App/`, every other Go file, `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, the sidecar.

## 6. Commands

Only those of the steps above. No full test suite.

## 7. Acceptance

- [ ] `sha256sum -c` printed `: OK`.
- [ ] gofmt and vet printed nothing; the test printed `--- PASS` and `ok` (no `SKIP`, no `FAIL`).
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1588 step')` lists only the test file, the report and this brief.
- [ ] No path was added to `UBYHOST_GO_PATHS`; nothing pushed to `main`.

## 8. Stop and ask

Stop, and write the report, if an anchor or hash is not as stated, the test fails (report the `pattern` lines, fix nothing), you reach 25 tool calls or about 50k tokens (report as `blocked`), or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1588-report.md` (600 tokens at most): files changed, each command with the last 5 lines of output, section 7 ticked, deviations, questions.

## Owner steps

None: nothing is switched on. The path switch is in `docs/plans/stay-fee-go-rollout.md` (brief 1589).
