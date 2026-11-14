# 1572 report

Status: review (one big PR mode: commits on go-wave3 worktree branch, no push, no PR)

## 1. Files changed

Commit `3c4a618 1572 step 1` adds six files (sidecars copied, sha256 verified):

- go/cmd/ubyhost-web/register_web_cleaning_host_settings_test.go
- go/internal/web/cleaning/host_settings.go
- go/internal/web/cleaning/host_settings_test.go
- go/internal/web/cleaning/host_shares.go
- go/internal/web/cleaning/hosttemplates/cleaning_settings.tmpl
- go/internal/web/cleaning/hosttemplates/cleaning_shares.tmpl

Step 5 commit: this report and the brief status line (`Status: review`).

## 2. Commands

- Step 0 anchors: all as stated (1570 and 1571 commits present, 6 sidecars, host_settings.go absent before step 1).
- Step 1: sha256 of the six copied files matches the brief table (all six).
- Step 2: `gofmt -l internal/web/cleaning cmd/ubyhost-web`, `go build ./...`, `go vet ./internal/web/cleaning/... ./cmd/...`: no output.
- Step 3: PostgreSQL 16 started on port 55721 (data dir /var/tmp/pg-1572, per orchestrator instruction; brief said 55570). Server stopped at the end.
- Step 4: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55721/postgres go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1`
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning	7.885s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.130s
  ```
- Step 4 named tests (`-v -run`):
  ```
  --- PASS: TestHostPropertySettingsPage (0.61s)
  --- PASS: TestHostSaveProperty (0.61s)
  --- PASS: TestHostShares (0.66s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning	1.894s
  --- PASS: TestCleaningHostSettingsRoutesRegistered (0.01s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.075s
  ```
- Golden test `TestCleaningMatchesPython`: `--- PASS` (0.77s).
- Full verbose run of both packages: `--- SKIP` count = 0.
- Context lint: see §4.

## 3. Acceptance (§7)

- [x] sha256 of all 6 files matches.
- [x] gofmt, build and vet silent.
- [x] Both packages `ok` on PostgreSQL; the 4 named tests PASS; 0 SKIP, 0 FAIL.
- [x] Only the §3 paths were added (plus sidecars already tracked).
- [x] No UBYHOST_GO_PATHS, Caddy, compose, env or App/ change; nothing pushed.
- UI: not applicable in this PR (pages dormant), per §7.

## 4. Deviations

- PostgreSQL port 55721 and data dir /var/tmp/pg-1572 instead of brief §4 step 3 (55570 / /var/tmp/pg55570), per orchestrator instruction.
- Context lint (`python3 scripts/context_lint.py`) reported `status review but docs/tasks/1572-report.md is missing` before this report existed; it is written now, lint rerun result is noted below.

## 5. Questions

None.

## 6. Owner steps left

None in this brief. The path switch is in brief 1573's owner steps.
