# 0468 report: transfer skips Litestream tables and names other differences

## Files changed
- `App/scripts/sqlite_to_postgres.py`: `app_tables()` also excludes `_litestream_%` tables (`ESCAPE '\'`); the table-set check in `transfer()` appends `(extra: [...], missing: [...])` names.
- `App/tests/test_db_postgres.py`: `test_transfer_skips_litestream_tables`, `test_transfer_names_an_unknown_table`.
- `docs/tasks/0468-transfer-litestream-tables.md`: Status set to `review`.

## Commands
- PostgreSQL, `-k transfer`: `11 passed, 41 deselected in 13.52s`
- PostgreSQL, whole file: `52 passed in 23.89s`
- SQLite (no `UBYHOST_TEST_DATABASE_URL`): `52 skipped in 0.12s`
- `python3 scripts/context_lint.py`: `context lint: OK` (warning only: App/ touched after last status.md update; orchestrator updates status at review)

## New error message
`source table set differs from the supported application schema (extra: ['legacy_stuff'], missing: [])`

## Section 7
- [x] Both new tests pass on PostgreSQL
- [x] Other transfer tests unchanged and green
- [x] Unknown-table message names the table

## Deviations
- Steps 1 and 2 were committed as `0468 step 1` and `0468 step 2`. The step-1 commit already contains both edits, so the step-2 commit is empty (`--allow-empty`). History only, no content impact.
- Tests were placed before `test_transfer_refuses_an_unsupported_source_schema_version`. The litestream test resets the target and re-copies, as the copy test does.

## Questions
None.

## Owner steps left
None. Orchestrator: update docs/context/status.md at review.
