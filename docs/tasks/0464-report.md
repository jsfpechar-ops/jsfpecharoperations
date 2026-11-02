# 0464 report: nightly PostgreSQL dump and tested restore

Status: review | Branch: task/0464-postgres-backups | Base: 0463 PR branch (0463 not on main yet)

## Files changed
- `deploy/lightsail/scripts/backup.sh`: after `backup_data.sh`, when `postgres` runs, `pg_dump -Fc | age -r` into the newest snapshot folder as `ubyhost-pg.dump.age`. Production without a recipient fails; no plaintext is written.
- `deploy/lightsail/scripts/pg-restore.sh` (new): refuses while `.env` has `UBYHOST_DB` (exit 2); decrypts with `AGE_IDENTITY_FILE` and streams into `pg_restore --clean --if-exists --single-transaction`; health check.
- `deploy/lightsail/scripts/pg-cutover.sh`: `restore_test` in `rehearse` after the verify step (dump, restore into `ubyhost_restoretest`, verify against SQLite); cleanup drops it too.
- `App/tests/test_pg_backup_scripts.py` (new), `deploy/lightsail/README.md`, `docs/LIGHTSAIL.md`, `docs/OPERATIONS.md` (one line each).

## Dry run (stub docker, PG_RUNNING=1, recipient set)
Calls recorded: `compose ps -q --status running postgres`, `exec ubyhost backup_data.sh`, `exec ubyhost sh -c ls -1 /data/backups`, `exec postgres pg_dump -U ubyhost -Fc ubyhost`, `exec ubyhost sh -c cat > /data/backups/<newest>/ubyhost-pg.dump.age`. No host plaintext.

## Tests
- `pytest tests/test_pg_backup_scripts.py tests/test_pg_cutover_script.py`: 16 passed, exit 0.
- `context_lint.py`: see push log.

## Section 7
- [x] Snapshot folder holds both `.age` files (dump step writes into newest folder; `backup_data.sh` writes the tar).
- [x] No plaintext dump on host or volume (pipe only; `ubyhost-pg.dump.age` is the only file).
- [x] Restore refuses while on SQLite (exit 2, tested).
- [x] Rehearsal fails if restored hashes differ (`--verify-only` on `ubyhost_restoretest` through `die`).

## Deviations
- Not run against real Docker or Postgres: no docker here. Stub tests only.
- `pg-restore.sh` pipes `age -d` into `pg_restore` instead of writing a host plaintext file (stricter than brief step 2).
- Without a recipient outside production, the dump is skipped with a warning, not failed.
- Docs: the "dump rides the snapshot" sentence sits under the LIGHTSAIL.md table, not in a table row.
- If decryption fails in `pg-restore.sh`, the app stays stopped until `docker compose up -d ubyhost worker` runs (same as `restore.sh`).

## Questions (stop-and-ask items, unverified)
- Does the `ubyhost` role have the rights `pg_restore --clean` needs? Not checked here.
- Is `age` on the cron PATH on the server? `backup.sh` now fails if it is missing while postgres runs.

## Owner steps left
1. Merge via PR (executor did not open one): `scripts/merge-pr-on-green.sh` after 0463.
2. On the server after deploy: `cd /opt/ubyhost/deploy/lightsail && ./scripts/pg-cutover.sh rehearse` (the drill; it now includes the restore test).
3. Quarterly drill: `AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh <stamp>` on a copy only, after cutover.
