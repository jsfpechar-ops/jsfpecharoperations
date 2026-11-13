# 1173 report: issue-queue starvation

Status: review. Branch task/1173-issue-queue-starvation. Base a2bdb416 (brief commit).

## 1. Files changed (`git diff a2bdb416 HEAD --stat -- App go`)

6 files, 193 insertions, 20 deletions: App/app/door_codes.py, App/tests/test_door_code_lost_pin.py, App/tests/test_issue_queue_starvation.py (new), App/tests/test_null_order_portability.py, App/tests/test_sm_door_code_state.py, go/internal/statemachine/tables.go. Plus the two task docs.

## 2. Commands (last lines)

- Step 8, SQLite: `40 passed in 2.24s`
- Step 9, SQLite: `522 passed, 2 skipped in 16.26s`
- Step 10, ruff: `All checks passed!`
- Step 11, Go: gofmt empty, vet empty, `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/statemachine`
- Step 12, PostgreSQL schema: `PostgreSQL schema apply OK: database=ubytest, version=45, tables=71, goose=16.`
- Step 12, PostgreSQL targeted: `26 passed in 6.51s`
- Step 12, PostgreSQL door codes, TTLock, admin: `367 passed, 3 skipped in 62.04s`
- Context lint: `context lint: OK` (warning only: status.md not updated since the App/ commits, for the orchestrator)

## 3. Bites (SQLite | PostgreSQL)

- B1 no backoff: 4 failed, 2 passed | 4 failed, 2 passed
- B2 no attempts order: 1 failed, 5 passed | 1 failed, 5 passed
- B3 no NULL clause: 1 failed, 1 passed | 2 failed
- B4 expiry reversed: 1 failed, 5 passed | 1 failed, 5 passed

Each bite restored with `git checkout HEAD -- App/app/door_codes.py`; `git diff HEAD --stat` empty after each.

## 4. Section 7

- [x] Six files of section 3 plus the two task docs
- [x] Steps 8, 9, 10, 11 green on SQLite; step 12 green on PostgreSQL
- [x] Each bite fails the named tests; B3 differs between databases
- [x] Tree clean after every bite; fixed code committed
- [x] Context lint OK

## 5. Deviations

- Commits per step (`1173 step k`), as the executor guide asks, not one commit at step 13. Step 13 therefore had nothing left to commit.
- Step 1 `git checkout -b` skipped: the branch already existed and was checked out.
- Step 8 expected count `40 passed` and step 9 `522 passed, 2 skipped` matched.

## 6. Questions

None.

## 7. Owner steps left

1. Open the PR when checks are green, including test-postgres and test-postgres-full.
2. Merge with `scripts/merge-pr-on-green.sh`.
3. Orchestrator: update status.md, add the known-issues line and the three backoffs to decisions (per the brief's risk list).
