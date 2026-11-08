# 0996: Retire Litestream

Status: review (lint cap fixed by orchestrator in a follow-up commit)
Depends on: 0995 | Base commit: 661f5e5 | Branch: claude/eloquent-mendel-vd8mfi
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Remove the Litestream service, its config, its scripts, its env variables and its tests, and say in the docs that PostgreSQL dumps are the recovery path and Litestream was retired on 2026-11-07. Litestream only replicates the stale SQLite file `/data/ubyhost.db` to S3 (the app moved to PostgreSQL on 2026-10-31, brief 0456) and its container downloads about 0.35 GB per hour from S3 for no benefit.

## 2. Context

- Real protection today: `backup.sh` pg_dump (daily and before each deploy), weekly Google Drive, daily S3 (brief 0995). This brief must land after 0995.
- The old S3 replica (bucket in `LITESTREAM_S3_BUCKET`, prefix `LITESTREAM_S3_PATH`) stays untouched as an archive. No step here deletes, lists or writes S3 data. The owner decides about deleting it after 30 days.
- `restore.sh` is the SQLite snapshot restore. Keep it working for old SQLite snapshots; only its Litestream messages go.
- `restore_test.sh` and `.github/workflows/restore-drill.yml` exist only to drill the Litestream replica, so both are deleted. The PostgreSQL restore path is `pg-restore.sh` (brief 0464).
- A server `.env` that still lists `litestream` in `COMPOSE_PROFILES` is harmless: compose ignores a profile no service uses.
- Anchors below are quoted from the repo at brief time. If one is not found verbatim, STOP (section 8). Line numbers are hints only; use `grep -n` and read at most 150 lines.
- Every shell command ends with `| tail -30`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/docker-compose.yml` | edit | delete the `litestream:` service; fix three comments |
| `deploy/lightsail/litestream.yml` | delete | config of the removed service |
| `deploy/lightsail/scripts/litestream_env.sh` | delete | profile switch |
| `deploy/lightsail/scripts/restore_test.sh` | delete | Litestream drill |
| `.github/workflows/restore-drill.yml` | delete | weekly run of that drill |
| `deploy/lightsail/scripts/deploy.sh` | edit | remove the litestream profile block |
| `deploy/lightsail/scripts/preflight.sh` | edit | remove staging prefix check and Litestream block; fix comments |
| `deploy/lightsail/scripts/restore.sh` | edit | remove Litestream stop and messages |
| `deploy/lightsail/.env.example` | edit | drop `LITESTREAM_*`, `UBYHOST_LITESTREAM_*`, the profile |
| `.github/workflows/deploy-preflight.yml` | edit | drop five `LITESTREAM_*` echo lines |
| `.github/workflows/deploy-staging.yml` | edit | one comment |
| `App/tests/test_litestream_env.py` | delete | tests the deleted script |
| `App/tests/test_wp32_container_sizing.py` | edit | drop the `litestream` entries |
| `deploy/lightsail/README.md` | edit | remove the Litestream section and mentions |
| `docs/LIGHTSAIL.md` | edit | backup table, rebuild step 5, sizing rows |
| `docs/ENVIRONMENT.md` | edit | two rows |
| `docs/OPERATIONS.md` | edit | one bullet in "Backup and restore" |
| `docs/OBSERVABILITY.md` | edit | one profile example |
| `docs/context/architecture.md` | edit | one bullet |
| `docs/runbook.md` | edit | two lines |
| `README.md` | edit | three mentions |
| `docs/context/decisions.md` | edit | append one line |

No other file may change. Historical files that keep their Litestream text on purpose: `docs/tasks/`, `docs/archive/`, `docs/gap-report.md`, `docs/compliance.md`, `docs/UBYPORT_CORE.md`, `docs/architecture.md`, `docs/UbyHost_workplan/`, `docs/integrations/`, `App/scripts/sqlite_to_postgres.py` and `App/tests/test_db_postgres.py` (the SQLite-to-PostgreSQL transfer still has to skip `_litestream_*` tables).

## 4. Steps

1. Baseline. Run `cd /home/user/jsfpecharoperations && grep -rnIil litestream --exclude-dir=.git --exclude-dir=archive --exclude-dir=tasks . | tail -40`. Expected: the files of section 3 plus the historical list above. Note any file not in either list and put it in the report (do not edit it).

2. `docker-compose.yml`, delete the service. Read `grep -n 'litestream' deploy/lightsail/docker-compose.yml`. Delete from the comment line `  # WP05: continuous replication of the SQLite database to S3. Runs as the` through the last line of the service, `    networks:` plus `      - web`, that sits just before the blank line and the comment `  # Step 0: the mock UbyPort for the staging server only.` The block contains `  litestream:`, `    profiles: ["litestream"]`, and ends with `      ubyhost:\n        condition: service_healthy\n    networks:\n      - web`. Keep exactly one blank line before `  # Step 0:`. Command: `grep -c litestream deploy/lightsail/docker-compose.yml | tail -30`. Expected: 3 (the comments of steps 3 to 5).

3. Same file, comment in the `ubyhost` service. Replace
`    # + litestream 256m + caddy 256m leaves over 4 GB for the OS, Docker and`
with
`    # + caddy 256m leaves over 4 GB for the OS, Docker and`.

4. Same file, comment above `alloy`. Replace
`  # COMPOSE_PROFILES=monitoring (combine: COMPOSE_PROFILES=litestream,monitoring).`
with
`  # COMPOSE_PROFILES=monitoring.`

5. Same file. Replace
`    # Pinned by digest (repo convention, like litestream/caddy).`
with
`    # Pinned by digest (repo convention, like caddy).`
and replace
`    # Same pattern as litestream: only the variables this service needs.`
with
`    # Only the variables this service needs are passed in, not the whole .env.`
Command: `grep -ci litestream deploy/lightsail/docker-compose.yml | tail -30`. Expected: 0. Then `docker compose -f deploy/lightsail/docker-compose.yml config -q 2>&1 | tail -30`; if docker is missing, run `python3 -c "import yaml;yaml.safe_load(open('deploy/lightsail/docker-compose.yml'))" 2>&1 | tail -30`. Expected: no output.

6. Delete files: `git rm deploy/lightsail/litestream.yml deploy/lightsail/scripts/litestream_env.sh deploy/lightsail/scripts/restore_test.sh .github/workflows/restore-drill.yml App/tests/test_litestream_env.py 2>&1 | tail -30`. Expected: five `rm '...'` lines.

7. `deploy.sh`. Delete these lines (and the blank line after them), keeping the blank line before them:
```
# shellcheck disable=SC1091
source "$(dirname "$0")/litestream_env.sh"
if [ "${litestream_enabled}" = "1" ]; then
  case ",${COMPOSE_PROFILES:-}," in
    *,litestream,*) ;;
    *)
      export COMPOSE_PROFILES="${COMPOSE_PROFILES:+$COMPOSE_PROFILES,}litestream"
      ;;
  esac
fi
```
Check first that these lines are the only ones with `litestream` in the file (`grep -n -i litestream deploy/lightsail/scripts/deploy.sh | tail -30`: 4 hits). Command: `bash -n deploy/lightsail/scripts/deploy.sh && grep -ci litestream deploy/lightsail/scripts/deploy.sh | tail -30`. Expected: `0`.

8. `preflight.sh`, staging prefix check. Delete these three lines and the blank line before them (inside the staging `if`, right before `elif [ "${DEPLOYMENT}" != "production" ]; then`):
```
case "${LITESTREAM_S3_PATH:-ubyhost/production}" in
    *production*) die "staging must replicate to its own LITESTREAM_S3_PATH, not ${LITESTREAM_S3_PATH:-ubyhost/production}" ;;
  esac
```
The line before the removed blank is `  fi` (end of the `UBYHOST_WEB_WORKERS` check); keep it. Command: `bash -n deploy/lightsail/scripts/preflight.sh | tail -30`. Expected: no output.

9. `preflight.sh`, comment. Replace
`# WP06: web + scheduler worker + litestream + Caddy need at least the 2 GB`
with
`# WP06: web + scheduler worker + Caddy need at least the 2 GB`
and replace
`# bundle. WP32: the compose defaults (web 2g, worker 1g, litestream 256m,`
with
`# bundle. WP32: the compose defaults (web 2g, worker 1g,`.
Then check the next line still reads `# caddy 256m) are sized for the 8 GB production server; a smaller server sets`; leave it.

10. `preflight.sh`, Litestream block. Read the range with `grep -n 'WP05: the litestream service' deploy/lightsail/scripts/preflight.sh`, then read 30 lines from it. Delete from `# WP05: the litestream service replicates the database to S3 continuously.` through the closing `fi` of
```
if [ "${litestream_enabled}" = "1" ]; then
  case "${LITESTREAM_S3_PATH:-ubyhost/production}" in
    /*|*/) die "LITESTREAM_S3_PATH must not start or end with a slash" ;;
  esac
fi
```
and the blank line after it, so that the block `if [ -n "${UBYHOST_SECRET_KEY:-}" ] && [ "${#UBYHOST_SECRET_KEY}" -lt 32 ]; then` follows one blank line after the previous `fi`. Command: `bash -n deploy/lightsail/scripts/preflight.sh && grep -ci litestream deploy/lightsail/scripts/preflight.sh | tail -30`. Expected: `0`.

11. `restore.sh`, comment and stop. Replace these lines
```
# WP05: Litestream must not replicate the restored (older) file into the
# existing replica: mixing two histories under one S3 path can make the
# replica unrestorable. Stop it here; it stays stopped until LITESTREAM_S3_PATH
# points at a new prefix (see the end of this script and README.md).
echo "==> Stopping litestream, worker and ubyhost (Caddy stays up and will 502 until restart)"
docker compose stop litestream 2>/dev/null || true
```
with
```
echo "==> Stopping worker and ubyhost (Caddy stays up and will 502 until restart)"
```

12. `restore.sh`, the two Litestream metadata removals. The line `      rm -rf /data/.ubyhost.db-litestream` (6 spaces) and the line `    rm -rf /data/.ubyhost.db-litestream` (4 spaces, inside the escaped `bash -lc` string) are each deleted. Keep them out: the directory no longer exists on a PostgreSQL server and is harmless on an old volume.

13. `restore.sh`, final messages. Delete these five lines (keep `    exit 0` after them):
```
    echo ""
    echo "Litestream is STOPPED. Point it at a fresh replica prefix before restarting it:"
    echo "  1. In .env set LITESTREAM_S3_PATH to a new value, e.g. ubyhost/production-$(date -u +%Y%m%d)"
    echo "  2. docker compose up -d litestream"
    echo "  3. ./scripts/restore_test.sh"
```
Command: `bash -n deploy/lightsail/scripts/restore.sh && grep -ci litestream deploy/lightsail/scripts/restore.sh | tail -30`. Expected: `0`.

14. `.env.example`. Edit with `grep -n -i litestream deploy/lightsail/.env.example` and read ranges of at most 40 lines:
 a. Delete the line `# LITESTREAM_S3_PATH=staging/ubyhost`.
 b. Replace the three comment lines starting `# WP32: once Litestream replicates to S3 (status.sh shows it, the heartbeat is` / `# green) set 7. Litestream plus S3 versioning is the long-term copy; 30 local` / `# full copies only fill the disk.` with `# 30 is the default. PostgreSQL dumps ride the daily snapshot; lower it if the disk fills.`
 c. Delete the whole section from `# --- Continuous S3 replica (WP05, Litestream) ---` through the line `LITESTREAM_HEARTBEAT_URL=` (the section holds `UBYHOST_LITESTREAM_ENABLED`, `LITESTREAM_S3_BUCKET`, `LITESTREAM_S3_REGION`, `LITESTREAM_S3_PATH`, `LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY`, `LITESTREAM_SYNC_INTERVAL`, `LITESTREAM_VALIDATION_INTERVAL`, `LITESTREAM_HEARTBEAT_URL`) and one of the two blank lines around it.
 d. Delete the line `# UBYHOST_LITESTREAM_MEM=256m`.
 e. Replace `COMPOSE_PROFILES=litestream,monitoring` with `COMPOSE_PROFILES=monitoring`.
 Command: `grep -ci litestream deploy/lightsail/.env.example | tail -30`. Expected: `0`.

15. `deploy-preflight.yml`. Delete the five lines that start with `            echo "LITESTREAM_S3_BUCKET=`, `            echo "LITESTREAM_S3_PATH=`, `            echo "LITESTREAM_ACCESS_KEY_ID=`, `            echo "LITESTREAM_SECRET_ACCESS_KEY=`, `            echo "LITESTREAM_HEARTBEAT_URL=`. In `deploy-staging.yml` line 5 replace `# for the mock UbyPort service) and its own Litestream prefix. Never real guest` with `# for the mock UbyPort service). Never real guest`; if the next line then reads badly, join them in one sentence. Command: `python3 -c "import yaml;[yaml.safe_load(open(f)) for f in ('.github/workflows/deploy-preflight.yml','.github/workflows/deploy-staging.yml')]" 2>&1 | tail -30; grep -ci litestream .github/workflows/deploy-preflight.yml .github/workflows/deploy-staging.yml | tail -30`. Expected: no yaml error, both counts `0`.

16. `test_wp32_container_sizing.py`. Read `grep -n -i litestream App/tests/test_wp32_container_sizing.py` (6 hits). Delete the line `    "litestream": "${UBYHOST_LITESTREAM_MEM:-256m}",`. Change `for name in ("ubyhost", "worker", "litestream", "caddy", "mock-ubyport"):` to `for name in ("ubyhost", "worker", "caddy", "mock-ubyport"):`. Delete the line `        "litestream": "256m",`, the line `        "UBYHOST_LITESTREAM_MEM": "128m",` and the line `        "litestream": "128m",`. In the tuple `for var in ("UBYHOST_WEB_MEM", "UBYHOST_WORKER_MEM", "UBYHOST_LITESTREAM_MEM", "UBYHOST_CADDY_MEM"):` remove `"UBYHOST_LITESTREAM_MEM", `. Read the three edited test bodies (about 60 lines) and check no dict is left with a trailing syntax error. Command: `cd App && .venv/bin/python -m pytest tests/test_wp32_container_sizing.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed, 0 skipped. If a test asserts a total that included 256m, STOP and report (section 8).

17. `deploy/lightsail/README.md`. Run `grep -n -i litestream deploy/lightsail/README.md` (31 hits).
 a. Nothing to change: brief 0995 already rewrote this sentence (README lines 44-45, `Production uses **7**: the daily S3 copy ...`). Check: `grep -n 'Once Litestream replicates' deploy/lightsail/README.md | tail -3` prints nothing.
 b. Delete the whole section from `## Litestream: continuous S3 replica (WP05)` up to, not including, `## Staging server (Step 0)`. This includes its replica restore steps and the closing paragraph that starts `If the replica is unusable, fall back to the newest age-encrypted snapshot`. In its place put exactly:
```
## Backups and recovery (Litestream retired 2026-11-07)

Litestream is gone. The app runs on PostgreSQL, so recovery is the age-encrypted `backup.sh` pg_dump (daily and before each deploy), the weekly Google Drive copy and the daily S3 copy. Restore with `./scripts/pg-restore.sh <stamp>`; `./scripts/restore.sh` remains only for old SQLite snapshots. The pre-cutover S3 replica stays untouched as an archive.

```
 c. In the "Useful later" line (line 26) delete `, `./scripts/restore_test.sh``.
 d. In the staging section delete the line `LITESTREAM_S3_PATH=staging/ubyhost        # its own prefix, its own IAM user` and the line `UBYHOST_LITESTREAM_MEM=128m`.
 e. At the line that contains `` `test`, a `mock` staging without the profile or the mock URL, or a Litestream`` read 3 lines around it and remove the words about Litestream so the sentence stays grammatical (the stack no longer has one).
 Command: `grep -ci litestream deploy/lightsail/README.md | tail -30`. Expected: `2` (only the new heading and the sentence `Litestream is gone.`).

18. `docs/LIGHTSAIL.md`. Run `grep -n -i litestream docs/LIGHTSAIL.md` (8 hits).
 a. Delete the table row starting `| Litestream → S3 (being retired, brief 0996;`. Replace it with `| `backup.sh` pg_dump on the S3 copy | daily (brief 0995) | see `backup-s3.sh` | off-site copy; Litestream was retired on 2026-11-07 |`.
 b. Rebuild step 5: replace the text from `5. Restore the database. **From Litestream (preferred, newest data):**` through the closing triple backtick of the following `docker compose run ... litestream restore ...` code block and the line `   Then go to step 7. **From a Drive copy instead:**` with `5. Restore the database from the newest dump (S3 or Drive copy): run `./scripts/pg-restore.sh <stamp>` as in the backup section. **For an old SQLite snapshot instead:**`. Keep the Drive-copy code block that follows unchanged.
 c. Delete the table row starting `| Litestream `mem_limit` | `UBYHOST_LITESTREAM_MEM``.
 d. In the row starting `| Local snapshots kept | `UBYHOST_BACKUP_RETENTION_DAYS`` replace `` `7` once Litestream replicates (default `30`) `` with `` `7` (default `30`) ``.
 e. In the paragraph starting `**Rebuild drill (once a quarter).**` replace `The drill proves the replica, the `.env` copy and the password-manager key together; `restore_test.sh` only proves the replica.` with `The drill proves the dump, the `.env` copy and the password-manager key together.`
 Command: `grep -n -i litestream docs/LIGHTSAIL.md | tail -30`. Expected: only the `retired on 2026-11-07` mention from 18a.

19. `docs/ENVIRONMENT.md`. In the row that starts `` | `UBYHOST_WEB_MEM`, `UBYHOST_WORKER_MEM`, `UBYHOST_LITESTREAM_MEM`, `UBYHOST_CADDY_MEM` | `2g`, `1g`, `256m`, `256m` | `` replace the first two cells with `` | `UBYHOST_WEB_MEM`, `UBYHOST_WORKER_MEM`, `UBYHOST_CADDY_MEM` | `2g`, `1g`, `256m` | `` and in its note change `Staging on 2 GB: `896m`, `448m`, `128m`, `128m`.` to `Staging on 2 GB: `896m`, `448m`, `128m`.` (read the full line first; fix only the numbers). In the `UBYHOST_BACKUP_RETENTION_DAYS` row replace ` Set `7` once Litestream replicates (WP32)` with ` Set `7` if the disk fills`. Command: `grep -ci litestream docs/ENVIRONMENT.md | tail -30`. Expected: `0`.

20. `docs/OPERATIONS.md`. Run `grep -n '^## Backup and restore' docs/OPERATIONS.md`, read 40 lines from it, and add at the end of that section's first bullet list one bullet: `- **Litestream is retired (2026-11-07).** The database is PostgreSQL; recovery is the pg_dump in the age-encrypted snapshot (daily and before each deploy), the weekly Drive copy and the daily S3 copy. The old SQLite replica in S3 is kept untouched as an archive until the owner deletes it.` Command: `grep -n 'Litestream is retired' docs/OPERATIONS.md | tail -30`. Expected: one hit.

21. Other docs.
 a. `docs/OBSERVABILITY.md`: replace `   COMPOSE_PROFILES=litestream,monitoring.` with `   COMPOSE_PROFILES=monitoring.`
 b. `docs/context/architecture.md`: delete the bullet `  - `litestream`: continuous SQLite replication to S3.`
 c. `docs/runbook.md`: run `grep -n -i litestream docs/runbook.md`; in the "Off-site" line (line 31) delete the sentence that starts `Litestream replicates the WAL to S3 (` through its end (read the full line first); in the "Locations" line (line 35) replace `read `deploy/lightsail/litestream.yml` on the server` with `read `BACKUP_S3_BUCKET` in the server `.env``. Check the name `BACKUP_S3_BUCKET` with `grep -n 'S3_BUCKET' deploy/lightsail/scripts/backup-s3.sh | head -3 | tail -30`; use the variable name found there.
 d. `README.md`: line 25 `replicated to S3 by Litestream.` becomes `backed up daily as encrypted pg_dump files (daily S3 copy, weekly Drive copy).` (read lines 23 to 27 and keep the sentence grammatical); delete the table row `| Backups | Litestream | 0.5.17 | `deploy/lightsail/docker-compose.yml` |` and replace it with `| Backups | `backup.sh` pg_dump, age, rclone | n/a | `deploy/lightsail/scripts/backup.sh` |`; in the tree line `├── deploy/lightsail/                   production compose, Caddy, Litestream, scripts` delete `Litestream, `.
 Command: `grep -n -i litestream docs/OBSERVABILITY.md docs/context/architecture.md docs/runbook.md README.md | tail -30`. Expected: no output.

22. `docs/context/decisions.md`. Append as the last line (check `tail -3 docs/context/decisions.md` first and match its format):
`- 2026-11-07 | [backup] Litestream retired: it replicated only the stale SQLite file after the PostgreSQL cutover and pulled about 0.35 GB/hour from S3. Recovery is pg_dump in the encrypted snapshot (daily and pre-deploy), weekly Drive, daily S3. Old S3 replica kept as archive; owner deletes it after 30 days | owner | [0996](../tasks/0996-remove-litestream.md)`

23. Final grep. Run `grep -rnIil litestream --exclude-dir=.git --exclude-dir=archive --exclude-dir=tasks . | tail -30`. Expected: only the historical files listed in section 3, `deploy/lightsail/README.md`, `docs/LIGHTSAIL.md`, `docs/OPERATIONS.md`, `docs/context/decisions.md`, `docs/context/architecture.md` is gone from the list. Anything else: STOP and report.

## 5. Do not touch

- `docs/tasks/` other than this brief and its report, `docs/archive/`, the historical files listed in section 3.
- `App/app/` (no app code change), `deploy/lightsail/scripts/backup.sh`, `backup-s3.sh`, `backup-gdrive.sh`, `pg-restore.sh`, `pg-cutover.sh`.
- No S3 command of any kind. Never delete or list the replica bucket or prefix.
- AGENTS.md hard rules 3 (no secrets in the repo), 5 (no SQL change) and 9 (one explanation in one place: the retirement is explained in the OPERATIONS bullet; the README and LIGHTSAIL texts stay one line).
- No SSH, no deploy, no push to `main`.

## 6. Commands

Test-map row "Deploy scripts, Caddyfile, compose" plus the changed tests:

1. `cd /home/user/jsfpecharoperations && shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` (expected: no output; if shellcheck is missing, run `for f in deploy/lightsail/scripts/*.sh; do bash -n "$f"; done 2>&1 | tail -30`, expected: no output).
2. `cd App && .venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` (expected: all passed, 0 skipped).
3. `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no errors).
4. `git status --short | tail -30` (expected: only section 3 paths plus this brief and its report).

## 7. Acceptance

- [ ] `grep -ci litestream deploy/lightsail/docker-compose.yml deploy/lightsail/.env.example deploy/lightsail/scripts/*.sh` shows 0 for every file.
- [ ] `ls deploy/lightsail/litestream.yml deploy/lightsail/scripts/restore_test.sh deploy/lightsail/scripts/litestream_env.sh .github/workflows/restore-drill.yml App/tests/test_litestream_env.py 2>&1 | tail -30` says "No such file" five times.
- [ ] `bash -n` passes for `deploy.sh`, `preflight.sh`, `restore.sh`; shellcheck is clean.
- [ ] `test_wp32_container_sizing.py` and `test_pg_backup_scripts.py` pass, 0 skipped.
- [ ] The decision line is the last line of `docs/context/decisions.md`.
- [ ] Context lint passes.
- [ ] No template, CSS or guest-page change, so no screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (list it in the report);
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0996-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations. Mention that `restore.sh` still handles old SQLite snapshots (kept on purpose), and that `restore_test.sh` and the weekly `restore-drill.yml` were deleted, so there is no scheduled restore drill now; a PostgreSQL drill needs its own brief.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `deploy/lightsail/docker-compose.yml`: the service block removed, YAML still valid, no other service had `depends_on: litestream`.
- `deploy/lightsail/scripts/preflight.sh` and `deploy.sh`: shell syntax and that the staging `if` block still closes.
- `deploy/lightsail/scripts/restore.sh`: SQLite restore path unchanged.
- `.github/workflows/deploy-preflight.yml`: YAML still valid.
- `docs/LIGHTSAIL.md` rebuild step 5: the new text points to `pg-restore.sh`.

## Owner steps

Do these after the PR is merged and you have run the normal deploy (0995 must already be deployed).

1. Open a terminal and connect to the server as usual: `ssh ubuntu@<your server>`.
2. Go to the stack folder: `cd /opt/ubyhost/deploy/lightsail`
3. Stop and remove the old container (the `--profile litestream` flag is needed because the service no longer exists in the file, so if compose says "no such service", skip to step 4 and use `docker rm -f` instead): `docker compose --profile litestream rm -sf litestream`
4. If step 3 said "no such service", run: `docker rm -f $(docker ps -aq --filter name=litestream)`
5. Confirm it is gone: `docker ps --format '{{.Names}}' | grep -i litestream`. Nothing should print (no `ubyhost-litestream-1`).
6. Edit the server settings file: `nano .env`. Delete every line that starts with `LITESTREAM_` or `UBYHOST_LITESTREAM_`. In the line `COMPOSE_PROFILES=` remove the word `litestream` (keep `monitoring`, for example `COMPOSE_PROFILES=monitoring`). Save with Ctrl+O, Enter, then exit with Ctrl+X.
7. Confirm: `grep -ci litestream .env`. It should print `0`.
8. Run `./scripts/status.sh` and check the site opens and `docker ps` lists `ubyhost`, `worker`, `postgres` and `caddy` as healthy.
9. Do NOT delete anything in S3 now. The old Litestream replica is your archive of the SQLite era.
10. Optional, your decision, not before 2026-12-07: in the AWS console open S3, open the Litestream bucket, and delete the replica prefix (the value your `LITESTREAM_S3_PATH` had, normally `ubyhost/production`). Afterwards the IAM user `ubyhost-litestream` can be deleted under IAM, Users.
11. After a day, check in the AWS console (Billing, or the bucket's metrics) that the roughly 0.35 GB per hour download is gone.
