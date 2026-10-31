# 0469: the SQLite→PostgreSQL transfer accepts any column order
Status: review
Depends on: 0468 (same branch) | Base commit: origin/task/0468-transfer-litestream-tables | Branch: task/0468-transfer-litestream-tables
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 40k tokens
## 1. Objective
The production SQLite file is old: many columns reached it through `ALTER TABLE ... ADD COLUMN` (`ADDED_COLUMNS` in `App/app/db.py`), so they sit at the end of their table. The frozen schema (`db._expected_sqlite_columns()`) declares 55 of them inline, so a fresh database has a different column order in 9 tables (user_account, legal_entity, apartment, reservation, guest, alert, reservation_claim, console_mail_log, invoice). Today the transfer compares column lists in order and would stop production with `source schema drift at <table>`. Column order carries no data. The transfer must compare column names as sets and verify with one shared order.
## 2. Context
- `App/scripts/sqlite_to_postgres.py`: in `transfer()`, `if _table_columns(source, table) != [c[0] for c in expected[table]]` raises the drift error. In `reconcile()`, `if columns != target_columns` raises `column mismatch`, and both `table_digest` calls use `columns` (source order). The copy already inserts by column name, so it needs no change.
- Tests: `App/tests/test_db_postgres.py`, `test_transfer_refuses_source_schema_drift` (line ~1279) is the model; it must keep passing (an extra column is still drift).
## 3. Files
Edit: `App/scripts/sqlite_to_postgres.py` (`transfer` drift check, `reconcile`), `App/tests/test_db_postgres.py` (one test). Write `docs/tasks/0469-report.md`. Nothing else.
## 4. Steps
1. `transfer()` drift check: compare `sorted(...)` of both lists instead of the lists. Same message.
2. `reconcile()`: compare `sorted(columns) != sorted(target_columns)` (same message), then pass `target_columns` to both `table_digest` calls, so source and target hash the same column order.
3. Test `test_transfer_accepts_a_different_column_order`: copy `transfer_workspace["source"]`; in the copy, read `SELECT id, guest_message FROM apartment`, run `ALTER TABLE apartment DROP COLUMN guest_message`, `ALTER TABLE apartment ADD COLUMN guest_message TEXT`, write the saved values back by id, commit. Assert `guest_message` is now the last column (`PRAGMA table_info`). Call `_reset_public_schema()`, run the transfer as `test_transfer_skips_litestream_tables` does, assert return code 0 and `copied-and-verified OK` in stdout, and that the report's `apartment` entry has `match` true.
## 5. Do not touch
`App/app/db.py`, `deploy/`, the 0468 changes, anything outside §3.
## 6. Commands
From `App/`: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test .venv/bin/python -m pytest tests/test_db_postgres.py -q --tb=short -x 2>&1 | tail -15` (0 skipped). From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
The new test passes; every existing test in the file is unchanged and green, including the drift test.
## 8. Stop and ask
Stop if any existing test changes result.
## 9. Report
`docs/tasks/0469-report.md`: the pytest tail and the `git diff --stat origin/main` output.
