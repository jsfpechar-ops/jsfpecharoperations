# 0461 report: PostgreSQL runtime lean (executor: Haiku 5.5)

Branch `task/0461-postgres-runtime-lean` (from `feat/postgresql-runtime-and-cutover-kit`).
Commits: `remove self-hosted kit` (deletions and reverts), `review fixes and dead code` (fixes, dead code, docs, this report).

## Files
- Deleted: 23 (3 App/scripts cutover/key files, App/tests/test_postgres_operations_scripts.py, docker-compose.postgres.yml, deploy/lightsail/postgres/ (5 files), 11 scripts/postgres-*.sh, owner-cutover-runbook.md, 0456-review-report.md).
- Reverted to main: 10 (App/scripts/backup_data.sh, deploy/lightsail/.env.example, .gitignore, caddy/Caddyfile.acme, caddy/Caddyfile.cloudflare, docker-compose.yml, scripts/backup.sh, deploy.sh, restore.sh, docs/context/status.md).
- Edited: App/app/config.py, App/app/db_postgres.py, App/scripts/sqlite_to_postgres.py, App/scripts/pg_schema.py, App/tests/test_db_postgres.py, docs/ENVIRONMENT.md (new section "Database (PostgreSQL, optional)"), docs/tasks/0455-review-report.md (one line), docs/tasks/0461-postgres-runtime-lean.md (Status: review).

## The three fixes
1. TLS: `App/app/config.py:~84` `_postgres_target` refuses a TCP URL unless `sslmode` is `verify-full` or `require`. Socket URLs unchanged.
2. Timeouts: `App/app/db_postgres.py` `connect()` passes `connect_timeout=10` and `options` with `-c statement_timeout=60000`, keeping any `options` already in the URL.
3. Tests: new `test_tcp_url_without_verified_tls_is_rejected` (missing, disable, prefer) and `test_connect_sets_timeouts_and_keeps_url_options` in `App/tests/test_db_postgres.py`. Existing TCP URLs in that file now carry `sslmode=verify-full`.

## Dead code removed
`sqlite_to_postgres.py`: `_typed_column_kinds`; unused `columns` arg of `_validate_pg_values`. `db_postgres.py`: `PostgresCursor.fetchmany`, `current_schema()`. `pg_schema.py`: `record-backup` action, `_record_backup_receipt`, `_status_ok`, `--stanza`, unused imports.

## Kept (called, or outside this brief)
- `_begin_immediate` (db_postgres.py, called in the writer-lock path).
- `database_label()` (called from `App/app/main.py:129`, a file the brief does not name).
- Authority marker in `config.py` (`assert_database_authority` runs at startup from db.py): live runtime check, not kit code.

## Tests and lint
- `App/.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py -q --tb=short -x -rs`: `20 passed, 49 skipped in 6.82s`. Skips are the PostgreSQL module (no server here; expected). The new PG tests were not run.
- `ruff check app scripts tests --select E9,F63,F7,F82,F401,F841`: one hit, `App/scripts/guide_import_eval.py:14` (unused `os`). Not in this diff (same on main). Not touched.
- `python3 scripts/context_lint.py | tail -3`: see the commit log / final report.

## Deviations and owner questions
1. Acceptance "no pgBackRest string anywhere" is not met. Left in place (not named in the brief): `docs/plans/postgresql/ubyhost-handoff/` (old patches and handoff docs), `docs/context/decisions.md`, `docs/tasks/0456-postgresql-cutover-and-recovery.md`, `App/scripts/reencrypt.py` (`--backup-reference` reads the receipt that `record-backup` used to write, so that PG path now has no producer; help text names pgBackRest). Owner decision: delete the handoff archive, and decide reencrypt's PG backup-reference path.
2. TLS rule: CI workflow is not on this branch (no `UBYHOST_DATABASE_URL` in `.github`). If the CI `test-postgres` job uses a TCP URL, it now needs `sslmode=require` or a socket URL, and the server needs SSL for `require`. Check before merge.
3. The module docstring example in `test_db_postgres.py` now shows `sslmode=require`.

## Owner steps left
- Decide item 1 and item 2 above before merge.
- Merge only through `scripts/merge-pr-on-green.sh`.
