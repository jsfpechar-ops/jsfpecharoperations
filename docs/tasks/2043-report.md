# 2043 report: rollback schema prep also removes goose version 24

Status: review

## Files changed

- `deploy/lightsail/scripts/rollback-schema-prep.sh`: unset-URL WARNING on stderr; dry-run text; one transaction that also deletes goose row 24.
- `deploy/lightsail/scripts/deploy.sh`: `rollback()` prints `ERROR: schema rollback prep failed; old release may not start` on failure and does not exit.
- `App/tests/test_pg_backup_scripts.py`: dry-run test asserts the goose delete; new unset-URL test.
- `App/tests/test_pg_go_slot_script.py`: static test for the SQL, `ON_ERROR_STOP=1`, and the deploy error text.
- `docs/tasks/2043-report.md`: this report.

## Commands (section 6)

- `shellcheck -S error deploy/lightsail/scripts/*.sh`: SKIPPED, shellcheck is not installed in this environment.
- `bash -n deploy/lightsail/scripts/deploy.sh` (and rollback-schema-prep.sh after step 1): no output, pass.
- `App/.venv/bin/python -m pytest tests/test_pg_backup_scripts.py tests/test_pg_go_slot_script.py -q --tb=short -x -rs`:
  ```
  ........................................................................ [ 67%]
  ..................................                                       [100%]
  106 passed in 2.85s
  ```
  Result: 106 passed, 0 failed, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (only pre-existing WARN lines, no errors).

## Acceptance (section 7)

- [x] `DELETE FROM goose_db_version WHERE version_id = 24` appears 2 times in rollback-schema-prep.sh (dry-run line 26, real SQL line 31).
- [x] Real SQL is one `-c "BEGIN; ...; COMMIT;"` with `-v ON_ERROR_STOP=1`.
- [x] Unset URL prints the WARNING to stderr (covered by the new test).
- [x] deploy.sh prints the ERROR line on failure and does not exit (checked by reading the code and the static test; not exercised against a failing database).
- [x] §6 commands pass, except shellcheck (skipped, not installed).

## Deviations

- The brief file `docs/tasks/2043-rollback-schema-prep-goose-row.md` is not on this worktree's branch. It exists in commit e8d7a05 on `claude/nice-hawking-fw98ct` and in the main checkout. I read it from the main checkout and did not copy it into this branch.
- Commit trailer: the task said `Co-Authored-By: Claude Opus 5.5`, which is the trailer used; the executor model is Haiku 5.5.

## Questions

- None.

## Owner steps left

- Review the PR and merge with `scripts/merge-pr-on-green.sh` when ready. No secrets, servers, or deploys involved.
