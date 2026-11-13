# 1173d report

Status: review
Branch: task/1173d-queue-final-nits (worktree /home/user/wt-1173d). Not pushed, no PR (owner step).

## 1. Files changed (git diff 8d7ba6cd --stat)

- App/app/door_codes.py: `_owner_can_hold_code` added, `ensure_row` uses it, `_issue_due` IN list built from `RELEASE_REASONS`, owner check before the delete in `_revive_unissued_expired` (C1, C2).
- App/tests/test_door_code_unverified_card.py: delayed-card test calls `_expire_ended_stays` and `_resolve_unverified_cards` directly (T1).
- App/tests/test_issue_queue_starvation.py: 6 new cases (T2, C1, C2).
- docs/tasks/1173d-queue-final-nits.md: Status review.
- docs/tasks/1173d-report.md: this report.

## 2. Commands (last lines)

- Baseline (SQLite, 3 files): `22 passed in 1.17s`
- Step 2 (SQLite, 3 files, after code edit): `22 passed in 0.85s`
- Step 3 (T1 file): `7 passed in 0.49s`
- Step 4 (3 files, ruff E9/F63/F7/F82/F401/F841): `28 passed in 1.09s`, `All checks passed!`
- Step 5 (SQLite wider): `542 passed, 2 skipped in 18.27s`
- Step 6 (Postgres schema): `PostgreSQL schema apply OK: database=ubytest, version=45, tables=71, goose=16.`
- Step 6 (Postgres, 3 files): `28 passed in 8.31s`
- Step 6 (Postgres wider): `541 passed, 3 skipped in 99.04s`
- Step 7 bites, SQLite and Postgres: `BITE FAILS AS EXPECTED` for A, B, C, D on both, then `ALL BITES CAUGHT`. `git diff HEAD --stat` empty before and after.

## 3. Section 7 acceptance

- [x] `git diff 8d7ba6cd --stat` lists door_codes.py, the two test files, the brief and the report.
- [x] SQLite 28 passed, 542 passed 2 skipped, ruff clean.
- [x] PostgreSQL 28 passed, 541 passed 3 skipped.
- [x] ALL BITES CAUGHT on both databases; tree clean afterwards.
- [x] context lint: OK (WARN about status.md is orchestrator work, not this brief).

## 4. Deviations

- Step 1 `git checkout -b` skipped: the branch already existed and was checked out; the baseline ran on it.
- Test runs used the brief's commands; no other files touched.

## 5. Questions

None.

## 6. Owner steps left

1. Open the PR from task/1173d-queue-final-nits when checks are green (test-postgres and test-postgres-full).
2. Merge with `scripts/merge-pr-on-green.sh`.
