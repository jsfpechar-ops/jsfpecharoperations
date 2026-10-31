# Owner cutover runbook: SQLite → PostgreSQL 18 (brief 0455–0456)

Status: **proposal for engineer/DBA review. Not rehearsed on Docker.** Every
command below has been statically checked (`bash -n`, `py_compile`, Caddyfile
validation with a local Caddy binary), but no step has been run against a Docker
Compose stack, a pgBackRest repository or a production host. Treat the first
execution as a rehearsal on a disposable Lightsail instance/volume, not as a
production run.

Read first: `docs/tasks/0456-postgresql-cutover-and-recovery.md`,
`docs/LIGHTSAIL.md` (backups and database sections) and
`docs/OPERATIONS.md#backup-and-restore`.

Working directory for every command: the deploy directory, normally
`/opt/ubyhost/deploy/lightsail` (referred to as `$ROOT` below). `$ROOT` is what
the scripts call `PG_OPS_ROOT`.

---

## 0. Owner decisions that block the irreversible steps

Do not start after step 6 until these are answered and written down in
`docs/context/decisions.md`:

1. **Off-host pgBackRest repository.** Reuse the existing S3-compatible bucket
   for the WAL/base-backup chain, or buy a new one? The kit assumes path-style
   S3 (`repo1-s3-uri-style=path`). State the cost, the retention and the real
   RPO/RTO; do not reuse an unverified claim.
2. **Restricted roles.** Approve or reject the proposal in
   `deploy/lightsail/postgres/roles.sql`. Until approved the app connects as the
   PostgreSQL superuser. Adopting a restricted app role changes
   `UBYHOST_DATABASE_URL`, and the 0455 migration CLI has no separate migration
   DSN yet (owner/engineer decision, see §9).
3. **Rehearsal host.** Approve one disposable Lightsail instance + one extra
   volume for the Docker/pgBackRest rehearsal. Production is not that host.
4. **Maintenance page check.** Confirm who watches the public page through
   Cloudflare while the maintenance window is open (the loopback curl cannot
   prove it, see §4).
5. **Passport uploads.** The kit deliberately excludes `/data/passport_photos`
   from the key bundle (short-lived IDs). Confirm that accepting their loss is
   still correct, or add them to a separate encrypted backup.
6. **Age identity custody.** The offline private identity and a copy of
   `UBYHOST_BACKUP_AGE_RECIPIENT` must exist before the first cutover, or the
   SQLite recovery artifact and key bundles are unreadable.

---

## 1. Preparation (no downtime; SQLite keeps serving)

1. Review and merge the combined PR. Deploy it the normal way first so the new
   scripts and images exist while SQLite is still authoritative:
   `./scripts/deploy.sh` (expect the usual green deploy; the PostgreSQL overlay
   is not selected because `UBYHOST_DATABASE_URL` is still unset).
   Confirm `./scripts/preflight.sh` passes and the public site is up.
2. Create the secrets directory and the four secret files, mode 0600, owner
   `ubuntu` (never in git, never in chat):

   ```bash
   install -d -m 700 ~/ubyhost-secrets
   openssl rand -base64 36 > ~/ubyhost-secrets/postgres_superuser_password
   openssl rand -base64 36 > ~/ubyhost-secrets/pgbackrest_cipher_pass
   # Key/secret: create a dedicated S3 access key limited to the prefix below.
   printf '%s' 'ACCESS_KEY_ID'     > ~/ubyhost-secrets/pgbackrest_s3_key
   printf '%s' 'SECRET_ACCESS_KEY' > ~/ubyhost-secrets/pgbackrest_s3_secret
   chmod 600 ~/ubyhost-secrets/*
   ```

   Store the superuser password and the cipher pass in the password manager too:
   a lost cipher pass makes every pgBackRest backup unreadable.
3. Create the repository bucket/prefix (owner decision §0.1). Suggested prefix:
   `ubyhost/postgres` (already configured in `deploy/lightsail/postgres/pgbackrest.conf`).
   The S3 key needs read/write/list on that prefix only.
4. Confirm the age identity from the SQLite backup documentation still exists
   offline and that `UBYHOST_BACKUP_AGE_RECIPIENT` in `.env` is the matching
   public recipient. Without it the cutover snapshot and key backup fail closed.
5. Add the PostgreSQL block to `.env` (copy the names from
   `deploy/lightsail/.env.example`, section "PostgreSQL cutover"). Uncomment and
   fill every value; the Compose overlay refuses to start on an empty one. Keep
   the file mode 0600. Keep the DSN secret.
6. Run the preparation checks:

   ```bash
   ./scripts/postgres-preflight.sh          # tools, compose v2, overlay, secret files
   ./scripts/postgres-cutover.sh status     # state_dir=..., phase=idle
   ```

   `postgres-cutover.sh` now takes a `flock`, so run one cutover command at a
   time. The state directory defaults to `$ROOT/.postgres-cutover-state`
   (gitignored) and can be overridden with `UBYHOST_PG_CUTOVER_STATE_DIR`.
7. Build the PostgreSQL image now, while the site is up (it needs network for
   apt; the base image already carries the PGDG repository):

   ```bash
   docker compose --env-file .env -f docker-compose.yml -f docker-compose.postgres.yml \
     build ubyhost postgres
   ```

   Do not run `up` for the overlay in production yet. A staging host may run
   everything below first; that staging run is the rehearsal and must be signed
   off before production.
8. Rehearsal (owner/engineer, not this kit's automated step): on the disposable
   host, run §3–§7 against a copy of the production `.env` (different
   `UBYHOST_DATABASE_URL`/bucket prefix), then §8 restore from that chain.
   Record the commands and timings; they are the evidence production is missing.

---

## 2. State machine at a glance

Phases are written to `$ROOT/.postgres-cutover-state/phase` only by explicit
commands. Any command whose phase does not match refuses to run and changes
nothing:

```
idle
 └─ prepare ──────────────> maintenance
     └─ stop-writers ─────> writers_stopped
         └─ start-postgres > postgres_ready
             └─ transfer ─> transfer_in_progress ──ok──> transfer_pending_offsite
                 │                     │                    └─ upload-final-snapshot ─┐
                 │                     └─ transfer-retry (target still empty) ──────┤
                 │                     └─ transfer-recovery-verify (target populated)┤
                 │                                                                    v
                 │                                                               transferred
                 │                                                                    │
                 │                                                    authorize-postgres-writers
                 │                                                                    v
                 │                                                           postgres_authoritative
                 │                                                                    │
                 │                                                              start-writers
                 │                                                                    v
                 │                                                            writers_enabled
                 │                                                                    │
                 │                                                             finish-live
                 │                                                                    v
                 │                                                                  live
                 └─ abort-to-sqlite (allowed only in maintenance / writers_stopped / postgres_ready)
```

`status` prints the phase, the transfer stamp, the writer marker and, in
`transfer_in_progress`, which recovery verb is valid.

---

## 3. Enter maintenance (reversible, still SQLite-authoritative)

1. Confirm the latest normal SQLite backup is good: `./scripts/backup.sh`, and
   `crontab -l` still shows the nightly UbyHost backup row.
2. Put the site into maintenance:

   ```bash
   ./scripts/postgres-cutover.sh prepare
   ```

   It runs `postgres-preflight.sh`, saves the previous Compose/Litestream
   settings, sets `UBYHOST_MAINTENANCE=1`, force-recreates Caddy and proves the
   running container carries the flag. If it fails, it restores
   `UBYHOST_MAINTENANCE=0` and Caddy before exiting (see §10 for the manual
   escape).
3. **Owner check (write down the time):** open the public URL in a normal
   browser. Expect the short maintenance page with HTTP 503 and
   `Retry-After: 300`. Also confirm the app container is still serving SQLite to
   internal health checks only; no customer traffic should reach it.
4. From here on, every write to `/data/ubyhost.db` must be stopped before the
   snapshot. Do not run deploys, backups or tests that write.

---

## 4. Quiesce writers (reversible, still SQLite-authoritative)

1. Stop the web process, the worker/scheduler and the Litestream replica:

   ```bash
   ./scripts/postgres-cutover.sh stop-writers
   ```

   The script stops `worker` and `ubyhost`, verifies Compose reports neither
   running, stops the Litestream container gracefully (SIGTERM) and records
   whether it was running so `abort-to-sqlite` can restart it. It refuses to
   advance if Compose cannot be queried or Litestream is still running.
2. Verify by hand (belt and braces): `docker compose ps` shows no `ubyhost`,
   `worker` or `litestream` container running.
3. Do not start any other host, shell loop or job against the volume.

---

## 5. Start PostgreSQL and initialize the backup stanza

```bash
./scripts/postgres-cutover.sh start-postgres
```

It starts `postgres`, waits up to 120 s for readiness, skips `stanza-create`
when the stanza already exists (so a rerun after a failed check can proceed),
then runs `pgbackrest check`. Expect `postgres_ready`.

If `check` fails (S3 credentials, endpoint, bucket, cipher pass), fix the secret
file/`.env` and rerun the same command; it is safe from `postgres_ready` and
from failure before that state. For a manually managed PostgreSQL that was
started outside this verb, the equivalent initializer is
`./scripts/postgres-init-backups.sh` (stanza-create if absent, check, full
backup, check); it refuses when PostgreSQL is not healthy.

---

## 6. Transfer the quiesced SQLite snapshot (first irreversible step)

```bash
./scripts/postgres-cutover.sh transfer
```

What it does, in order:

1. Generates a UTC stamp and writes it to the state directory.
2. Sets phase `transfer_in_progress` **before** any write.
3. Inside the app image: consistent SQLite snapshot on `/dev/shm`
   (`create_postgres_cutover_snapshot.py`, integrity + foreign-key checks),
   age-encrypted artifact in `/data/backups/postgres-cutover/`, then the 0455
   `sqlite_to_postgres.py` transfer into the empty PostgreSQL target.
4. Copies the encrypted artifact off-host with `rclone` and verifies it with
   `rclone check --download`.
5. Takes the first pgBackRest full backup and runs `check` again.
6. Phase `transferred`.

Owner check before continuing: read the reconciliation report on the volume
(aggregates only, never guest rows):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml \
  exec -T ubyhost sh -c 'ls -l /data/backups/postgres-cutover && cat /data/backups/postgres-cutover/transfer-*.json'
```

Counts/hashes must match the report from the rehearsal. Do **not** proceed if
any table, filing, receipt, invoice or money aggregate mismatches.

### 6a. If `transfer` failed

The phase stays `transfer_in_progress`; do not restart SQLite and do not reset
the target.

- **The 0455 transfer rolled back (nothing committed).** `transfer` prints
  "failed before commit". Prove the target is still empty, then retry with a
  fresh stamp/artifact:

  ```bash
  ./scripts/postgres-cutover.sh transfer-retry
  ```

  The verb itself proves `public` is empty (any object → refuses), so it cannot
  overwrite a committed transfer. If the check cannot run, it refuses.
- **The outcome is ambiguous (the target may contain committed rows).** Verify
  against the encrypted artifact; this never retransfers:

  ```bash
  ./scripts/postgres-cutover.sh transfer-recovery-verify
  ```

  It requires the age artifact to exist and be a real age file, then runs the
  0455 `--verify-only` reconciliation. On success it moves to
  `transfer_pending_offsite`; continue with §6b.
- **The local transfer succeeded but the off-host upload failed.** The phase is
  `transfer_pending_offsite`; retry the artifact and the base backup:

  ```bash
  ./scripts/postgres-cutover.sh upload-final-snapshot
  ```

  The artifact is encrypted before it leaves the volume; never copy a plaintext
  SQLite file off-host.

---

## 7. Authorize PostgreSQL and bring writers up (irreversible)

1. Confirm backups first: `docker compose ... exec -T postgres
   /usr/local/bin/pgbackrest-runner --stanza=ubyhost info` shows a completed
   full backup and no failed WAL archive, and
   `./scripts/postgres-status.sh` shows a small `lag_seconds` and
   `failed_count: 0`.
2. Only after the owner accepts the reconciliation and the backup chain:

   ```bash
   ./scripts/postgres-cutover.sh authorize-postgres-writers \
     --owner-ack=POSTGRES_IS_AUTHORITATIVE
   ```

   This seals the durable authority marker `/data/database-authority.json` (via
   0455) and writes the host marker. From this point the app refuses to start
   against SQLite, and the state machine refuses `abort-to-sqlite`. Keep the
   SQLite volume and the off-host artifact for incident review.
3. Start the web/worker processes against PostgreSQL:

   ```bash
   ./scripts/postgres-cutover.sh start-writers
   ```

   It verifies both markers, then starts `ubyhost` and `worker` while the site
   is still in maintenance.
4. Verify internal health and normal job behaviour with synthetic checks only
   (no real police/lock/mail/payment calls, no guest data in reports):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.postgres.yml \
     exec -T ubyhost python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status)"
   ```

   Open one host page and one guest page while the public site is still in
   maintenance (through the internal health/smoke path), check the worker's
   `/data/worker.alive` freshness and one UbyPort filing in mock/test mode.
5. Turn off maintenance and finish:

   ```bash
   ./scripts/postgres-cutover.sh finish-live --owner-ack=POST_CUTOVER_CHECKS_PASSED
   ```

   It re-checks web + worker health, `pgbackrest check`, archive lag, installs
   the PostgreSQL cron jobs (replacing only UbyHost's SQLite backup rows),
   sets `UBYHOST_MAINTENANCE=0`, force-recreates Caddy and records `live`.
6. **Owner check:** public URL returns the normal site; `./scripts/postgres-schedule.sh
   status` lists the two new cron lines and no UbyHost SQLite backup line;
   `./scripts/postgres-status.sh` still reports zero failed archives.

---

## 8. Backups, restore and point-in-time recovery after cutover

Daily jobs installed by `finish-live`:

```cron
0  3 * * * cd '$ROOT' && ./scripts/postgres-backup.sh full   >> "$HOME/ubyhost-postgres-backup.log" 2>&1
30 3 * * * cd '$ROOT' && ./scripts/postgres-key-backup.sh     >> "$HOME/ubyhost-postgres-key-backup.log" 2>&1
```

- `postgres-backup.sh [full|diff]` runs `pgbackrest check`, the backup, `check`
  again and writes a secret-free verified receipt through 0455
  (`scripts/pg_schema.py record-backup`). It never replaces the previous
  successful chain on failure.
- `postgres-key-backup.sh` streams `/.env`, Caddy certs, the four secret files
  and the app key files through age; it refuses to run when it cannot prove key
  material is present (so retention can never age out the last key-bearing
  bundle). Prune is pair-wise and keeps the newest pair.
- Watch the dead-man URL (`UBYHOST_BACKUP_PING_URL`); the backup job pings it
  only on success.
- `./scripts/postgres-status.sh` prints server-observed archive lag. It is not
  an RPO promise; the real RPO is WAL switch/archive latency, measure it.

### Restore to a fresh isolated volume

```bash
# newest chain, no PITR
./scripts/postgres-restore.sh ubyhost-pg-restore-$(date -u +%Y%m%dT%H%M%SZ)

# point in time (UTC, inclusive; pgBackRest --type=time)
./scripts/postgres-restore.sh ubyhost-pg-restore-$(date -u +%Y%m%dT%H%M%SZ)-pitr \
  --target='2026-11-01 02:30:00+00'
```

The script refuses an existing or mounted volume, creates a fresh labeled
volume, restores into `.../18/docker` under it, then verifies `PG_VERSION` and
`pg_controldata` before reporting success. It does **not** start the volume as a
writer. Keep the volume until reconciliation and disposition are recorded.

### Read-only rehearsal on the restored volume

```bash
UBYHOST_PG_RESTORE_VOLUME=<the volume from above> \
  docker compose --env-file .env -f docker-compose.yml -f docker-compose.postgres.yml \
  --profile postgres-restore up -d postgres-rehearsal

docker compose --env-file .env -f docker-compose.yml -f docker-compose.postgres.yml \
  exec -T postgres-rehearsal psql -U postgres -d ubyhost -X -qAt \
  -c "SELECT count(*) FROM guest" -c "SELECT count(*) FROM reservation"
```

The rehearsal container mounts the volume read-only from the app's point of
view (`default_transaction_read_only=on`, `archive_mode=off`,
`listen_addresses=127.0.0.1`) and has **no egress network**, so it cannot reach
S3 or the production database. Use it for counts, `PRAGMA`-equivalent checks and
one restored guest/PDF read; do not run migrations or UbyPort calls on it. Stop
it with `... stop postgres-rehearsal` and keep the volume.

PITR beyond the newest restore point is only possible if the WAL archive is
intact; the retention settings keep WAL for the oldest retained full backup
(pgBackRest default with `repo1-retention-full-type=time`). Verify the window in
the rehearsal instead of assuming it.

---

## 9. Adopting restricted roles (proposal; owner decision)

`deploy/lightsail/postgres/roles.sql` proposes three roles:
`ubyhost_app` (DML only), `ubyhost_migrate` (DDL/owner of future objects) and
`ubyhost_backup` (proposal only; pgBackRest currently runs as the local
postgres superuser and needs DBA review before it uses a role).

```bash
# after the postgres service is running and the owner approved the proposal
UBYHOST_PG_APP_PASSWORD_FILE=~/ubyhost-secrets/app_password \
UBYHOST_PG_MIGRATION_PASSWORD_FILE=~/ubyhost-secrets/migration_password \
  ./scripts/postgres-create-roles.sh
```

The script passes passwords to `psql` as environment variables (`\getenv`), not
argv; it never prints them and refuses missing/empty files. Before changing
`UBYHOST_DATABASE_URL` to `ubyhost_app`, decide how schema migrations will run:
the 0455 `scripts/pg_schema.py apply` uses the single `UBYHOST_DATABASE_URL`, so
either migration keeps the superuser DSN and only the app is restricted, or a
separate migration DSN is added to 0455 (engineer decision). Do not force the DSN
change blindly: a wrong grant set breaks the app in the maintenance window.

---

## 10. Abort back to SQLite (pre-write only) and rollback limits

Allowed only in `maintenance`, `writers_stopped` or `postgres_ready` — i.e.
before any PostgreSQL write. It checks both authority markers (host and
`/data/database-authority.json`) and refuses if either exists:

```bash
./scripts/postgres-cutover.sh abort-to-sqlite
```

It stops PostgreSQL, removes `UBYHOST_DATABASE_URL` from `.env` (never leaves a
contradictory empty value), restores the saved Compose profiles, Litestream
setting and SQLite cron rows, restarts SQLite web/worker, restarts Litestream
only if this cutover stopped it, turns maintenance off and records
`aborted_to_sqlite`.

**Rollback limits.**

- Before PostgreSQL writes (`authorize-postgres-writers`): rollback is the
  preserved SQLite volume; nothing needs to be reversed.
- After any transfer write (phase `transfer_in_progress` or later): SQLite is
  stale; never start it. Recovery is `transfer-retry`/`transfer-recovery-verify`
  (pre/ambiguous commit) or a PostgreSQL restore (§8). The state machine refuses
  `abort-to-sqlite`.
- After `authorize-postgres-writers`: there is no scripted rollback. A reverse
  PostgreSQL→SQLite transfer would need its own full verification, external
  effect reconciliation and an explicit owner decision.
- An ambiguous or unknown phase is not guessed: the script refuses and only
  `status` reports it. If the state directory is lost while writers are already
  PostgreSQL, do not recreate phases by hand; verify the authority marker and
  treat the site as PostgreSQL-authoritative, or restore PostgreSQL.

### Manual escape if `prepare` left maintenance on but the phase is `idle`

`prepare` cleans up after a failed `maintenance_on`; if the host died in
between, do this only after confirming phase `idle` and no markers:

```bash
./scripts/postgres-cutover.sh status                     # phase=idle
# turn the maintenance page off without touching databases
python3 - <<'PY'
from pathlib import Path
p = Path('.env'); lines = p.read_text().splitlines()
lines = [('UBYHOST_MAINTENANCE=0' if l.startswith('UBYHOST_MAINTENANCE=') else l) for l in lines]
p.write_text('\n'.join(lines) + '\n')
PY
docker compose --env-file .env up -d --no-deps --force-recreate caddy
```

Then verify the public site is normal and re-run `prepare` in a quieter moment.

---

## 11. What is still unrehearsed (engineer/DBA pass required)

- Docker Compose interpolation/merge for the PostgreSQL overlay (no Docker on
  the reviewing host) and the exact container startup order.
- pgBackRest against the real S3-compatible repository: stanza-create, WAL
  archive, full/diff backup, `expire`, encrypted restore, PITR, backup-chain
  integrity after 30-day retention.
- The 0455 transfer against a real PostgreSQL 18 (the runtime tests are 0455's
  own scope; run them before the production window).
- The full state machine on a disposable host, including every failure path
  (pre-commit retry, ambiguous commit, upload failure, abort from each phase).
- The visible maintenance page through Cloudflare and the 0421 guard (loopback
  cannot show it by design).
- Resource sizing (the earlier 512 MB/1 GB caps are not validated) and real
  RPO/RTO numbers. No server timings are claimed here.
- Role adoption (`roles.sql`) and any switch of `UBYHOST_DATABASE_URL` to
  `ubyhost_app`; the 0455 migration-DSN question.

Only the owner performs production steps; this runbook itself performs nothing.
