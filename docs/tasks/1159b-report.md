# 1159b report: Go filing watchdog run

Status: review

## 1. Files changed (`git diff --stat origin/main..HEAD | tail -10`)

```
 App/scripts/filing_watchdog_run_golden.py          |  236 ++
 App/tests/test_filing_watchdog_run_golden.py       |   25 +
 docs/tasks/1159b-go-filing-watchdog-run.md         |    2 +-
 go/internal/calendar/filing_watchdog_run.go        |  381 +++
 go/internal/calendar/filing_watchdog_run_test.go   |  374 +++
 .../testdata/filing_watchdog_run_golden.json       | 3074 ++++++++++++++++++++
 go/internal/mail/deadline_at_risk.go               |  253 ++
 7 files changed, 4344 insertions(+), 1 deletion(-)
```

## 2. Commands and last lines

Step 0 checks: branch correct, six §3 paths absent, 1159 hashes match (d751…, b61e…, 6e64…), all anchors found once, `App/.venv` present.

Step 1 hashes: `b44e624c…910d8` (script), `7a5da39c…180fe` (JSON), both match. The generator printed the expected run-6 `TypeError` traceback, then `wrote …filing_watchdog_run_golden.json`.

Step 2 (`gofmt` and `go vet ./...`): empty output, clean. Hash `472daf4c…f70b5` matches.

Step 3 (`gofmt` and `go vet ./...`): empty output, clean. Hash `7b6eca2f…1c8d` matches.

Step 4 (`go test ./internal/calendar/ ./internal/mail/ -count=1`):
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar	0.096s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail	0.085s
```
Hash `125918c3…2720` matches.

Step 5 (`pytest` on three watchdog files): `41 passed in 3.53s`. Hash `38a35a45…6589` matches. Freshness: regenerated JSON, `git status --short go` empty.

Step 6 (DB tests on the existing PostgreSQL 16 at port 55432, not started by me): DB test RAN, did not skip.
```
--- PASS: TestRunFilingWatchdogMatchesPython (0.87s)
--- PASS: TestBuildDeadlineDigestMatchesPython (0.00s)
--- PASS: TestWatchdogAddressNeverDivergesSilently (0.00s)
--- PASS: TestRunFilingWatchdogRefusesBadSweepMinutes (0.00s)
--- PASS: TestWatchdogStaysMatchPython (0.75s)
--- PASS: TestFilingHeartbeatURLMatchesPython (0.00s)
--- PASS: TestWatchdogRetryGrace (0.00s)
--- PASS: TestWatchdogAwaitingRetry (0.00s)
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar	1.628s
```

`python3 scripts/context_lint.py`: `context lint: OK`, `next free: task 1160 | migration 0046`.

## 3. Acceptance (§7)

- [x] Six sha256 values in steps 1-5 match; 1159 hashes match.
- [x] gofmt empty, `go vet ./...` clean, `go test` ok.
- [x] Eight DB tests PASS on PostgreSQL.
- [x] Three pytest files pass (41); freshness leaves `git status --short go` empty.
- [x] `context_lint.py` passes.
- [x] Diff lists only §3 paths.
- [x] Commits "1159b step 1" to "1159b step 6"; nothing pushed.

## 4. Deviations

- Done: steps 1 to 6. Left: none.
- Temp helper written to the scratchpad instead of `/tmp/extract_block.py`, per the session's temp-file rule. The hashes decided correctness, so the output is unchanged.
- Step 6 did not initdb or start a server; it used the already-running PostgreSQL 16 at `127.0.0.1:55432`.

## 5. Questions

None.

## 6. Owner steps left

None (nothing is wired; brief E owns the switch).
