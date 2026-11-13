# 1173e report

Status: review

## 1. Files changed (`git diff e8c30e72 --stat`)

- App/app/door_codes.py: the revive skips only when `not ttlock.allowed_for(owner)`; a broken lock account now deletes the expired row so `_alert_delayed` raises `door_code_delayed` with `reason=not_set_up`.
- App/tests/test_issue_queue_starvation.py: parametrized plan/account test split into a plan-only test (kept) and a broken-account test (deleted, card raised); import adds `alerts`.
- docs/tasks/1173e-revive-broken-account.md: `Status: todo` to `Status: review`.
- docs/tasks/1173e-report.md: this report.

## 2. Commands (last lines of output)

Baseline before edits: `pytest tests/test_issue_queue_starvation.py` (SQLite)
```
...................   [100%]
19 passed in 0.87s
```

After step 2 (SQLite): `19 passed in 0.89s`. Diff stat: `2 files changed, 25 insertions(+), 15 deletions(-)`.

Revert bite, SQLite:
```
assert 0 == 1
FAILED tests/test_issue_queue_starvation.py::test_a_broken_lock_account_deletes_the_expired_row_and_the_host_is_told
1 failed, 18 passed in 1.04s
```

Revert bite, PostgreSQL (ubytest):
```
assert 0 == 1
FAILED tests/test_issue_queue_starvation.py::test_a_broken_lock_account_deletes_the_expired_row_and_the_host_is_told
1 failed, 18 passed in 4.88s
```

Five files, SQLite:
```
88 passed in 1.82s
```

`scripts/pg_schema.py apply --expect-database ubytest`:
```
PostgreSQL schema apply OK: database=ubytest, version=45, tables=71, goose=16.
```

Five files, PostgreSQL (ubytest):
```
88 passed in 18.97s
```

Ruff (`--select E9,F63,F7,F82,F401,F841`):
```
All checks passed!
```

Context lint: see section 6 (run after this report was written).

## 3. Acceptance (section 7 of the brief)

- [x] `git diff e8c30e72 --stat` lists door_codes.py, test_issue_queue_starvation.py, the brief and the report.
- [x] 19 passed (one file) and 88 passed (five files) on SQLite and PostgreSQL; ruff All checks passed.
- [x] Bite: old check restored gives `1 failed, 18 passed` on both databases; `git diff HEAD --stat` empty afterwards.
- [ ] `context lint: OK`: pending, see section 6.

## 4. Deviations

- Step 1: the branch `task/1173e-revive-broken-account` already existed and was checked out in the worktree, so no `git checkout -b` was run.
- Step 2: the replacements were made with the edit tool (old text asserted unique by the tool), not by `git apply`. Result matches the brief diff.
- Commit message: `1173e step 2` (executor convention `NNNN step k`), not the message suggested in the brief.
- The revert bite was not committed; the file was restored with `git checkout HEAD --` and the tree was clean before the next commit.

## 5. Questions

None.

## 6. Owner steps left

1. Open the PR from `task/1173e-revive-broken-account` when the checks are green, including test-postgres and test-postgres-full.
2. Merge with `scripts/merge-pr-on-green.sh`.
