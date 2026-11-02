# 0461 report: PostgreSQL runtime lean (executor: Haiku 5.5)

Branch `task/0461-postgres-runtime-lean` (from `feat/postgresql-runtime-and-cutover-kit`).
Commits: `remove self-hosted kit`, `review fixes and dead code`, `review fixes: loopback TLS exemption, reencrypt receipt removal`, `remove stale PostgreSQL handoff bundle`.

## Files
- Deleted: 23 kit files (cutover/key scripts, operations test, postgres compose, deploy/lightsail/postgres/, 11 postgres-*.sh, cutover runbook, 0456 review report), plus the handoff bundle docs/plans/postgresql/ubyhost-handoff/.
- Reverted to main: 10 shared deploy, backup and status files.
- Edited: App/app/config.py, App/app/db_postgres.py, App/scripts/sqlite_to_postgres.py, App/scripts/pg_schema.py, App/scripts/reencrypt.py, App/tests/test_db_postgres.py, docs/ENVIRONMENT.md (new "Database (PostgreSQL, optional)" section), docs/tasks/0455-review-report.md, docs/tasks/0452-0454-integration-report.md (link to the removed bundle), docs/tasks/0456-postgresql-cutover-and-recovery.md (Status: replaced), docs/tasks/0461-postgres-runtime-lean.md (Status: review).

## The three fixes
1. TLS: App/app/config.py ~line 79, `_postgres_target`. A TCP URL to a non-loopback host needs sslmode=verify-full or require. Loopback (localhost, 127.0.0.1, ::1) and socket URLs are exempt, for the CI service container.
2. Timeouts: App/app/db_postgres.py `connect()`: connect_timeout=10, options "-c statement_timeout=60000", keeping URL options.
3. Tests in App/tests/test_db_postgres.py: remote TCP without sslmode rejected (parametrized); loopback URL accepted; connect timeouts and options checked. Existing TCP URLs carry sslmode=verify-full.

## Dead code removed
sqlite_to_postgres.py: `_typed_column_kinds`, unused `columns` arg of `_validate_pg_values`. db_postgres.py: `PostgresCursor.fetchmany`, `current_schema()`. pg_schema.py: `record-backup`, `_record_backup_receipt`, `_status_ok`, `--stanza`. reencrypt.py: `--backup-reference` and its receipt-reading code (no producer), plus an unused import.

## Kept
`_begin_immediate` (called), `database_label()` (called from App/app/main.py:129), the authority marker in config.py (live startup check).

## Tests and lint
- `App/.venv/bin/python -m pytest tests/test_data_keys.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x`: `38 passed, 50 skipped`. Skips are the PostgreSQL module (no server here). The new PG tests were not run.
- Ruff (brief selectors) on changed files: all checks passed. Repo-wide, one pre-existing F401 in App/scripts/guide_import_eval.py (on main, untouched).
- `python3 scripts/context_lint.py`: OK.

## Owner steps left
- Merge only through `scripts/merge-pr-on-green.sh`.
- Confirm the CI test-postgres job (not on this branch) uses loopback or sslmode for TCP.
