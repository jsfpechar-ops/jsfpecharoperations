# 0470: the SQLite→PostgreSQL transfer skips seven retired stay-fee columns, only while they hold defaults
Status: review
Depends on: 0469 (merged) | Base commit: main f536784 | Branch: claude/project-thread-rzmxxx
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 40k tokens
## 1. Objective
Rehearsal 2 (2026-10-31 22:57Z) refused with `source schema drift at apartment (extra: ['stay_fee_cash', 'stay_fee_payment_link', 'stay_fee_policy'], missing: [])`. A read-only check of every production table found no missing column and exactly seven extra ones, left by an old stay-fee build (`docs/archive/plans/PLAN_POPLATEK_Z_POBYTU.md`) that no current code reads:

| column | production values |
|---|---|
| apartment.stay_fee_cash | 8 rows, all `1` (its default) |
| apartment.stay_fee_payment_link | all NULL |
| apartment.stay_fee_policy | 8 rows, all `'on'` (its default) |
| guest.fee_claim | all NULL |
| reservation.stay_fee_paid_amount_czk, reservation.stay_fee_paid_at, reservation.stay_fee_rate_czk | all NULL |

They carry no data. The transfer must leave them out, and must refuse if any of them ever holds a value other than NULL or its default, so nothing real can be dropped.
## 2. Context
`App/scripts/sqlite_to_postgres.py`: `_table_columns()` (line ~156) feeds the drift check in `transfer()`, the copy loop and `reconcile()`; filtering there covers all three. Tests: `App/tests/test_db_postgres.py`, model `test_transfer_accepts_a_different_column_order` and `test_transfer_names_an_unknown_table`.
## 3. Files
Edit: `App/scripts/sqlite_to_postgres.py`, `App/tests/test_db_postgres.py`. Write `docs/tasks/0470-report.md`. Nothing else.
## 4. Steps
1. Under `REPORT_VERSION`, add a constant with a one-line comment (old stay-fee build, see this brief):
   `RETIRED_COLUMNS = {("apartment", "stay_fee_cash"): (1,), ("apartment", "stay_fee_payment_link"): (), ("apartment", "stay_fee_policy"): ("on",), ("guest", "fee_claim"): (), ("reservation", "stay_fee_paid_amount_czk"): (), ("reservation", "stay_fee_paid_at"): (), ("reservation", "stay_fee_rate_czk"): ()}` (the tuple lists the allowed non-NULL values).
2. `_table_columns()`: leave out names where `(table, name)` is in `RETIRED_COLUMNS`.
3. New `_check_retired_columns(source)`: for each entry whose column exists in the source (`PRAGMA table_info`), count rows `WHERE "col" IS NOT NULL` plus, when the allowed tuple is not empty, `AND "col" NOT IN (?, ...)` with the allowed values as parameters. If the count is above 0, raise `ValueError(f"retired column {table}.{col} holds data")`. Call it in `transfer()` right after the table-set check.
4. Test `test_transfer_skips_retired_columns_with_defaults`: copy the source, add the seven columns with `ALTER TABLE ... ADD COLUMN` (`stay_fee_cash INTEGER NOT NULL DEFAULT 1`, `stay_fee_policy TEXT NOT NULL DEFAULT 'on'`, the rest plain `TEXT` or `INTEGER`), `_reset_public_schema()`, run the transfer, assert return code 0 and `copied-and-verified OK`.
5. Test `test_transfer_refuses_a_retired_column_with_data`: same copy, add `apartment.stay_fee_payment_link TEXT`, set it to `'https://x'` on one row, assert return code 1, `retired column apartment.stay_fee_payment_link holds data` in stderr, and no report file.
## 5. Do not touch
`App/app/`, `deploy/`, anything outside §3.
## 6. Commands
From `App/`: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test .venv/bin/python -m pytest tests/test_db_postgres.py -q --tb=short -x 2>&1 | tail -15` (0 skipped). From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
Both new tests pass; every existing test in the file still passes.
## 8. Stop and ask
Stop if any existing test changes result.
## 9. Report
`docs/tasks/0470-report.md`: the pytest tail and `git diff --stat origin/main`.
