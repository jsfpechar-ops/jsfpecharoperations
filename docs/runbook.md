# Runbook

Authoritative operational detail already lives in
[OPERATIONS.md](OPERATIONS.md), [LIGHTSAIL.md](LIGHTSAIL.md), and
[DEPLOYMENT.md](DEPLOYMENT.md). This page orders them and adds what the code
shows. Do not edit production from this page; the owner deploys manually
(`AGENTS.md`, rule 8).

## Deploy (production, Lightsail)

1. Confirm `main` is green in CI (`.github/workflows/ci.yml`). Merge only via `scripts/merge-pr-on-green.sh` (`AGENTS.md`).
2. Run the preflight workflow (`.github/workflows/deploy-preflight.yml`) — `⚠️ UNKNOWN`: confirm its checks (not read in full).
3. Deploy: **production deploys automatically after green CI on `main`** (confirmed). `.github/workflows/deploy-production.yml:19-22` is a `workflow_run` trigger; the job at `:55` uses `environment: production`. The GitHub `production` environment has **no protection rules** (checked via `gh api`), so there is no approval gate. Two runs succeeded on 2026-10-31 (09:07 and 09:38 UTC). `AGENTS.md` rule 8 says production deploy is manual; that statement is out of date with the workflow. Manual dispatch requires typing `DEPLOY`.
4. On the server, the manual path is documented in [LIGHTSAIL.md § Updating after code changes](LIGHTSAIL.md#updating-after-code-changes) (`/opt/ubyhost`).
5. Verify: `/healthz` (Docker healthcheck in `Dockerfile`; `GET /healthz` version `1.1.0` per `docs/context/status.md`) and the worker liveness file (`deploy/lightsail/docker-compose.yml`, worker healthcheck: `worker.alive` newer than 120 s).

## Rollback

`⚠️ UNKNOWN — needs human input`: no rollback script or procedure is in the repo beyond re-deploying an older image/commit. Check `docs/LIGHTSAIL.md § Deploy path and failure modes`. Before any rollback that crosses a migration, read the forward-only note in [migrations](#running-migrations): the migration runner has no down-migrations (`App/app/db.py:1124-1260`).

## Running migrations

- Automatic at start-up of web and worker under a file lock (`App/app/db.py:1088-1116`, `:1236`). No manual step is needed.
- Forward-only: the runner records applied versions in `schema_migrations` and has no down path (`App/app/db.py:1136`, `:1205`).
- Downtime: `⚠️ UNKNOWN` per migration; check each `App/app/migrations/*.sql` for table rebuilds.
- Backup first: take a backup (below) before deploying a migration. `⚠️ UNKNOWN` whether this is written as a required step; it is recommended by `docs/OPERATIONS.md § Schema migrations` (read that section before running).

## Backups

- Script: `App/scripts/backup_data.sh` — snapshots SQLite, tars `ubyhost.db` with `secret_key` and `initial_admin_credentials`, encrypts to the age recipient in `UBYHOST_BACKUP_AGE_RECIPIENT`; production with no recipient fails closed (`docs/OPERATIONS.md § Backup and restore`).
- Off-site: `deploy/lightsail/scripts/backup-s3.sh` (rclone copy of `*.age`, refuses plaintext; `deploy/lightsail/`). Litestream replicates the WAL to S3 (`deploy/lightsail/litestream.yml`, `deploy/lightsail/docker-compose.yml` litestream service).
- Retention: `UBYHOST_BACKUP_RETENTION_DAYS` default 30 (`docs/OPERATIONS.md`).
- Last run record: `$BACKUP_ROOT/.last_success.json`. Monitoring hook: `UBYHOST_BACKUP_PING_URL`.
- Schedule: `⚠️ UNKNOWN` — no cron/timer for `backup_data.sh` found in this pass. Check `deploy/lightsail/scripts/` and the server crontab.
- Locations: server volume `/data/backups`; Google Drive `UbyHost-backups`; S3 bucket (name is `⚠️ UNKNOWN` in this pass; read `deploy/lightsail/litestream.yml` on the server). Source: `docs/OPERATIONS.md`.
- Restore: `deploy/lightsail/scripts/restore.sh` with `AGE_IDENTITY_FILE` (never inside the volume); full procedure in [LIGHTSAIL.md § Restore runbook](LIGHTSAIL.md#restore-runbook-same-instance).
- **Tested?** The last `restore-drill.yml` run succeeded on 2026-10-26 (GitHub Actions, checked via `gh run list`). That is the only run visible; it does not show what was restored. The `docs/OPERATIONS.md` quarterly full-restore check is `⚠️ UNKNOWN` until the owner confirms it against a real snapshot.
- **Scheduled backups (confirmed in scripts):** `deploy/lightsail/scripts/setup-server.sh:72-76` and `finish-bootstrap.sh:70` install crontab entries: daily `backup.sh` at 03:00 UTC and `backup-gdrive.sh` on Sundays at 04:00. Whether the crontab is installed on the live server is `⚠️ UNKNOWN`.

## Monitoring and alerting

- Uptime: `.github/workflows/uptime.yml` (`⚠️ UNKNOWN` target and alert channel; read it).
- Host metrics: Grafana Alloy, node-exporter, cAdvisor (`deploy/lightsail/docker-compose.yml`, `deploy/lightsail/monitoring/`).
- Job health: dead-man switches `UBYHOST_HEARTBEAT_*` (see [architecture](architecture.md#background-jobs)); `job_failed` alerts shown in-app.
- Queue depth: `⚠️ UNKNOWN` — no dashboard or alert on the mail outbox or submission backlog located; the in-app Operations page reads `job_last_ok` (`App/app/scheduler.py:74-106`).
- DB connections: not applicable (SQLite file lock; `busy timeout 30 s`, `App/app/db.py:669`).
- Alert destination: `⚠️ UNKNOWN` — Better Stack and healthchecks.io are named as owner-done in `docs/context/status.md`; confirm the on-call route.

## Logging

- App log: `ubyhost.scheduler` and per-request PII-free lines (`App/app/main.py`, OPS-3 per `Dockerfile` comment). uvicorn access log is disabled (`--no-access-log`, `Dockerfile` CMD).
- Destination: Docker logs; `deploy/lightsail/docker-compose.yml` logging/alloy config (`⚠️ UNKNOWN` shipping target and retention — `docs/LIGHTSAIL.md § Disk, logs, photos` has details).
- Search: `docker compose logs --since 1h ubyhost` on the host (`⚠️ UNKNOWN` exact command — check `docs/LIGHTSAIL.md § Day-to-day commands`).
- Retention of logs: `⚠️ UNKNOWN`.

## Common failure modes

| Symptom | Likely cause (from code) | Remediation |
|---|---|---|
| Submissions pending, `job_failed` on `submit` (critical) | UbyPort unreachable or login refused; sweep skips apartments with open `ubyport_auth_failed` alert (`App/app/scheduler.py`) | Check UbyPort status and credentials; do not retry login repeatedly (lockout risk, per code comment). `docs/OPERATIONS.md § UbyPort error codes` |
| "Queue backed up" (mail) | `mail.drain` backoff up to 6 h; terminal FAILED after 8 attempts (`App/app/mail.py:684-693`) | Read the failed rows; check SES (`docs/SES.md`) |
| iCal feed stopped | feed auth expired or private URL blocked (`UBYHOST_ICAL_ALLOW_PRIVATE`, `App/app/config.py:452`); `ical` job failure | See [iCal integration](integrations/ical-feeds.md) |
| "police API down" | `UbyportTransportError` / `OutcomeUnknownError` (`App/app/ubyport/client.py:33-58`) | Outcome unknown is never auto-resent; a second send counts as duplicate (code 150). Verify in UbyPort web app before re-filing (`App/app/guide_i18n.py:140`) |
| Worker restarts repeatedly | scheduler thread died, worker exits 1 (`App/app/worker.py:87-89`) | Read worker logs; check `DATA_DIR/scheduler.lock` is not stale |
| Web says "scheduler lock held" | second process holds `scheduler.lock` (`App/app/worker.py:77-83`, exit 3) | Stop the duplicate; never run two workers on one volume |
| DB errors / "database is locked" | SQLite single writer; busy timeout 30 s (`App/app/db.py:669`) | Check long-running writers; see [performance](performance.md) |
| Calendar-based deadline wrong | holiday list hardcoded (`App/app/deadlines.py:38-59`) | Check against official calendar; see [gap report](gap-report.md) |
| "iCal credentials expired" | `⚠️ UNKNOWN` — no credential concept in iCal (public feed URLs); check `App/app/feed_fetch.py` error path | — |

## Escalation

`⚠️ UNKNOWN — needs human input`: named contacts are not in the repo. The owner
is Josef (`render.yaml`, `josef@ubyhost.com`). Vendor contacts (UbyPort
helpline `+420 731 670 444`, `ubyport@pcr.cz`) are in `App/app/guide_i18n.py:140`
and are for hosts, not operators.
