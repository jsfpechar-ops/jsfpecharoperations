# 0473: deploy.sh works when production runs on PostgreSQL, and applies goose migrations before start
Status: review
Depends on: 0465a (merged) | Base commit: main | Branch: claude/0473-deploy-on-postgres
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Production switched to PostgreSQL on 2026-10-31 23:56Z (`.env` has `UBYHOST_DATABASE_URL`; `/data/ubyhost.db` stays on the volume as the frozen rollback copy and must never be written). `deploy/lightsail/scripts/deploy.sh` still assumes SQLite. The first deploy after the cutover would stop at the "migration dry-run" (`PRAGMA integrity_check` against PostgreSQL), and after `up` the `migrate_encrypt_doc_fields.py` step queries `sqlite_master`. Every check that reads `/data/ubyhost.db` with `sqlite3` now reads a stale file. The deploy must check the live PostgreSQL data, apply pending goose migrations with the new image before the stack starts, and behave exactly as today on SQLite.
## 2. Context
- `deploy.sh` (read it all, about 260 lines): the missing-e-mail check (line ~80), the backup and row-count block (~90–127), the migration dry-run (~149–161), `up` (~165), the healthz rollback to `ubyhost:previous` (~190–215), the two backfills (~245–265), the post-deploy integrity and row-count check (~266–282).
- PostgreSQL mode = `UBYHOST_DATABASE_URL` non-empty after `source .env` (the same test `scripts/backup.sh` line 22 uses). `backup.sh` already writes `/data/backups/<stamp>/ubyhost-pg.dump.age` in that mode.
- Goose: `App/scripts/pg_schema.py apply --expect-database ubyhost` applies pending files from `App/migrations_pg/` in one transaction (`db.apply_postgresql_schema`). The app refuses to start while a goose file is pending (`db.validate_postgres_schema`). Goose files must be additive (old image keeps working) so the healthz rollback stays valid; add one line saying so to the Database section of `docs/context/rules.md`.
- The app's db layer runs the same SQL on both backends: `docker compose exec -T ubyhost python -c "from app import db; print(db.query_one('SELECT COUNT(*) AS n FROM guest')['n'])"`.
- `App/scripts/migrate_encrypt_doc_fields.py` `_open()` (line ~75–100) checks `config.DB_PATH` exists and queries `sqlite_master`; `App/scripts/backfill_legal_acceptance.py`: check it the same way.
## 3. Files
Edit: `deploy/lightsail/scripts/deploy.sh`, `App/scripts/migrate_encrypt_doc_fields.py`, `App/scripts/backfill_legal_acceptance.py` (only if it is SQLite-only), their tests in `App/tests/` (grep the script names), `docs/context/rules.md` (one line). Write `docs/tasks/0473-report.md`.
## 4. Steps
1. `deploy.sh`: after `source .env`, set `PG_MODE=1` when `UBYHOST_DATABASE_URL` is non-empty, else `0`.
2. Missing-e-mail check and the before/after row counts: run them through the app's db layer (`docker compose exec -T ubyhost python -c ...`) in both modes, so one code path serves SQLite and PostgreSQL. Keep the messages and the "count fell" rule.
3. Backup block: in PG mode check that `/data/backups/${BACKUP_STAMP}/ubyhost-pg.dump.age` exists, is non-empty and starts with `age-encryption.org/v1`; skip the SQLite `.backup` copy and `PRAGMA integrity_check`. SQLite mode unchanged.
4. Migration step: in PG mode replace the dry-run with `docker compose run --rm --no-deps -T --entrypoint python ubyhost scripts/pg_schema.py apply --expect-database ubyhost` (new image, before `up`); a failure prints "Goose apply failed." and exits 1 before the stack is touched. SQLite mode unchanged.
5. Post-deploy block: in PG mode skip the `sqlite3 PRAGMA integrity_check` and do the row-count comparison through the db layer (step 2).
6. `migrate_encrypt_doc_fields.py` `_open()`: on PostgreSQL (`db.config.DB_BACKEND == "postgresql"`) skip the file-exists and `sqlite_master` checks (use `to_regclass('public.guest')` through the db layer instead); SQLite unchanged. Same treatment for `backfill_legal_acceptance.py` if needed. Add one PostgreSQL test per changed script (skips without `UBYHOST_TEST_DATABASE_URL`, like `tests/test_db_postgres.py`).
7. Never write to `/data/ubyhost.db` in PG mode. No new dependency.
## 5. Do not touch
`pg-cutover.sh`, `backup.sh`, `App/app/`, anything outside §3.
## 6. Commands
From the repo root: `bash -n deploy/lightsail/scripts/deploy.sh && shellcheck deploy/lightsail/scripts/deploy.sh 2>&1 | tail -10` (if shellcheck exists). From `App/`: the tests of the two scripts on SQLite, then on PostgreSQL with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test` (start with `service postgresql start` if down), `-q --tb=short 2>&1 | tail -5`. `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`bash -n` clean; script tests green on both backends; in PG mode no line of deploy.sh calls `sqlite3`.
## 8. Stop and ask
Stop if a step needs a change in `App/app/` or in `backup.sh`.
## 9. Report
`docs/tasks/0473-report.md`: the command tails and a list of each deploy.sh block with what it does in each mode.
