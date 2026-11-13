# 1170 report: NULL order in due-row queries

Status: review

## Files changed

- App/app/door_codes.py: two ORDER BY lines (`_handle_cancellations` revoke batch, `_issue_due`)
- App/app/admin_ops.py: one ORDER BY (`feeds_needing_attention`), COALESCE repeated for PostgreSQL
- App/tests/test_null_order_portability.py: new, two tests
- App/tests/test_admin_operations.py: one test appended
- docs/tasks/1170-report.md: this file

Commits (oldest first): steps 1-2 (door_codes), step 3 (admin_ops), step 4 (new test file), step 5 (admin test). Each has the attribution trailers.

## Commands

1. `pytest tests/test_null_order_portability.py tests/test_admin_operations.py`, SQLite: `11 passed in 2.10s`
2. Test-map rows, SQLite: `385 passed, 2 skipped in 10.40s` (the 2 skips are the Playwright browser tests the brief allows)
3. `ruff check --select E9,F63,F7,F82,F401,F841 app tests`: `All checks passed!`
4. SQLite bite (source reverted to eacdb305): `FAILED tests/test_null_order_portability.py::test_due_queries_put_null_next_attempt_first`, `1 failed, 1 passed in 0.34s`. Restored, tree clean.
5. PostgreSQL with fix: `11 passed in 5.11s`. PostgreSQL bite (source reverted): `FAILED test_issue_due_takes_a_new_row_before_due_retries` (`assert 6 in [1, 2, 3]`), `FAILED test_due_queries_put_null_next_attempt_first`, `FAILED test_a_never_checked_feed_is_listed_before_stale_ones` (`assert [7] == [10]`); `3 failed, 8 passed`. Restored, tree clean. The schema was already present, so `pg_schema.py apply` was not run.
6. `python3 scripts/context_lint.py`: `context lint: OK` (with a WARN that the orchestrator should update status.md; not in scope here)

## Section 7 (acceptance)

- [x] Three ORDER BY lines match steps 1-3; `git diff --stat` for the code files shows 2 files, 4 lines changed
- [x] Commands 1-3 and 6 green; command 4 SQL-order test fails on the old code
- [x] Command 5 shown on PostgreSQL (3 fail on old code, pass on new)

## Deviations

- Bites: the fix was already committed, so `git stash push` had nothing to save. I used `git checkout eacdb305 -- <two files>` to revert, then `git checkout HEAD -- <two files>` to restore. Tree was clean after each.
- Command 2 ran with `-rs` added so skip reasons print.
- Attribution: the four task commits were rewritten (`git rebase --exec`) to add the Co-Authored-By and Claude-Session trailers. The rewrite also replayed a commit that was already on the branch, `docs(tasks): 1170-cont-1 (commands, bites, report)` (originally 11cad083, now 20064b68), and added the Haiku trailer. Its tree is unchanged.
- A pytest process from an earlier resumed run of this session (pid 4652, running in App/) was still active during the runs. It only runs tests. I did not stop it. `docs/tasks/1170-cont-1.md` came from that earlier run and refers to commits 3be43725..cc236aad, which are not this branch's hashes.

## Questions

- Should 1170-cont-1.md and the earlier run be cleaned up, or kept as the record?

## Owner steps left

- None for this task. Open the PR and merge via `scripts/merge-pr-on-green.sh` after green checks, including test-postgres and test-postgres-full (orchestrator/owner step, not run here).
