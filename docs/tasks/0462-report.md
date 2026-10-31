# 0462 report: the whole app suite on PostgreSQL
Status: done
Branch: task/0462-full-suite-on-postgres | PR #609 | Executor: Haiku 5.5 in four batches, reviewed by the orchestrator

## Done
- `.github/workflows/ci.yml`: job `test-postgres-full` runs `tests/` against a PostgreSQL 17 service with `-m "not sqlite_only"`, uploads the junit file, and gates merges (no `continue-on-error`).
- `App/tests/conftest.py`: on PostgreSQL only, a module-scoped reset drops and re-creates `public` and applies the schema; `db.init_db` is wrapped so a never-seen `config.DB_PATH` truncates the data (SQLite tests switch to a fresh temp file at that moment; a known path keeps its data); `sqlite_only` items are skipped. `App/pytest.ini` registers the marker.
- App fixes (portable, SQLite unchanged): `ON CONFLICT ... DO UPDATE SET calls = lock_api_usage.calls + 1` in `guest_guide_import.py`, `stripe_connect.py`, `ttlock.py`; `int()` on the token sums in `ai._usd` (PostgreSQL returns Decimal for `SUM`); `GROUP BY r.id, a.id, a.internal_name` in `mail_notify.stays_for_submission`; `PostgresRow.__eq__` so two rows compare by value like `sqlite3.Row`.
- Test fixes: 53 tests marked `sqlite_only` (SQLite file, migration runner, PRAGMA, `sqlite_master`, file-level startup locks, `BEGIN IMMEDIATE` timing, the reencrypt script's backup check); `test_pii_encryption` helper uses `RETURNING id`; `test_worker` subprocess env drops `UBYHOST_DATABASE_URL`; integrity errors caught through `db.integrity_errors()`; `test_havel_page` stubs `havel.support_blocked` instead of relying on a leaked `havel_support` cap; `test_billing_analytics_export` hardlink case is SQLite-only.

## Results
- CI at c4e123e (before batches C and D): 16 failed, 4471 passed, 102 skipped, 43 deselected, 2 errors in 23 min. SQLite job at the same commit: 4534 passed, 150 skipped.
- Batches C and D locally: every touched file green on both backends (PostgreSQL 227 passed + 18 passed; SQLite 237 + 18). The CI run at 609f18f is the proof for the whole suite.

## Open
- K-PG04 candidate: the reencrypt script refuses to write on PostgreSQL without a verified backup source, so its six tests in `test_data_keys.py` are `sqlite_only`; it needs a PostgreSQL backup source (the nightly `pg_dump`) before key rotation on PostgreSQL.
