# 0468: the SQLite→PostgreSQL transfer ignores Litestream's bookkeeping tables and names any other difference
Status: todo
Depends on: nothing | Base commit: main | Branch: task/0468-transfer-litestream-tables
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 40k tokens
## 1. Objective
The production rehearsal on 2026-10-31 stopped with `source table set differs from the supported application schema`. The production file holds exactly two tables the frozen schema does not know: `_litestream_seq` and `_litestream_lock`, written by Litestream (the replication sidecar) into the same SQLite file. They are not application data and must not be copied. The transfer must skip them, and when any other table differs it must say which.
## 2. Context
- `App/scripts/sqlite_to_postgres.py`: `app_tables()` lists the source tables (`name NOT LIKE 'sqlite_%'`); `transfer()` compares that set with `db._expected_sqlite_columns()` and raises the message above. Every later step (`_table_columns`, `_validate_pg_values`, copy, `reconcile`) takes its table list from `app_tables()`, so one exclusion there covers the copy and both verify passes.
- Tests: `App/tests/test_db_postgres.py`, fixture `transfer_workspace` (grep `def transfer_workspace`); `test_transfer_refuses_source_schema_drift` (line ~1279) shows how a source file is altered before a run and how the failure message is asserted. They run only with `UBYHOST_TEST_DATABASE_URL` (local server: `postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test`).
## 3. Files
Edit: `App/scripts/sqlite_to_postgres.py` (`app_tables`, the table-set check in `transfer`), `App/tests/test_db_postgres.py` (two tests). Nothing else.
## 4. Steps
1. `app_tables()`: also exclude names starting with `_litestream_` (`AND name NOT LIKE '\_litestream\_%' ESCAPE '\'`; keep the existing `sqlite_%` clause).
2. The table-set check in `transfer()`: keep the exception type and the leading text, and append the names: `f"source table set differs from the supported application schema (extra: {sorted(set(tables) - set(expected))}, missing: {sorted(set(expected) - set(tables))})"`. Names only, never values.
3. Test `test_transfer_skips_litestream_tables`: in the source file create `_litestream_seq (id INTEGER PRIMARY KEY, seq INTEGER)` with one row and `_litestream_lock (id INTEGER)`, run the transfer exactly as `test_transfer_copies_and_verifies_every_table` does, assert it succeeds, the report has no key starting with `_litestream`, and the PostgreSQL target has no table named `_litestream_seq` (`to_regclass`).
4. Test `test_transfer_names_an_unknown_table`: create `legacy_stuff (id INTEGER)` in the source, assert the failure message contains `extra: ['legacy_stuff']`.
## 5. Do not touch
`App/app/db.py`, `deploy/`, anything outside §3.
## 6. Commands
From `App/`: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test .venv/bin/python -m pytest tests/test_db_postgres.py -q --tb=short -x -k transfer 2>&1 | tail -15`, then the whole file the same way (0 skipped). Then `.venv/bin/python -m pytest tests/test_db_postgres.py -q 2>&1 | tail -3` without the variable (all skip). From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
Both new tests pass on PostgreSQL; every other transfer test unchanged and green; the message for an unknown table names it.
## 8. Stop and ask
Stop if any existing transfer test changes result, or if `app_tables` is used anywhere the brief does not list (grep it).
## 9. Report
`docs/tasks/0468-report.md`: the pytest tails and the new error message text.
