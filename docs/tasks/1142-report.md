# 1142 report: claim refresh respects TTL

## 1. Files changed (`git diff --stat 7833efbf HEAD`)

```
 App/app/reporting.py                 | 31 +++++++++--------
 App/tests/test_claim_recheck_stay.py | 58 ++++++++++++++++++++++++++++----
 go/internal/ical/syncfeed.go         |  5 ++-
 go/internal/ubyport/claim.go         | 10 ++++--
 go/internal/ubyport/claim_test.go    | 64 +++++++++++++++++++++++++++++++++---
 go/internal/ubyport/sweep.go         | 12 ++++---
 6 files changed, 147 insertions(+), 33 deletions(-)
```

## 2. Commands and results

Step 6.1, Python (SQLite), from `App/`:
`.venv/bin/python -m pytest tests/test_claim_recheck_stay.py tests/test_icalsync.py tests/test_sm_*.py ... tests/test_endtoend.py -q --tb=short 2>&1 | tail -30`
Result: 13 failed, 878 passed, 1 skipped. Run twice with the same result. All 13 failures are in `tests/test_endtoend.py` (test_06, 08, 09, 12, 13, 14, 15, 17, 18, 19, 21, 22, 23). `tests/test_endtoend.py` alone: 28 passed.
Pre-existing: the orchestrator ran the same combined file list on `origin/main` (without 1142 and without `test_claim_recheck_stay.py`) and got the same 13 failures. This is a known test-ordering failure, not caused by 1142. Last lines of output:
```
FAILED tests/test_endtoend.py::test_22_house_book_export_covers_everyone_including_czechs
FAILED tests/test_endtoend.py::test_23_deadline_watch_raises_nothing_once_everyone_is_reported
13 failed, 878 passed, 1 skipped, 3 warnings in 30.22s
```

Step 6.2, Go (PG), from `go/`:
`UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ ./internal/ubyport/ -count=1 2>&1 | tail -30`
Result: `ok ical 11.746s`, `ok ubyport 34.497s`. SKIP count with `-v`: 0.

Step 6.3: `go vet ./internal/ical/ ./internal/ubyport/` produced no output (exit 0). `gofmt -l internal` produced no output.

Extra PG check, from `App/`:
`UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short 2>&1 | tail -10`
Result: `9 passed in 5.24s`.

Step 6.5: `python3 scripts/context_lint.py 2>&1 | tail -3`
Result: a WARN that 15 commits touched App/ after the last status.md update (orchestrator to update status.md), then `context lint: OK`.

## 3. Section 7 (acceptance)

- [x] `claimed_at >= ?` in the refresh UPDATE (`App/app/reporting.py`); `claimed_at >= $3` in `go/internal/ubyport/claim.go`.
- [x] Two new Python tests and two new Go tests pass, 0 SKIP.
- [x] Four revert-bite checks failed with the fix reverted and passed after restore (reported by the orchestrator; not re-run in step 6).
- [x] Expired claim is neither refreshed nor sent; missing guest row stops the send (Python and Go).
- [x] `go vet` and `gofmt -l` clean; claim tests and `test_sm_*` green in step 6.1 except the pre-existing `test_endtoend.py` ordering failures; context lint OK.
- [x] `syncfeed.go` no longer discards the type assertion result.

## 4. Revert-bite outcomes

Reported by the orchestrator from steps 2 and 4: Py (a), Py (b), Go (a), Go (b) each FAILED with the fix reverted, then passed after restore.

## 5. Deviations

- Extra commit `eef9634a`: removed an unused `counter` table from the `fresh_db` fixture in `App/tests/test_claim_recheck_stay.py`. It caused a DuplicateTable error on Postgres CI.

## 6. Questions

None.

## 7. Owner steps left

None for this brief. Merge goes through `scripts/merge-pr-on-green.sh` after the PR is opened.
