# 0464: Nightly PostgreSQL dump in the existing backup, and a tested restore
Status: todo
Depends on: 0463 on main | Base commit: main | Branch: task/0464-postgres-backups
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
The nightly `backup.sh` run also dumps the PostgreSQL database, age-encrypted, into the same snapshot folder, so retention (`UBYHOST_BACKUP_RETENTION_DAYS`), the S3 and Drive copies and the Lightsail snapshots cover it without new jobs. A restore script exists and the rehearsal proves the dump restores byte-for-byte (same per-table hashes). Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) step 9. No pgBackRest, no new image.
## 2. Context
`deploy/lightsail/scripts/backup.sh` runs `App/scripts/backup_data.sh` inside the `ubyhost` container, which writes `/data/backups/<stamp>/ubyhost-backup.tar.age` and prunes old folders; `backup-s3.sh` and `backup-gdrive.sh` upload the newest folder and refuse plaintext. `restore.sh` decrypts on the host with `AGE_IDENTITY_FILE` (so `age` is installed on the host). The `postgres` service and `pg-cutover.sh rehearse` come from 0463; `sqlite_to_postgres.py --verify-only` checks a PostgreSQL database against the SQLite source.
## 3. Files
Edit: `deploy/lightsail/scripts/backup.sh`, `deploy/lightsail/scripts/pg-cutover.sh` (rehearse only), `deploy/lightsail/README.md` and `docs/LIGHTSAIL.md` (one row for `pg-restore.sh`; one sentence in the backup layers table that the dump rides the daily snapshot), `docs/OPERATIONS.md` backup section (one bullet). New: `deploy/lightsail/scripts/pg-restore.sh`, `App/tests/test_pg_backup_scripts.py`.
## 4. Steps
1. `backup.sh`: after `backup_data.sh` succeeds and only when the `postgres` container is running: `docker compose exec -T postgres pg_dump -U ubyhost -Fc ubyhost | age -r "$UBYHOST_BACKUP_AGE_RECIPIENT" | docker compose exec -T ubyhost sh -c "cat > /data/backups/<newest stamp>/ubyhost-pg.dump.age"`. Without a recipient in production: fail closed like `backup_data.sh`. Print the dump size, nothing else.
2. `pg-restore.sh <stamp>`: stop `worker` and `ubyhost`; pull the `.age` file out with `docker compose cp`; decrypt on the host with `AGE_IDENTITY_FILE`; `docker compose exec -T postgres pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction` from stdin; delete the host plaintext; `up -d ubyhost worker`; health check as in `restore.sh`. Refuse if `.env` still has `UBYHOST_DB` (app not on PostgreSQL yet).
3. `pg-cutover.sh rehearse`, after the transfer verifies: `pg_dump -Fc ubyhost_rehearsal` → `pg_restore` into a fresh `ubyhost_restoretest` → `sqlite_to_postgres.py --verify-only --expect-database ubyhost_restoretest` against the same SQLite copy; print `RESTORE TEST OK` or fail the rehearsal; drop both databases.
4. Test (`App/tests/test_pg_backup_scripts.py`): `bash -n` on both scripts; `pg-restore.sh` exits 2 on a `.env` that has `UBYHOST_DB` (use a temp dir and a stub `docker` on `PATH` that records calls); `backup.sh` with the stub records a `pg_dump` call only when the stub reports `postgres` running.
## 5. Do not touch
`App/scripts/backup_data.sh`, `restore.sh`, `restore_test.sh`, Litestream, `App/app/`.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`; `python3 scripts/context_lint.py | tail -3` from the repo root.
## 7. Acceptance
A snapshot folder holds both `.age` files; no plaintext dump stays on the host or in the volume; restore refuses while the app is on SQLite; rehearsal fails if the restored copy's hashes differ.
## 8. Stop and ask
Stop if `age` is missing on the host path used by cron, or if `pg_restore --clean` needs rights the `ubyhost` role lacks.
## 9. Report
`docs/tasks/0464-report.md`: the backup folder listing from a dry run with the stub, the test tail, and the owner's quarterly drill command.
