# 0469 report: transfer accepts any column order

- `transfer()` compares column names as sets; the drift error now names extra and missing columns (names only).
- `reconcile()` compares names as sets and hashes source and target in the target's column order.
- New test `test_transfer_accepts_a_different_column_order` (apartment.guest_message moved to the end, as in an old ALTER-grown file). It fails on the old code and passes now.
- `tests/test_db_postgres.py` on PostgreSQL 16: 53 passed, 0 skipped. Without the variable: 53 skipped.
- Why: 55 columns in `ADDED_COLUMNS` are also inline in `SCHEMA`, so an old production file has a different column order in 9 tables than a fresh one.
