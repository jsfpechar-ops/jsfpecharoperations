# 1450 report (executor run, One big PR mode)

Status: review

Branch: worktree-agent-ada3e91ca7cc075fa (not pushed, no PR; the orchestrator collects the commits).

## 1. Files changed

- `98b17c47c 1450 step 1`: `go/internal/scheduler/{scheduler.go,parity_test.go,scheduler_test.go,enqueue_test.go}`, `go/internal/scheduler/testdata/python_schedule.json` (11482 lines), `go/cmd/ubyhost-web/register_scheduler.go`, `go/cmd/ubyhost-web/register_scheduler_test.go`
- `5acf24132 1450 step 2`: `App/scripts/scheduler_golden.py`
- Report: `docs/tasks/1450-report.md`, brief Status line.

## 2. Commands (last 5 lines)

- Step 0 sha256: 8 of 8 `OK`. Anchors: all 6 gave 1.
- `go build ./...`: no output, exit 0.
- Golden script: `wrote .../go/internal/scheduler/testdata/python_schedule.json`; hash `17109dfde7ebba051593e30c87e44f44f69805b5402a88d3f6a67fa6c0ef56e1` (matches).
- `go vet ./internal/scheduler/... ./cmd/...`: no output. `gofmt -l`: no output.
- `go test -v ./internal/scheduler/` (with disposable PostgreSQL 16, port 5570): all 11 listed `--- PASS`, plus `TestEnqueueKeepsOneOpenRowPerKind` and `TestConcurrentEnqueueAddsOneRow` PASS (no SKIP). `ok`.
- `go test -v -run Scheduler ./cmd/ubyhost-web/`: 3 `--- PASS`, `ok`. Full `./cmd/ubyhost-web/`: `ok`.
- `go mod tidy -diff`: no output.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none names 1450).
- `cmp` of sidecar files vs copies: no output.

## 3. Section 7

- [x] Step commits list, stat names the 8 files (the step 1 commit has 7 files plus the step 2 script = 8).
- [x] Copies equal sidecar files.
- [x] Section 6 output as stated.
- [x] No change to main.go, registry.go, internal/jobs, go.mod, App/app, deploy.

## 4. Deviations

- Branch is the worktree branch, not the brief's; per One big PR mode.
- Created `App/.venv` with `requirements.txt` and `requirements-dev.txt` (untracked, not committed).
- PostgreSQL ran as the `postgres` user (root cannot run it), port 5570, data under `/var/tmp/pg1450`. Stopped and deleted.
- One compound git command was refused by the shell guard; the same commands were run one at a time.

## 5. Questions

None.

## 6. Owner steps left

None for this brief. Nothing runs until brief 1451 (`UBYHOST_SCHEDULER`).
