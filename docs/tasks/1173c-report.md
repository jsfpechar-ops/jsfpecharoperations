# 1173c report: queue review fixes

Status: review

## 1. Files (git diff 21d70cf3 --stat, App part)

- App/app/door_codes.py: 63 lines (RELEASE_REASONS, due ORDER BY CASE, `_revive_unissued_expired` and its `_phase` call, second UPDATE in `_resolve_unverified_cards`)
- App/tests/test_issue_queue_starvation.py: 100 lines added (8 cases)
- App/tests/test_door_code_unverified_card.py: 60 lines (`_issued_stay(lock_id)` plus 3 tests)
- App/tests/test_null_order_portability.py: 2 lines (regex)
- docs/tasks/1173c-queue-review-fixes.md: Status review

## 2. Commands (last lines)

- Step 6, SQLite: `22 passed in 0.91s`
- Step 7, SQLite: `536 passed, 2 skipped in 16.65s` (2 Playwright, not installed); ruff: `All checks passed!`
- Step 9, PostgreSQL: schema `PostgreSQL schema apply OK: database=ubytest, version=45, tables=71, goose=16`; step 6 set `22 passed in 6.70s`; step 7 set `535 passed, 3 skipped` (2 Playwright, 1 `sqlite_only` in test_door_codes_schema.py)
- Step 10 bites, SQLite and PostgreSQL: all 8 `BITE FAILS AS EXPECTED`, `ALL BITES CAUGHT`; `git diff HEAD --stat` empty afterwards
- Step 11: `context lint: OK`

## 3. Section 7 acceptance

- [x] diff stat lists the four App files plus the task doc (report added)
- [x] SQLite 22 / 536 / ruff; PostgreSQL 22 and 535 + 3 skipped (see deviations)
- [x] ALL BITES CAUGHT on both databases, tree clean
- [x] Lint OK

## 4. Deviations

- Commits per step (`1173c step 2`, `step 3`, `step 4-5`) and a report commit, not the brief's single step 8 commit. Commits are not amended or squashed.
- Step 1 `git checkout -b` skipped: the branch already existed (the executor brief says so).
- The brief's step 9 expects `389 passed, 3 skipped` for a narrower selection (no smart_locks_page or sm_* files). I ran the step 7 selection on PostgreSQL: `535 passed, 3 skipped`.
- Bite script written to the scratchpad, not /tmp (per the executor brief).
- Brief helper scripts were extracted from the brief text and run unchanged.

## 5. Questions

None.

## 6. Owner steps left

1. Open the PR when checks are green, including test-postgres and test-postgres-full, then merge with `scripts/merge-pr-on-green.sh`.
2. Orchestrator: context lint WARN says status.md is behind the App commits (not this brief's work).
