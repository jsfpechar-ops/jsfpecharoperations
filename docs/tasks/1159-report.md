# 1159 report: Go filing watchdog selection

## 1. Diff stat (4e56401..HEAD)
```
App/scripts/filing_watchdog_golden.py              |  305 +++
App/tests/test_filing_watchdog_golden.py           |   25 +
docs/tasks/1159-go-filing-watchdog.md              | 1001 ++++++++
docs/tasks/1159b-go-filing-watchdog-run.md         | 1438 +++++++++++
go/internal/calendar/filing_watchdog.go            |  266 ++
go/internal/calendar/filing_watchdog_test.go       |  245 ++
go/internal/calendar/testdata/filing_watchdog_golden.json | 2554 ++++++++++++++++++++
7 files changed, 5834 insertions(+)
```
Files 1159b and the brief itself were already on the branch from the brief commits; this run added steps 1-5 only.

## 2. Commands
- Step 1 hashes: script `4b162294...c099172` and JSON `f181775b...2067a` match. Commit 6bc7c77.
- Step 2: `gofmt -l` empty, `go vet ./...` clean; filing_watchdog.go sha `21884e76...4978` matches. Commit 408513d.
- Step 3: `go test ./internal/calendar/ -count=1` -> `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar 0.010s`. Test sha `21f36464...ff011` matches. Commit e70bb0c.
- Step 4: test sha `5eff8eba...3dab` matches. `40 passed in 4.15s`. Commit 8201093.
- Step 5 (local PostgreSQL 16, port 55432, data dir /var/tmp/pg1159):
  ```
  --- PASS: TestWatchdogStaysMatchPython (1.07s)
  --- PASS: TestFilingHeartbeatURLMatchesPython (0.00s)
  --- PASS: TestWatchdogRetryGrace (0.00s)
  --- PASS: TestWatchdogAwaitingRetry (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar	1.076s
  ```
  No SKIP: the DB parity test ran.
- §6 freshness: `git status --short go` empty after regenerating the golden.
- §6 `python3 scripts/context_lint.py`: `context lint: OK`, next free task 1160, migration 0046.

## 3. Acceptance (§7)
- [x] five sha256 values match
- [x] gofmt empty, vet clean, go test ok
- [x] step 5 four tests PASS on local PostgreSQL
- [x] App pytest 40 passed; freshness empty
- [x] context_lint OK
- [x] diff stat: only §3 paths (plus the 1159b brief already on the branch)
- [x] commits "1159 step 1" to "1159 step 5"; nothing pushed

## 4. Deviations
- Step 5 PostgreSQL: the scratch directory /tmp/claude-0/pg1159 was not usable. /tmp/claude-0 is root 0700, so the postgres user could not read its data directory, and the first start crashed (PANIC on pg_control, see log). The data directory was moved to /var/tmp/pg1159 (the brief's own path), port 55432. The first crashed attempt failed only for this reason; no test result came from it.
- Step 5 tests ran with the same Go code and golden file; nothing was edited to make them pass.
- Step 5 commit: ff8da0c (brief status and this report; amended from 1a73ff0).

## 5. Questions
None.

## 6. Owner steps left
None: nothing is wired (brief 1132 §10 E wires it).
