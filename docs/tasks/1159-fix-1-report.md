# 1159-fix-1 report

Status: review

## Files changed (`git diff --stat 5d2a27a..HEAD | tail -10`)

```
 App/scripts/filing_watchdog_golden.py              |   56 +-
 docs/tasks/1159-fix-1.md                           |  267 +++
 docs/tasks/1159b-go-filing-watchdog-run.md         |    4 +-
 go/internal/calendar/filing_watchdog.go            |   16 +-
 go/internal/calendar/filing_watchdog_test.go       |    5 +-
 .../calendar/testdata/filing_watchdog_golden.json  | 2458 +++++++++++++++++++-
 6 files changed, 2732 insertions(+), 74 deletions(-)
```

Plus this report (`docs/tasks/1159-fix-1-report.md`, new).

## Commits

- `13292173b` 1159-fix-1 step 1 (patch block 1 applied; three sha256 values as expected)
- `64e30f850` 1159-fix-1 step 2 (golden regenerated; sha256 `bdc27cc4...6022` as expected)
- Step 3 changed nothing, no commit.
- Step 4 changed nothing, no commit.

## Commands (last 5 lines each)

Step 0 anchors: all three sha256 match §2 (`4b162294...`, `21884e76...`, `21f36464...`).

Step 1 (`git apply --check` then `git apply`, then sha256sum):
```
d751ed495c29245c040402b06e7e644aa19b6026663058ae577edaa48d97317f  App/scripts/filing_watchdog_golden.py
b61e9aefa8214498ff911309f13babe1321fb5908d34d15bd132c5596e7f2b74  go/internal/calendar/filing_watchdog.go
6e64ea523cde046c7a5e70006d1ffcac1f41797a2b3e08290c83ed6e7f358cff  go/internal/calendar/filing_watchdog_test.go
```

Step 2 (generator, then sha256sum of the JSON):
```
wrote /home/user/jsfpecharoperations/go/internal/calendar/testdata/filing_watchdog_golden.json
bdc27cc4a4e856fbc59b61425787444a58c2996a6111c69ad2ec340604be6022  go/internal/calendar/testdata/filing_watchdog_golden.json
```

Step 3 (gofmt, go vet, go test ./internal/calendar/):
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar	0.014s
```

Step 3 (pytest, two files):
```
........................................                                 [100%]
40 passed in 3.65s
```

Step 4 (DB test against the PostgreSQL 16 already running on 127.0.0.1:55432, not the brief's new server on 55444):
```
--- PASS: TestWatchdogStaysMatchPython (1.47s)
--- PASS: TestFilingHeartbeatURLMatchesPython (0.00s)
--- PASS: TestWatchdogRetryGrace (0.00s)
--- PASS: TestWatchdogAwaitingRetry (0.00s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar	1.475s
```

Lint (`python3 scripts/context_lint.py`, last lines):
```
next free: task 1160 | migration 0046
context lint: OK
```

## Section 7 acceptance

- [x] The four sha256 values in steps 1-2 match.
- [x] gofmt empty, `go vet ./...` clean, `go test ./internal/calendar/` ok; the two pytest files pass (40 passed).
- [x] Step 4: four PASS on PostgreSQL (existing server on 55432).
- [x] `python3 scripts/context_lint.py` passes.
- [x] `git diff --stat 5d2a27a..HEAD` lists only §3 paths plus brief 1159b (hash update) and this brief.

## Deviations

- Step 4: the DB test used `postgresql://postgres@127.0.0.1:55432/postgres` as instructed by the session, so no server was started or stopped and the brief's initdb/pg_ctl commands were not run.
- Temp files (the block extractor and the patch) were written to the session scratchpad instead of `/tmp`.
- Done: steps 0 to 4. Left: none.

## Questions

None.

## Owner steps

None.
