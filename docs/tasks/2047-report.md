# 2047 report: backup transient-gap test flake

Status: review (partial, see Deviations)

## Files changed

- `App/tests/test_pg_backup_scripts.py`: two stub lines in `test_backup_waits_for_a_transient_gap_then_succeeds` replaced with the three-line marker-file version from brief §4 step 1.
- `docs/tasks/2047-backup-transient-gap-flake.md`: brief copied into the worktree.
- `docs/tasks/2047-report.md`: this report.

No other file changed. `backup.sh` untouched.

## Commands

- Flake loop (20 runs, `-k transient_gap`): `20 1 passed, 86 deselected`. Result: 20 passed, 0 failed.
- File run (`tests/test_pg_backup_scripts.py -q --tb=short -x`): `1 failed, 55 passed`, failing test `test_backup_fails_in_production_without_database_url_but_keeps_snapshot`. A later full run without `-x` gave `2 failed, 85 passed` and `1 failed, 86 passed` in other runs.
- Context lint (`python3 scripts/context_lint.py`): `context lint: OK`.
- Base comparison (`git show HEAD~1` copy of the test file, 3 runs): `87 passed`, `2 failed, 85 passed`, `1 failed, 86 passed`. The unpatched file also fails intermittently, with different tests each time.

## Acceptance (brief §7)

- [x] `grep -nF 'STUB_LOG.up'` shows 3 matches in one stub string.
- [x] The flake loop prints `20 1 passed`.
- [ ] The file run passes with 0 failed. Not met: other tests in the same file fail intermittently, on base and patched code alike.
- [x] Context lint passes.
- [x] `git diff --stat` shows only the test file plus the brief and report.

## Deviations

- Commit was made with the brief inside the same commit as the test edit, then split into separate commits (see Commits below).
- The worktree has no `App/.venv`; the main checkout venv `/home/user/jsfpecharoperations/App/.venv/bin/python` was used as instructed.
- No PR is opened (parent instruction: commit only, no push, no PR).

## Questions

- Which tests in `test_pg_backup_scripts.py` are flaky beyond 2047? Seen failing intermittently: `test_backup_fails_in_production_without_database_url_but_keeps_snapshot`, `test_pg_restore_file_form_streams_host_file_without_docker_cp`, `test_backup_dumps_postgres_only_when_running[1]`. The brief names only the transient-gap test, so these were not touched. A separate brief is needed for them.

## Owner steps left

- None for this brief. The file-level flake needs its own brief before the file run can be fully green.
