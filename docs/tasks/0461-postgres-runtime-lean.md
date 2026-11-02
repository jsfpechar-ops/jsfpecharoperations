# 0461: PostgreSQL runtime from #592, reviewed fixes, self-hosted kit removed
Status: done
Depends on: none | Base commit: head of `feat/postgresql-runtime-and-cutover-kit` (PR #592) | Branch: task/0461-postgres-runtime-lean
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Turn PR #592 into a mergeable runtime-only change: SQLite stays the default, PostgreSQL is active only with `UBYHOST_DATABASE_URL`. Remove the self-hosted pgBackRest/cutover kit (owner decision D1: managed PostgreSQL), apply the review's should-fix items, delete the dead helpers. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) steps 5–6. Review findings: [0461-review](0461-review-report.md).
## 2. Context
Review verdict: no blocker in the runtime half; startup fails fast on an unreachable URL, transfer is all-or-nothing with per-table typed hashes, tenancy `IS ?` maps to `IS NOT DISTINCT FROM`, every write takes the advisory writer lock. The ops half (pgBackRest, Docker postgres image, cutover state machine, key bundles, roles) was never executed and is dead weight with a managed database. CI now has a `test-postgres` job (#596) that runs `App/tests/test_db_postgres.py` against a real PostgreSQL 17 and fails on any skip.
## 3. Files
Start: `git checkout -b task/0461-postgres-runtime-lean origin/feat/postgresql-runtime-and-cutover-kit`.
Delete (git rm): `App/scripts/create_postgres_cutover_snapshot.py`, `App/scripts/postgres_cutover_transfer.sh`, `App/scripts/postgres_key_bundle.py`, `App/tests/test_postgres_operations_scripts.py`, `deploy/lightsail/docker-compose.postgres.yml`, `deploy/lightsail/postgres/` (whole directory), `deploy/lightsail/scripts/postgres-*.sh` (all 11), `docs/plans/postgresql/owner-cutover-runbook.md`, `docs/tasks/0456-review-report.md`.
Revert to `origin/main` (`git checkout origin/main -- <path>`): `App/scripts/backup_data.sh`, `deploy/lightsail/.env.example`, `deploy/lightsail/.gitignore`, `deploy/lightsail/caddy/Caddyfile.acme`, `deploy/lightsail/caddy/Caddyfile.cloudflare`, `deploy/lightsail/docker-compose.yml`, `deploy/lightsail/scripts/backup.sh`, `deploy/lightsail/scripts/deploy.sh`, `deploy/lightsail/scripts/restore.sh`, `docs/context/status.md`.
Edit: `App/app/config.py`, `App/app/db_postgres.py`, `App/app/db.py`, `App/scripts/sqlite_to_postgres.py`, `App/scripts/pg_schema.py`, `App/tests/test_db_postgres.py`, `docs/ENVIRONMENT.md` (one section for `UBYHOST_DATABASE_URL`), `docs/tasks/0455-review-report.md` (one line: ops half removed, see 0461).
## 4. Steps
1. Deletions and reverts above. Then `grep -rn "pgbackrest\|postgres-cutover\|key_bundle\|cutover_snapshot\|_record_backup_receipt\|authority marker\|UBYHOST_POSTGRES_" App deploy docs/ENVIRONMENT.md` and remove every remaining reference (code, env var, doc line). If a config variable exists only for the removed kit, delete it.
2. TLS: in `config.py` `_postgres_target`, when the host is a hostname (not an absolute socket directory), require `sslmode` to be `verify-full` or `require`; otherwise raise `RuntimeError("UBYHOST_DATABASE_URL over TCP needs sslmode=verify-full (or require)")`. Socket URLs stay as they are. Add two tests (missing sslmode rejected; `verify-full` accepted; socket URL without sslmode accepted).
3. Timeouts: in `db_postgres.connect`, pass `connect_timeout=10` and `options="-c statement_timeout=60000"` to `psycopg.connect` (keep any options already present). One test asserts both appear in the conninfo or connection kwargs.
4. Dead code: delete `_typed_column_kinds` and the unused argument of `_validate_pg_values` in `sqlite_to_postgres.py`; `_begin_immediate`, `current_schema()`, unused `PostgresCursor.fetchmany` in `db_postgres.py` (check callers with grep first; keep anything that is called); `database_label()` in `config.py` if it only returns `DB_BACKEND` (replace callers); `_record_backup_receipt` and the pgBackRest path in `pg_schema.py`.
5. `ruff check app scripts tests --select E9,F63,F7,F82,F401,F841`.
6. Run the SQLite rows: `tests/test_migrations.py tests/test_db_*.py` (PG module skips locally: expected, say so). CI runs the 45 PG tests.
## 5. Do not touch
`App/app/db.py` transaction logic beyond what step 4 names; the frozen `SCHEMA`/`ADDED_COLUMNS`; `invoices.py`; routes; `App/app/migrations/`.
## 6. Commands
`cd App && .venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30`; `.venv/bin/ruff check app scripts tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -10`; `python3 scripts/context_lint.py | tail -3` from the repo root.
## 7. Acceptance
No file under `deploy/lightsail/postgres/`, no `postgres-*.sh`, no pgBackRest string anywhere in the repo. Tests and ruff pass. The branch diff against `main` touches only `App/` runtime, `App/scripts/{pg_schema,sqlite_to_postgres,reencrypt}.py`, `App/tests`, requirements, `docs/ENVIRONMENT.md`, and the 0455/0461 docs.
## 8. Stop and ask
Stop if a runtime file imports anything from the deleted scripts, or if removing a helper changes a test's behaviour in a way you cannot explain.
## 9. Report
`docs/tasks/0461-report.md`: files deleted and reverted, the three fixes with line refs, dead helpers removed, test and ruff tails.
