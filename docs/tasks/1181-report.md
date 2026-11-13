# 1181 report: NULL order in due-row queries (re-verified)

Status review: the earlier report was invalid because the step-5 commit had reverted the ORDER BY fix (a bite checkout got committed). fa9b5d0c restored it. This report re-verifies on HEAD fb1598ef.

## Files changed (since eacdb305, App/app)

```
 App/app/admin_ops.py  | 3 ++-
 App/app/door_codes.py | 4 ++--
 2 files changed, 4 insertions(+), 3 deletions(-)
```

## Commands (last lines)

1. `pytest tests/test_null_order_portability.py tests/test_admin_operations.py`, SQLite: `11 passed in 1.64s`
2. Test-map set (door_code, ttlock, smart_locks_page, admin_operations, null_order_portability), SQLite: `387 passed, 2 skipped in 9.59s` (the 2 skips are Playwright browser tests; playwright not installed)
3. PostgreSQL (`localhost:5432`, accepting connections; schema already present, `pg_schema.py apply` not run): `11 passed in 4.71s`
4. Bite, source reverted to eacdb305:
   - PostgreSQL: `3 failed, 8 passed in 4.87s`
     - FAILED test_issue_due_takes_a_new_row_before_due_retries
     - FAILED test_due_queries_put_null_next_attempt_first
     - FAILED test_a_never_checked_feed_is_listed_before_stale_ones
   - SQLite: `1 failed, 1 passed in 0.34s`
     - FAILED test_due_queries_put_null_next_attempt_first
   - Restored with `git checkout HEAD -- ...`; `git status --short` empty, `git diff HEAD --stat` empty.
5. ruff `--select E9,F63,F7,F82,F401,F841 app tests`: `All checks passed!`

## Bite result

- SQLite: FAIL on old code, PASS on fix (1 of 2 tests catches it).
- PostgreSQL: FAIL on old code (3 of 3 catch it), PASS on fix.

## Notes

- Commit trailer: the brief asks for `Co-Authored-By: Claude Opus 5.5`. This run is Haiku 5.5, and the session attribution reminder says Haiku 5.5, so the trailer uses Haiku 5.5. Change it if the owner wants Opus.
- No push, no rebase, no amend.
