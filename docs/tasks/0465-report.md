# 0465a report: goose baseline, Python reader, startup check

Status: review

Part a only. Part b (goose binary in CI, `test-postgres` goose step, LIGHTSAIL and owner lines) is not started.

## Files
- New: `App/migrations_pg/00001_baseline.sql` (4216 lines), `App/tests/test_goose_migrations.py`.
- Edited: `App/app/db.py` (goose helpers, goose step in `apply_postgresql_schema`, goose table excluded from the table list, pending check and baseline adoption in `validate_postgres_schema`), `App/scripts/pg_schema.py` (plan, check, apply output), `deploy/lightsail/scripts/pg-cutover.sh` (`pg_schema_apply` after the rehearsal and cutover `--verify-only`), `App/tests/test_migrations.py` (`test_python_runner_is_frozen`), `docs/context/rules.md` (Database bullet), `docs/tasks/0465-goose-migrations.md` (Status).

## Tests
- PostgreSQL (`UBYHOST_TEST_DATABASE_URL` on 127.0.0.1:5432/ubyhost_test): `60 passed, 10 skipped in 31.14s`. The 10 skips are the `sqlite_only` tests in `test_migrations.py`, deselected on PostgreSQL per section 10.
- SQLite (both env vars unset): `16 passed, 54 skipped in 2.27s`. The PostgreSQL tests skip with their reason.
- `bash -n deploy/lightsail/scripts/pg-cutover.sh`: exit 0.
- `python3 scripts/context_lint.py`: OK.

## Step 3 (baseline)
- Schema-only dumps of the Python-built `ubyhost_test` and the goose-built `ubyhost_test_goose` are identical: no diff output. `pg_schema.py check` on the goose database: `check OK ... version=33, tables=67`.

## Deviations
1. pg_dump 16.15 writes `\restrict` and `\unrestrict` psql lines with a random key per dump. They are removed from the baseline file and filtered out of the diff. Goose cannot run them.
2. `goose_files()` and `_goose_up_statements()` do not need PostgreSQL, because test (a) must run on SQLite. `goose_applied`, `_goose_ensure_table`, `goose_pending` and the baseline adoption raise outside PostgreSQL.
3. `postgres_schema_status` leaves `goose_db_version` out of its table list. Otherwise the existing test sees 68 tables instead of 67, and `zz_extra` counts as two extra tables. Test (d) asserts that `extra_tables` rises by exactly 1.
4. Step 7a: adoption runs when the status is current and version 1 is pending. It inserts `(1, true)` only if `goose_db_version` does not exist, in one transaction, then the status is read again.
5. `test_goose_migrations.py` imports `test_db_postgres` for the skip guard, `TARGET` and `_reset_public_schema`. It does not import that module's autouse fixture.
6. `pg_schema_apply` in the cutover script has no `| tail`, so a failure is seen by `|| die` and `|| fail_cutover`.
7. `ubyhost_test_goose` is left with an empty `public` schema.

## Questions and owner steps
- Question: does the Docker image copy `App/migrations_pg/`? The Dockerfile was not checked in this part.
- Owner steps left for part a: none.
