# 0456 review — PostgreSQL operations kit (BLOCKED, do not merge)

Status: **blocked / draft.** Static review only. Encrypted restore/PITR, cutover failure ordering and the
runbook have **not** been rehearsed: no Docker here, and pgBackRest 2.60.0
(official source) cannot be built (no `pkg-config`/OpenSSL/lz4 dev libs, no
Homebrew). No production access, secrets or deployment was used.

Input: `docs/plans/postgresql/ubyhost-handoff/handoff/UNREVIEWED-postgresql-operations.patch`
(23 files, **+1269/−42**), inspected in a throwaway clone with the patch applied
only there. Based on reviewed 0455 interfaces (`feat/0455-postgresql-runtime`).

## Exact allowlist (23 files)

New: `App/scripts/{create_postgres_cutover_snapshot.py +57, postgres_cutover_transfer.sh +78, postgres_key_bundle.py +34}`;
`deploy/lightsail/docker-compose.postgres.yml +151`;
`deploy/lightsail/postgres/{Dockerfile +20, entrypoint.sh +29, pgbackrest-runner.sh +23, pgbackrest.conf +17}`;
`deploy/lightsail/scripts/{postgres-backup.sh +36, postgres-compose-env.sh +26, postgres-cutover.sh +281, postgres-init-backups.sh +19, postgres-key-backup.sh +139, postgres-lib.sh +78, postgres-preflight.sh +24, postgres-restore.sh +70, postgres-schedule.sh +62, postgres-status.sh +13}`.
Changed: `App/scripts/backup_data.sh +5`, `deploy/lightsail/docker-compose.yml +1`,
`deploy/lightsail/scripts/{backup.sh +4, deploy.sh +92/−42, restore.sh +10}`.
All new files are added as mode `100644`; direct `./scripts/postgres-cutover.sh`
fails until `deploy.sh` chmods them. Must be `100755`.

## Static evidence

- `bash -n`: 36/36 scripts exit 0 (23 tracked + 13 new); `sh -n`: 3/3 exit 0.
- `py_compile`: 2/2 new Python files exit 0. `shellcheck` absent; manual review
  found no `eval`/unquoted expansion hazards, but see H2/H4.
- Compose YAML parses, but `docker compose config` is **not runnable** here, so
  interpolation/merge is unvalidated.
- pgBackRest config retention was checked against its docs: time-based full
  retention does keep the archive needed for the oldest retained full (sound).
- Pins checked: `postgres:18.6-bookworm` digest exists (multi-arch), PGDATA
  `/var/lib/postgresql/18/docker`, `pgbackrest 2.60.0-1.pgdg12+1` installable.

## Blockers

- **B1 visible maintenance mode does not work.** `docker-compose.yml:178` wires
  `UBYHOST_MAINTENANCE` into caddy, but the generated Caddyfile never uses it
  and the app ignores it. `postgres-cutover.sh:69-81` requires `/healthz` → 503,
  so `prepare` fails after already writing `MAINTENANCE=1` and recreating caddy;
  `abort-to-sqlite` then refuses idle (254-257) → half-maintenance state.
- **B2 restore/rehearsal not executable.** `postgres-restore.sh:57-67` restores
  to `/restore` while `docker-compose.postgres.yml:114-130` expects
  `PGDATA=/var/lib/postgresql/18/docker`; no script runs the rehearsal profile;
  restore checks only the exit code (no `pg_verifybackup`/`pg_controldata`).
- **B3 transfer dead-end.** `postgres-cutover.sh:163-168` marks
  `transfer_in_progress`; only `transfer-recovery-verify` is allowed after a
  failed/rolled-back 0455 transfer, and abort refuses those phases — no scripted
  retry or back-out.
- **B4 SQLite rollback broken.** `postgres-cutover.sh:264` writes an empty
  `UBYHOST_DATABASE_URL=`; 0455 `config.py` rejects empty-but-set (compose passes
  it), so after `abort-to-sqlite` web/worker crash-loop. The line must be removed.
- **B5 missing deliverables.** No owner runbook, tests or `.env.example` for the
  required vars (`UBYHOST_PG_DATABASE`, `_SUPERUSER`, `_SUPERUSER_PASSWORD_FILE`,
  `_BACKREST_BUCKET/_ENDPOINT/_REGION`, `_BACKREST_S3_KEY_FILE/_S3_SECRET_FILE`,
  `_BACKREST_CIPHER_PASS_FILE`; `UBYHOST_S3_BUCKET` undocumented).
- **B6 no restricted DB role.** `docker-compose.postgres.yml:20-24` runs the app
  as the superuser; separate migration/backup/runtime roles and grants are a
  0456 requirement and an owner decision.

## High/medium findings

- H1 key bundles can age out the last key-bearing bundle / silently keyless
  (`postgres_key_bundle.py:23-29`, `postgres-key-backup.sh:62-67,83-137`).
- H2 fail-open guards: `postgres-cutover.sh:120,258` test markers inside `if`;
  `:85` `ps … || true` ignores a failed web stop.
- H3 Litestream is never stopped (`:131,262`) → stale SQLite replica keeps
  uploading after cutover.
- H4 state dir keyed to `$HOME` with no `flock` (`:10`, `deploy.sh:183-190`).
- H5 disaster restore requires forward-backup env incl. an age recipient
  (`postgres-restore.sh:39-40`, `postgres-lib.sh:73-76`) → restore blocked.
- H6 `postgres-preflight.sh`/`postgres-init-backups.sh` are never invoked;
  `postgres-schedule.sh sqlite` is not wired into abort.
- H7 the rehearsal network is shared with restore/backup
  (`docker-compose.postgres.yml:152-160` vs `:67,124`) → rehearsal can reach the
  production DB.
- H8 the read-only WAL snapshot (`create_postgres_cutover_snapshot.py:34`) can
  fail after an unclean stop.
- Low: the cutover full backup is not recorded through `pg_schema.py
  record-backup`; a `.partial` file is left after a failed transfer; cron
  matching depends on the exact `PG_OPS_ROOT`.

## 0455 interface reconciliation (OK so far, re-verify after 0455 merges)

The kit's calls match the implemented CLIs (`pg_schema.py` verbs +
`--expect-database`, `sqlite_to_postgres.py --source --report
--expect-database [--verify-only]`, authority marker, single
`UBYHOST_DATABASE_URL` switch); the CLIs bootstrap `sys.path`.

## Blocking gate

0456 stays **blocked** until at least: B1–B4 fixed, an executable isolated
restore → verify → read-only-start → 0455 `--verify-only` rehearsal runs, the
Docker image builds and the cutover failure transitions are exercised, and the
owner decides B6 (roles) and H3 (Litestream quiesce). Encrypted pgBackRest
restore/PITR rehearsal has **not** been run anywhere; nothing here is
production-ready and nothing was applied to the repo.
