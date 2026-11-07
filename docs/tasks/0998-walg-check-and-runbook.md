# 0998: WAL-G monitor, daily base backup, restore runbook, owner rollout

Status: todo
Depends on: 0997 | Base commit: 47640cf | Branch: task/0998-walg-runbook
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the daily WAL-G base backup with 7-day retention, a monitor that fails loudly when archiving stalls or WAL piles up, and the runbook with the owner's rollout, restore drill and rollback. Downtime is acceptable; silent data loss is not.

## 2. Context

Rules: AGENTS.md rule 1 (data correctness first), rule 2 (privacy: backups must expire), rule 3 (no secrets in the repo), rule 9 (one explanation in one place).

Built by 0997 (must be merged; STOP if not): the `walg` sidecar (`env_file: .env.walg`, `wal-g` on PATH, read-only data mount, spool volume `ubyhost-walspool` at `/walspool`), the postgres service with `archive_mode=on`, `archive_timeout=300`, and the spool `archive_command`. Postgres has `network_mode: none`, so the database container never talks to S3; the sidecar does.

**What `pg_stat_archiver` means here.** `archive_command` only copies into the spool, so `last_archived_time` proves the copy, not the upload to S3. The monitor therefore also checks the age of the oldest file left in the spool. A file stays in the spool until `wal-g wal-push` succeeded.

**Failure mode the monitor guards:** if archiving fails, WAL piles up on disk (in `pg_wal` when the copy fails, in the spool when the upload fails) and can fill the disk. The monitor warns when `pg_wal` is over 5 GB (`WALG_PGWAL_MAX_MB`, default 5120).

**Retention (confirmed against `docs/privacy/RETENTION.md` line "Encrypted backups ... 30 days local/off-site (G-D3)"):** WAL and base backups keep 7 days: `wal-g delete retain FULL 7 --confirm` after each daily base backup (7 full backups = 7 days), and an S3 lifecycle rule deleting objects older than 10 days as a safety net if the delete job stops. Erased personal data is therefore gone from the archives within 10 days at most, inside the 30-day window. A point-in-time restore brings back data that was erased since the restore point; the retention runner must have run again before the restored database serves guests.

**Cost:** about USD 0.05 a month in PUT requests (288 a day at `archive_timeout=300`), plus a few cents of storage and LIST requests for a small database. WAL-G does not read objects back in normal running. The monitor must not call `wal-g wal-verify`, `backup-fetch` or any command that reads many objects. Owner check: look at Cost Explorer for the bucket after 7 days; expected under USD 1 a month.

**Anchor A, `deploy/lightsail/scripts/backup.sh`, the dead-man style to follow:**

```
if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: backup succeeded but the ping to UBYHOST_BACKUP_PING_URL failed" >&2
fi
```

**Anchor B, `docs/OPERATIONS.md`, the section to extend (and the line to insert before):**

```
### Purging pre-OPS-1 plaintext backups (operator, one-time)
```

**Anchor C, `docs/privacy/RETENTION.md`, the row to put the new row after:**

```
| Encrypted backups | `/data/backups`, Drive, S3 | snapshot age | 30 days local/off-site (G-D3) |
```

**Anchor D, `deploy/lightsail/docker-compose.yml` (from 0997):**

```
    command: ["/usr/local/bin/walg-ship.sh"]
```

**Anchor E, `docs/ENVIRONMENT.md`, the row to put the new row after:**

```
| `UBYHOST_BACKUP_PING_URL` | unset |
```

**Anchor F, `docs/LIGHTSAIL.md`, the cron example to put the new lines after:**

```
(crontab -l 2>/dev/null; echo "0 3 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh >> /var/log/ubyhost-backup.log 2>&1") | crontab -
```

**Context-rollout upload (orchestrator):** put files flat in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/walg-check.sh | create | monitor: archiver age, failed count, spool age, pg_wal size, ping |
| deploy/lightsail/scripts/walg-backup.sh | create | daily `wal-g backup-push` then `delete retain FULL 7 --confirm`, ping |
| App/tests/test_pg_backup_scripts.py | edit | append stub tests for the two scripts |
| docs/OPERATIONS.md | edit | one new subsection in "Backup and restore": setup, restore, drill, rollback |
| docs/privacy/RETENTION.md | edit | one row for WAL archives and base backups |
| docs/ENVIRONMENT.md | edit | one row: `UBYHOST_WALG_PING_URL` |
| docs/LIGHTSAIL.md | edit | the two cron lines |

No other file may change.

## 4. Steps

1. Confirm 0997 is merged and the anchors exist. Command: `grep -n 'walg-ship.sh' deploy/lightsail/docker-compose.yml | tail -30; grep -n 'Purging pre-OPS-1' docs/OPERATIONS.md | tail -30; grep -n 'Encrypted backups' docs/privacy/RETENTION.md | tail -30; grep -n 'UBYHOST_BACKUP_PING_URL' docs/ENVIRONMENT.md | tail -30; grep -n 'backup.sh >> /var/log' docs/LIGHTSAIL.md | tail -30`. Expected: at least one hit each. Any missing: STOP.

2. Create `deploy/lightsail/scripts/walg-check.sh` (mode 0755) with this content:

```bash
#!/usr/bin/env bash
# 0998: monitor for WAL-G archiving. Exits non-zero (and does NOT ping the
# dead-man URL) when archiving is late, failing, stuck in the spool, or pg_wal is large.
# Cron (every 10 minutes): see docs/OPERATIONS.md, "WAL-G continuous archiving".
# Reads only pg_stat_archiver, file ages and a directory size. It never lists or reads S3.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

MAX_AGE_S="${WALG_MAX_ARCHIVE_AGE_S:-1800}"      # 30 minutes
MAX_SPOOL_AGE_S="${WALG_MAX_SPOOL_AGE_S:-1800}"  # 30 minutes
PGWAL_MAX_MB="${WALG_PGWAL_MAX_MB:-5120}"        # 5 GB
STATE="${WALG_CHECK_STATE:-/var/tmp/ubyhost-walg-check.state}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

problems=()

row="$(docker compose exec -T postgres psql -U ubyhost -d ubyhost -Atc \
  "SELECT COALESCE(EXTRACT(EPOCH FROM now() - last_archived_time)::bigint, -1), failed_count FROM pg_stat_archiver" 2>/dev/null | tr -d '\r')"
if [ -z "${row}" ]; then
  problems+=("cannot read pg_stat_archiver (is the postgres container running?)")
else
  age="${row%%|*}"
  failed="${row##*|}"
  if [ "${age}" -lt 0 ]; then
    problems+=("pg_stat_archiver has never archived a WAL file")
  elif [ "${age}" -gt "${MAX_AGE_S}" ]; then
    problems+=("last WAL archived ${age}s ago (limit ${MAX_AGE_S}s)")
  fi
  prev=0
  [ -f "${STATE}" ] && prev="$(cat "${STATE}" 2>/dev/null || echo 0)"
  if [ "${failed}" -gt "${prev}" ] 2>/dev/null; then
    problems+=("failed_count rose from ${prev} to ${failed}")
  fi
  printf '%s' "${failed}" > "${STATE}" 2>/dev/null || true
fi

oldest="$(docker compose exec -T walg sh -c \
  'f=$(ls -1tr /walspool 2>/dev/null | grep -v "\.tmp$" | head -1); [ -n "$f" ] && stat -c %Y "/walspool/$f"' 2>/dev/null | tr -d '\r')"
if [ -n "${oldest}" ]; then
  spool_age=$(( $(date +%s) - oldest ))
  if [ "${spool_age}" -gt "${MAX_SPOOL_AGE_S}" ]; then
    problems+=("oldest WAL file in the spool is ${spool_age}s old: the upload to S3 is stuck (docker compose logs walg)")
  fi
fi

pgwal_mb="$(docker compose exec -T postgres sh -c 'du -sm /var/lib/postgresql/data/pg_wal | cut -f1' 2>/dev/null | tr -d '\r')"
if [ -n "${pgwal_mb}" ] && [ "${pgwal_mb}" -gt "${PGWAL_MAX_MB}" ] 2>/dev/null; then
  problems+=("pg_wal is ${pgwal_mb} MB (limit ${PGWAL_MAX_MB} MB): archiving is failing and WAL is piling up on disk")
fi

if [ "${#problems[@]}" -gt 0 ]; then
  for p in "${problems[@]}"; do echo "WALG-CHECK FAIL: ${p}" >&2; done
  exit 1
fi

echo "walg-check ok"
if [ -n "${UBYHOST_WALG_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_WALG_PING_URL}" >/dev/null || \
    echo "WARNING: walg-check ok but the ping to UBYHOST_WALG_PING_URL failed" >&2
fi
```

Command: `chmod +x deploy/lightsail/scripts/walg-check.sh && bash -n deploy/lightsail/scripts/walg-check.sh && shellcheck -S error deploy/lightsail/scripts/walg-check.sh 2>&1 | tail -30`. Expected: no output.

3. Create `deploy/lightsail/scripts/walg-backup.sh` (mode 0755):

```bash
#!/usr/bin/env bash
# 0998: daily WAL-G base backup, then keep the newest 7 (7 days). Run from cron
# after backup.sh (see docs/OPERATIONS.md). The pg_dump backup stays the primary
# copy; this is the point-in-time path.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

docker compose exec -T walg wal-g backup-push /var/lib/postgresql/data
docker compose exec -T walg wal-g delete retain FULL 7 --confirm

if [ -n "${UBYHOST_WALG_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_WALG_PING_URL}/backup" >/dev/null || \
    echo "WARNING: base backup succeeded but the ping failed" >&2
fi
echo "WAL-G base backup done; kept the newest 7."
```

Command: `chmod +x deploy/lightsail/scripts/walg-backup.sh && bash -n deploy/lightsail/scripts/walg-backup.sh && shellcheck -S error deploy/lightsail/scripts/walg-backup.sh 2>&1 | tail -30`. Expected: no output.

4. Append tests to `App/tests/test_pg_backup_scripts.py`. The file's `make_tree` copies only two scripts, so these tests build their own tree. Append:

```python
CHECK_DOCKER_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
case "$*" in
  *pg_stat_archiver*) echo "${ARCH_ROW:-60|0}" ;;
  *walspool*) [ -n "${SPOOL_MTIME:-}" ] && echo "$SPOOL_MTIME" ;;
  *du\ -sm*) echo "${PGWAL_MB:-100}" ;;
esac
exit 0
"""


def make_check_tree(tmp_path):
    root = tmp_path / "deploy" / "lightsail"
    (root / "scripts").mkdir(parents=True)
    for name in ("walg-check.sh", "walg-backup.sh"):
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (root / ".env").write_text("")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "docker").write_text(CHECK_DOCKER_STUB)
    (bindir / "docker").chmod(0o755)
    curl = bindir / "curl"
    curl.write_text('#!/usr/bin/env bash\necho "curl $*" >> "$STUB_LOG"\n')
    curl.chmod(0o755)
    return root, bindir, tmp_path / "stub.log"


@pytest.mark.parametrize("script", ["walg-check.sh", "walg-backup.sh"])
def test_walg_scripts_pass_bash_syntax(script):
    result = subprocess.run(["bash", "-n", str(SCRIPTS / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("extra,expected_fail", [
    ({}, False),
    ({"ARCH_ROW": "4000|0"}, True),            # last archive older than 30 minutes
    ({"ARCH_ROW": "-1|0"}, True),              # never archived
    ({"PGWAL_MB": "6000"}, True),              # pg_wal over 5 GB
    ({"SPOOL_MTIME": "1000"}, True),           # spool file from 1970: upload stuck
])
def test_walg_check_exit_codes(tmp_path, extra, expected_fail):
    root, bindir, log = make_check_tree(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "WALG_CHECK_STATE": str(tmp_path / "state"), "UBYHOST_WALG_PING_URL": "https://ping.example/x"}
    env.update(extra)
    result = subprocess.run(["bash", str(root / "scripts/walg-check.sh")], cwd=root, env=env,
                            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert (result.returncode != 0) == expected_fail, result.stderr
    pinged = "ping.example" in calls(log)
    assert pinged == (not expected_fail)  # the dead-man ping fires only when healthy


def test_walg_check_flags_rising_failed_count(tmp_path):
    root, bindir, log = make_check_tree(tmp_path)
    state = tmp_path / "state"
    state.write_text("2")
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "WALG_CHECK_STATE": str(state), "ARCH_ROW": "60|5"}
    result = subprocess.run(["bash", str(root / "scripts/walg-check.sh")], cwd=root, env=env,
                            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert result.returncode == 1
    assert "failed_count rose" in result.stderr


def test_walg_backup_pushes_then_retains_seven(tmp_path):
    root, bindir, log = make_check_tree(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log)}
    result = subprocess.run(["bash", str(root / "scripts/walg-backup.sh")], cwd=root, env=env,
                            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert recorded.index("backup-push /var/lib/postgresql/data") < recorded.index("delete retain FULL 7 --confirm")
```

Command: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. If the `du -sm` stub pattern does not match, fix only the stub, once; a second failure: STOP.

5. `docs/privacy/RETENTION.md`: insert directly after the "Encrypted backups" row (anchor C) this single row:

```
| WAL archives and base backups (WAL-G) | S3 eu-central-1, bucket `ubyhost-wal-...`, client-side encrypted | base backup age | 7 days (`wal-g delete retain FULL 7`); S3 lifecycle deletes objects older than 10 days as a safety net | `deploy/lightsail/scripts/walg-backup.sh`; S3 lifecycle rule | Disaster recovery |
```

Command: `grep -n 'WAL-G' docs/privacy/RETENTION.md | tail -30`. Expected: one hit.

6. `docs/ENVIRONMENT.md`: after the `UBYHOST_BACKUP_PING_URL` row (anchor E), add a row in the same column format:

```
| `UBYHOST_WALG_PING_URL` | unset | `deploy/lightsail/scripts/walg-check.sh` (pinged only when archiving is healthy; a separate dead-man check from the backup one) and `walg-backup.sh` (pinged at `<url>/backup` after the daily base backup; with healthchecks.io use a URL whose `/backup` suffix is a valid slug, or leave unset) |
```

Read the neighbour row first with `sed -n` on a range of 3 lines and match its column count. Command: `grep -n 'UBYHOST_WALG_PING_URL' docs/ENVIRONMENT.md | tail -30`. Expected: one hit.

7. `docs/LIGHTSAIL.md`: after the cron line in anchor F add exactly these lines, in the same style (they are the cron lines for the owner; do not run them):

```
(crontab -l 2>/dev/null; echo "30 3 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/walg-backup.sh >> /var/log/ubyhost-walg-backup.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "*/10 * * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/walg-check.sh >> /var/log/ubyhost-walg-check.log 2>&1") | crontab -
```

Add one sentence under them: "WAL-G setup, restore drill and rollback: [OPERATIONS](OPERATIONS.md#wal-g-continuous-archiving-and-point-in-time-recovery)." Use the relative link style of the neighbouring lines.

8. `docs/OPERATIONS.md`: insert the new subsection below directly before the line `### Purging pre-OPS-1 plaintext backups (operator, one-time)` (anchor B). Write it exactly:

````markdown
### WAL-G continuous archiving and point-in-time recovery

The daily age-encrypted `pg_dump` (above) stays the primary backup. WAL-G adds point-in-time recovery for the last 7 days. Downtime is acceptable here; losing data is not. Postgres has no network, so it copies finished WAL segments into the `ubyhost-walspool` volume and the `walg` container ships them to S3 (brief 0997).

- **Cost.** About USD 0.05 a month in PUT requests (`archive_timeout=300`), plus a few cents of storage. WAL-G does not read back in normal running. Check Cost Explorer after 7 days; expect under USD 1 a month.
- **Retention.** 7 days: `wal-g delete retain FULL 7 --confirm` after each daily base backup, plus an S3 lifecycle rule at 10 days. See the RETENTION table row.
- **Encryption and key custody.** WAL-G encrypts on the server before upload (`WALG_LIBSODIUM_KEY`, 32 random bytes as 64 hex characters, made with `openssl rand -hex 32`). Keep the key in the password manager and one offline copy, the same custody as the age key. Never put it in the repo, in a chat, or only on the server. Whoever holds it can read the archives; if it is lost, every archive is unreadable and only the pg_dump backups remain.
- **If archiving fails** the WAL piles up on disk and can fill it. `walg-check.sh` fails when the last archive is older than 30 minutes, when `failed_count` rises, when a file sits in the spool longer than 30 minutes, or when `pg_wal` is over 5 GB. It runs every 10 minutes from cron and pings `UBYHOST_WALG_PING_URL` only when healthy, so a missing ping is the alarm. On an alarm: `docker compose logs --tail 50 walg`.

#### Owner rollout (once; do it in a quiet hour)

AWS (one time, about 15 minutes):

1. Sign in to the AWS console, top right choose region **Europe (Frankfurt) eu-central-1**.
2. Open **S3**, click **Create bucket**. Name: `ubyhost-wal-<your-12-digit-account-id>-eu-central-1`. Keep **Block all public access** ticked. Leave **Versioning** off. Default encryption: SSE-S3. Click **Create bucket**. Use a separate bucket, not the one holding the pg_dump copies, so the lifecycle rule below cannot touch them.
3. Open the new bucket, tab **Management**, **Create lifecycle rule**. Name `expire-wal`. Scope: **This rule applies to all objects**, tick the warning box. Actions: tick **Expire current versions of objects**, **Days after object creation: 10**, and tick **Delete incomplete multipart uploads: 1 day**. Click **Create rule**.
4. Open **IAM**, **Policies**, **Create policy**, tab **JSON**, paste this (replace `BUCKET` with the bucket name), name it `ubyhost-walg`, click **Create policy**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListOnlyThePrefix",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::BUCKET",
      "Condition": {"StringLike": {"s3:prefix": ["postgres-wal", "postgres-wal/*"]}}
    },
    {
      "Sid": "ObjectsUnderThePrefix",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::BUCKET/postgres-wal/*"
    },
    {
      "Sid": "Location",
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::BUCKET"
    }
  ]
}
```

5. **IAM**, **Users**, **Create user**, name `ubyhost-walg`, no console access, **Attach policies directly**: `ubyhost-walg`. Open the user, tab **Security credentials**, **Create access key**, choose **Application running outside AWS**, copy both values into the password manager (the secret is shown once).

Server:

6. Generate the encryption key on your laptop: `openssl rand -hex 32`. Save it in the password manager and offline now.
7. On the server create `/opt/ubyhost/deploy/lightsail/.env.walg`, then `chmod 600` it and `chown root:root` it (the existing `.env.*` rule keeps it out of git):

```
WALG_S3_PREFIX=s3://BUCKET/postgres-wal
AWS_REGION=eu-central-1
AWS_ACCESS_KEY_ID=<from step 5>
AWS_SECRET_ACCESS_KEY=<from step 5>
WALG_COMPRESSION_METHOD=zstd
WALG_LIBSODIUM_KEY=<from step 6>
WALG_LIBSODIUM_KEY_TRANSFORM=hex
PGHOST=/var/run/postgresql
PGUSER=ubyhost
PGDATABASE=ubyhost
```

   Create this file **before** deploying: without it every `docker compose` command on the server fails. If `zstd` is rejected by `wal-g --version`/first push, set `brotli`.
8. Add `UBYHOST_WALG_PING_URL=<your dead-man URL>` to `.env` (create a second check in your dead-man service, separate from the backup one).
9. Merge 0997 and 0998, then deploy with `./scripts/deploy.sh`. It takes the mandatory pre-deploy pg_dump first. The database restarts once (archive_mode needs a restart): a short outage, acceptable at a quiet hour.
10. Verify: `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT archived_count, failed_count, last_archived_time FROM pg_stat_archiver;"` shows `archived_count` rising and `failed_count` 0. Then `docker compose logs --tail 20 walg` shows `wal-push` lines and `docker compose exec -T walg ls /walspool` is empty or nearly so.
11. Run the first base backup by hand: `./scripts/walg-backup.sh`. Then `docker compose exec -T walg wal-g backup-list`. Expected: one backup.
12. Add the two cron lines from [LIGHTSAIL](../LIGHTSAIL.md), then run `./scripts/walg-check.sh` once. Expected: `walg-check ok`.
13. Do the restore drill below. **Do not rely on WAL-G until it has passed once.**

#### Restore drill (mandatory; repeat quarterly with the age-key test above)

Restores into a scratch container; production is not touched. Run from `/opt/ubyhost/deploy/lightsail`. Pick `TARGET` as a UTC time after the base backup finished (`wal-g backup-list --detail` shows when).

```
docker volume create walg-drill
docker run --rm --user root --env-file .env.walg -v walg-drill:/restore ubyhost-postgres-walg:local \
  sh -c 'wal-g backup-fetch /restore LATEST && chown -R postgres:postgres /restore && chmod 700 /restore'
docker run --rm --user root -v walg-drill:/restore ubyhost-postgres-walg:local sh -c \
  "touch /restore/recovery.signal && printf \"restore_command = 'wal-g wal-fetch %%f %%p'\nrecovery_target_time = '2026-11-08 10:00:00+00'\nrecovery_target_action = 'promote'\n\" >> /restore/postgresql.auto.conf"
docker run -d --name walg-drill-pg --env-file .env.walg -v walg-drill:/var/lib/postgresql/data \
  ubyhost-postgres-walg:local postgres -c listen_addresses= -c archive_mode=off
sleep 20; docker logs --tail 30 walg-drill-pg
docker exec walg-drill-pg psql -U ubyhost -d ubyhost -Atc "SELECT pg_is_in_recovery(), now();"
docker exec walg-drill-pg psql -U ubyhost -d ubyhost -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 5;"
```

Replace the date in `recovery_target_time` with your `TARGET`. Pass: the log shows "recovery stopping before/after ... time" then "database system is ready", `pg_is_in_recovery` is `f`, and the top table counts are close to production's same query at that time. Clean up: `docker rm -f walg-drill-pg && docker volume rm walg-drill`. Write the date and result in the password manager note for this backup.

#### Real point-in-time restore (only with the owner's decision)

Stop `worker` and `ubyhost`, keep `postgres` stopped, copy the current data directory aside **encrypted** (`docker run --rm -v ubyhost-pgdata:/d alpine tar -C /d -c . | age -r "$UBYHOST_BACKUP_AGE_RECIPIENT" > pgdata-before-pitr.tar.age`), empty the volume, repeat the drill's fetch and recovery-config steps into `ubyhost-pgdata` (volume name instead of `walg-drill`), start `postgres`, check, then start `ubyhost worker`. Afterwards wait for the retention runner (it erases expired personal data) before reopening to guests, and delete `pgdata-before-pitr.tar.age` when no longer needed.

#### Rollback (if the deploy or archiving misbehaves)

1. `git revert` the merge commits of 0997 and 0998 (or deploy the previous release): the postgres service goes back to the plain pinned `postgres:16-alpine` image and loses `archive_mode`, `archive_timeout` and `archive_command`.
2. `docker compose rm -sf walg` removes the sidecar. Then `docker compose up -d postgres` restarts Postgres with archiving off. The data directory is compatible: it is the same Postgres 16 image digest.
3. Remove the two cron lines (`crontab -e`). The S3 data expires by lifecycle in 10 days; delete the IAM access key in the console if you are done with WAL-G.
4. If Postgres does not start: restore the pre-deploy dump with `AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh <stamp>` (the stamp deploy.sh printed).
5. If the disk is nearly full because WAL piled up: fix or roll back first, then `docker compose exec -T walg ls /walspool | wc -l`. Never delete files from `pg_wal` by hand.
````

Command: `grep -n 'WAL-G continuous archiving\|Restore drill\|Rollback' docs/OPERATIONS.md | tail -30`. Expected: three hits.

9. Lint. Commands: `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no new error; the repo's lint may check link targets: the `#wal-g-continuous-archiving-and-point-in-time-recovery` anchor must match) and `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`.

## 5. Do not touch

`backup.sh`, `pg-restore.sh`, `deploy.sh`, `docker-compose.yml`, the Dockerfile and `walg-ship.sh` (0997), all `.env*` files, `.gitignore`, `App/app/`. Rules 3 (no real bucket name, keys, account id or key value anywhere; placeholders only) and 9 apply: the runbook lives only in OPERATIONS.md; other files link to it. Do not run docker, aws or wal-g.

## 6. Commands

The pytest line (step 9), `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` (the test-map row for deploy scripts; if shellcheck is missing, say so), `python3 scripts/context_lint.py`. Never the full suite.

## 7. Acceptance

- [ ] `walg-check.sh` exits 1 and does not ping for: archive older than 30 minutes, never archived, pg_wal over 5 GB, a stale spool file, a rising `failed_count` (tests pass).
- [ ] `walg-backup.sh` runs `backup-push` before `delete retain FULL 7 --confirm`.
- [ ] OPERATIONS.md has the cost, retention (7 days, within the 30-day window), key custody, IAM policy JSON, click-by-click owner rollout, restore drill with `recovery_target_time`, real restore, and rollback.
- [ ] RETENTION.md has the WAL-G row; ENVIRONMENT.md has `UBYHOST_WALG_PING_URL`; LIGHTSAIL.md has both cron lines.
- [ ] `grep -rn 'AKIA\|LIBSODIUM_KEY=[0-9a-f]\{8\}' docs deploy | tail -30` shows nothing.
- [ ] Pytest line and context lint pass.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt (anchors A to F) is not found, or 0997 is not merged;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0998-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left: the "Owner rollout" in OPERATIONS.md, steps 1 to 13.

## Risk list (for the reviewer)

`deploy/lightsail/scripts/walg-check.sh` (the alarm logic and the ping-only-when-healthy rule), `walg-backup.sh` (the `delete retain` line deletes data), the IAM JSON and the lifecycle days in `docs/OPERATIONS.md` (scope, 10 days), and the RETENTION row.

## Owner steps

The full numbered, click-by-click rollout is written into `docs/OPERATIONS.md` by step 8 (AWS bucket, lifecycle rule, IAM policy and user, key, `.env.walg`, deploy in a quiet hour, verify `pg_stat_archiver`, first base backup, cron, restore drill, rollback). Summary for the PR description: (1) AWS bucket, lifecycle and least-privilege IAM user; (2) `.env.walg` on the server, mode 600, **before** deploy; (3) deploy in a quiet hour (one short Postgres restart, pre-deploy pg_dump runs first); (4) verify archiving; (5) first base backup and cron; (6) restore drill must pass before relying on it.
