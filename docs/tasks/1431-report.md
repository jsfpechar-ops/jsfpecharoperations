# 1431 report: Go Havel store (limits, stats, gap log, plan multiplier, AI switches)

Status: review

## Files changed (section 3 only)

- `go/internal/web/ai/havel_store.go` (new, from sidecar)
- `go/internal/web/ai/havel_store_test.go` (new, from sidecar)
- `go/internal/web/ai/havel_testdb_test.go` (new, from sidecar)
- `docs/tasks/1431-report.md` (new)
- `docs/tasks/1431-go-ai-havel-store.md` (Status line only, per section 9)

## Checks

- Step 0 anchors: all matched (1430 step 1 present, havel_engine.go present, havel_store.go absent, both Python anchors 1, 3 sidecar files).
- sha256: all three match section 4 step 1.
- PostgreSQL: disposable server on port 5619, data in `/var/tmp/pg1431` (per task message, instead of the brief's 55432 and `/var/tmp/pgai`). Stopped and deleted at the end.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5619/postgres`

Command outputs (last lines):

- gofmt, go build, go vet: no output.
- `go test ./internal/web/ai/ -count=1 -v`: `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai 17.904s`. The five 1431 tests PASS: TestHavelWindowsAreWallClockSeconds, TestHavelGates, TestHavelLimitsOnPostgres, TestHavelRecordsAndSupportCap, TestHavelStatsAndGapLog. The 1430 tests also PASS.
- Skip count: 0 (`grep -c -- '--- SKIP'` on the full run). PASS lines: 48.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none for files in section 3).

## Section 7 acceptance

- [x] sha256 values match
- [x] gofmt, build, vet clean; 1431 tests PASS, 0 skipped; 1430 tests PASS
- [x] commit stat lists only section 3 paths (checked with `git show --stat`)
- [x] commits `1431 step 1` and `1431 step 3`; nothing pushed

## Deviations

- Port 5619 and data dir `/var/tmp/pg1431` (task message) instead of 55432 and `/var/tmp/pgai`.
- Brief section 3 says no other file may change. The Status line in the brief was set to `review`, as section 9 and the executor instructions ask.

## Questions

None.

## Owner steps

None.
