# WP18: Prepare a later Postgres move

Patch: `WP18-postgres-portability.patch`. It is stacked on WP16, so apply `WP16-data-key-multifernet.patch` first. The two touch neighbouring parts of `db.py` and the WP16 test file path.

## Summary

- **`db.insert` and RETURNING.** `db.insert` now uses `INSERT ... RETURNING id` instead of `lastrowid`. It returns `None` for the 6 tables that have no `id` column: `settings`, `codelist`, `invoice_sequence`, `submission_claim`, `reservation_claim` and `schema_migrations`. No caller uses that return value.
- **Other `lastrowid` sites.** The other 2 sites (`invoices._write_issued` and `stay_fee_filing` sealing) now use `RETURNING id` too. They read the result with `fetchall()`, so the statement finishes inside its transaction.
- **`db.execute` return value.** It now returns the row count instead of `lastrowid`. The row count means the same thing on both engines. The only caller that used the return value is `acceptance.backfill_from_audit`, which counts inserted rows. It works the same with the row count.
- **`INSERT OR` rewrites.** All 4 sites now use `ON CONFLICT`:
  - `submission_claim` (the send claim): `ON CONFLICT (guest_id) DO NOTHING`. The row count is still 1 for the winner and 0 for a second holder.
  - `codelist` upsert: `ON CONFLICT (kind, code) DO UPDATE` of every non-key column.
  - `legal_acceptance` (2 sites): `ON CONFLICT (user_account_id, document, version) DO NOTHING`.
- **Null-safe comparisons, all 67 sites in one commit:**
  - **Helper:** new `db.null_safe_eq(column)` replaces the bare `x IS ?`. It returns `"<column> IS ?"` on SQLite. Postgres needs `IS NOT DISTINCT FROM`, which then means changing one constant (`db.NULL_SAFE_EQ`).
  - **55 sites use the helper:** `db.update_if` plus 54 in 11 modules (access, mail, invoices, workspace_export, onboarding, stay_fee, dsr, routes/admin, routes/invoices, routes/stay_fees, routes/exports).
  - **12 sites now use plain `=`:** they are in `retention._delete_workspace`, where `owner_id` always comes from a `user_account.id` and is never NULL.
- **Numbered migrations:**
  - **Where they live:** files `App/app/migrations/NNNN_name.sql`, applied in order, each in its own `BEGIN IMMEDIATE` transaction together with its `schema_migrations` row. The "already applied" check runs inside the lock, so two processes starting together apply a file once. A failing file rolls back completely and is not recorded.
  - **Baseline:** version 1 is the existing `SCHEMA` plus `ADDED_COLUMNS`. Both are now frozen, and comments say so.
  - **Existing databases:** they still go through the old idempotent pass first. They are then marked at version 1, which is the current version, with no schema change.
  - **Tests:** `init_db()` keeps working unchanged for tests.
  - **Shipped files:** no migration file ships yet. The directory holds only a `.gitkeep`.
- **AGENTS.md:** new section "Database access", with rule 8 from the README plus the new conventions.

## Files changed

- `AGENTS.md`: new "Database access" rules section.
- `App/app/db.py`: `execute` returns the row count; `insert` uses RETURNING; `_TABLES_WITHOUT_ID`; `null_safe_eq`; migration runner (`migration_files`, `_statements`, `schema_version`, `apply_migrations`); `init_db` records the baseline and applies migrations.
- `App/app/migrations/.gitkeep`: the migrations directory.
- `App/app/invoices.py`, `App/app/stay_fee_filing.py`: `RETURNING id` instead of `lastrowid`.
- `App/app/reporting.py`, `App/app/codelists.py`, `App/app/acceptance.py`: `ON CONFLICT` instead of `INSERT OR`.
- `App/app/access.py`, `mail.py`, `invoices.py`, `workspace_export.py`, `onboarding.py`, `stay_fee.py`, `dsr.py`, `routes/admin.py`, `routes/invoices.py`, `routes/stay_fees.py`, `routes/exports.py`: `IS ?` changed to `db.null_safe_eq(...)`.
- `App/app/retention.py`: `IS ?` changed to `= ?` in `_delete_workspace`.
- `App/tests/test_migrations.py`: new tests (13).

## Tests added

`tests/test_migrations.py`:
- An empty database is created at the baseline, and a second `init_db` adds nothing.
- An existing pre-WP18 database (built from the current schema, with a data row) is marked at the current version with an identical schema, and the data is kept.
- An empty and an upgraded database end with the same schema.
- A numbered migration is applied once and recorded.
- An existing database gets later migrations on top of the baseline.
- A failing migration leaves nothing behind and is not recorded.
- A file numbered inside the baseline is refused.
- Non-migration files are ignored.
- `insert` returns ids, returns `None` for tables without `id`, and `execute` returns the row count.
- The send claim still refuses a second holder (first token kept).
- The codelist upsert keeps one row with the latest values.
- `null_safe_eq` matches NULL the way `IS` did.
- A guard test: no `INSERT OR`, no `.lastrowid` and no bare `x IS ?` left in `app/`.

## Test commands and results

From `/tmp/wp/wp16/App`, with WP16 and WP18 applied:
- Broad chunks:
  - `tests/test_[a-d]*.py`: 400 passed, 2 skipped.
  - `tests/test_[e-h]*.py`: 579 passed, 5 skipped, 1 failed.
  - `tests/test_[i-p]*.py`: 648 passed (includes the 13 new tests).
  - `tests/test_[q-s]*.py`: 415 passed, 1 failed.
  - `tests/test_[t-z]*.py`: 152 passed.
- The 2 failures are the same ones that fail on the untouched base:
  - `test_host_geometry`: Chromium cannot launch in this sandbox.
  - `test_stale_submission`: an order-dependent failure.
- `pytest -q tests/test_migrations.py tests/test_data_keys.py tests/test_pii_encryption.py tests/test_db_upgrade.py tests/test_endtoend.py`: 74 passed.
- `ruff check app tests tools scripts --select E9,F63,F7,F82,F401,F841`: all checks passed.
- The full suite was not run in ONE process, as CI does. It was run in chunks because of the time limit per call.

## Deviations from the spec and why

- **Null-safe helper:** `null_safe_eq` emits `IS ?`, not `IS NOT DISTINCT FROM`. SQLite only accepts `IS NOT DISTINCT FROM` from 3.39. The Render staging service uses Render's native Python runtime, whose system SQLite may be older. The helper makes the Postgres switch a one-line change without risking today's hosts. Behaviour is unchanged.
- **Baseline stays in code:** it is not moved into a SQL file. Moving `SCHEMA` and `ADDED_COLUMNS` into files would change how every existing database starts, for no gain now. Existing databases are marked at version 1 after the old idempotent pass, as the spec asks.
- **WP16 columns stay in the baseline:** the 4 `*_enc` columns from WP16 remain in `ADDED_COLUMNS` and do not get a migration file. A database that ran WP16 before WP18 has no `schema_migrations` table. If those columns were in an `ALTER TABLE` migration, it would fail there with "duplicate column".
- **`ON CONFLICT` behaviour differences:**
  - Unlike `OR IGNORE`, `DO NOTHING` does not swallow NOT NULL or CHECK failures. All values at these sites are constants or always set, so nothing changes in practice. A bad value would now raise instead of being silently dropped.
  - `codelist` had no cascades, references or triggers, so `DO UPDATE` and the old delete-plus-insert give the same rows. Only the rowid differs, and nothing reads it.
- **`db.execute` contract change:** it now returns the row count instead of `lastrowid` (see What Cursor must verify).

## What Cursor must verify or adapt when applying on the real main

- Grep main for any new `x IS ?`, `INSERT OR`, `lastrowid`, or use of `db.execute(...)`'s return value as an id. The guard test `test_no_sqlite_only_insert_variants_or_bare_is_comparisons_remain` fails on any of the first three.
- Any WP merged after this one that adds a column or table (for example WP19 `apartment_slug`) must add `App/app/migrations/0002_<name>.sql` instead of editing `SCHEMA` or `ADDED_COLUMNS`. Watch for migrations from different branches being given the same number.
- Check that production SQLite is 3.35 or newer (needed for RETURNING): `python -c "import sqlite3; print(sqlite3.sqlite_version)"` in the container. Debian bookworm `python:3.12-slim` ships 3.40.
- Rewritten f-strings in `routes/admin.py` and others: confirm no string that previously contained literal braces was broken. The rewrite escaped braces and the full suite passes.

## Manual steps for the owner

- None for deploy. The first start after deploy creates `schema_migrations` and records version 1.
- Before deploying, check the SQLite version on Render staging as above, if Render staging is still in use.
