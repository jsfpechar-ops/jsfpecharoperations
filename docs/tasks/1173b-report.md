# 1173b report

Status: review

## 1. Files (git diff 1d3f5816 --stat, App)

- App/app/door_codes.py: +16 (two alerts.resolve lines, _resolve_unverified_cards, one _phase call in reconcile)
- App/tests/test_door_code_unverified_card.py: new, 4 tests
- App/tests/test_admin_operations.py: docstring 1170 -> 1181
- App/tests/test_door_code_host_notices.py: docstring 1166 -> 1168
- docs/tasks/1173b-unverified-card-resolve.md: Status todo -> review
- docs/tasks/1173b-report.md: this file

## 2. Commands (last lines)

- Card tests, SQLite: `4 passed in 0.65s`
- Mapped tests, SQLite: `524 passed, 2 skipped in 17.14s` (2 skips: playwright not installed)
- Ruff E9,F63,F7,F82,F401,F841: `All checks passed!`
- Card tests, PostgreSQL: `PostgreSQL schema apply OK: database=ubytest, version=45`; `4 passed in 1.76s`
- Mapped tests, PostgreSQL: `377 passed, 3 skipped in 69.10s` (skips: 2 playwright, 1 sqlite_only)
- Bite C1 (no resolve in issue()): SQLite and PostgreSQL both `1 failed, 3 passed` (..._when_a_lost_code_is_issued_again). Restored, diff clean.
- Bite C2 (no resolve after move): SQLite and PostgreSQL both `1 failed, 3 passed` (..._when_a_move_makes_a_new_code). Restored, diff clean.
- Bite C3 (sweep never matches): SQLite and PostgreSQL both `2 failed, 2 passed` (..._when_the_stay_is_cancelled, ..._when_the_code_expires). Restored, diff clean.
- context_lint.py: `context lint: OK`

## 3. Section 7

- [x] diff lists the four App files of section 3 plus the two task docs
- [x] steps 5, 6, 7 green on SQLite; step 8 green on PostgreSQL
- [x] each bite fails the named tests on both databases; diff empty after each
- [x] lint OK

## 4. Deviations

- Preflight `git checkout -b` not run: the branch already existed and was checked out.
- Commits: steps 2, 3, 4 were committed one by one (`1173b step 2/3/4`) per executor rule; step 9 commit had nothing left to add.
- No push, no PR (orchestrator instruction).
- Grep for `1157` in the named test files: no matches, nothing to list.

## 5. Questions

- Two Playwright tests skip on SQLite and PostgreSQL because playwright is not installed in the worktree venv. Brief accepts this; executor rule says browser tests must have 0 skips. Not a UI change, so no browser test was required by the brief.

## 6. Owner steps left

1. Open the PR when checks are green, including test-postgres and test-postgres-full, and merge with `scripts/merge-pr-on-green.sh`.
