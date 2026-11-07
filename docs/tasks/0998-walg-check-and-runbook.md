# 0998: WAL-G monitor, daily base backup, restore drills, runbook, owner rollout

Status: todo
Depends on: 0997 (merged) | Base commit: 47640cf | Branch: task/0998-walg-runbook
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the daily WAL-G base backup with 7-day retention, a monitor that fails loudly when archiving stalls or WAL piles up, and one runbook section with the owner's rollout, the two restore drills (the existing daily `pg_dump` and the new point-in-time restore), the real restore and the rollback. Downtime is acceptable; data loss is not.

## 2. Context

Rules: AGENTS.md rule 1 (data correctness first), rule 2 (privacy: backups must expire), rule 3 (no secrets, bucket name or account id in the repo), rule 9 (one explanation in one place: the runbook lives only in OPERATIONS.md; other files link to it).

Built by 0997 (must be merged; STOP if not): the production postgres service keeps its pinned Alpine image and `network_mode: none`; `archive_mode=${UBYHOST_PG_ARCHIVE:-off}`, `archive_timeout=300` and an `archive_command` that copies each WAL file durably into the spool volume `ubyhost-walspool` (mounted at `/walspool` in postgres and walg). The `walg` sidecar (profile `walg`, image `ubyhost-walg:local`, Debian Postgres 16 + WAL-G, uid 70, `.env.walg`, read-only data mount, socket volume) ships the spool with `walg-ship.sh` and deletes a file only after `wal-g wal-push` succeeded.

**Why there is no Postgres restore drill today.** Brief 0996 deletes `restore_test.sh` and `.github/workflows/restore-drill.yml` (they drilled the Litestream replica). Nothing tests that the daily `ubyhost-pg.dump.age` can be decrypted and restored. This brief adds that drill (owner-run, with the offline age identity) as well as the WAL-G drill.

**What `pg_stat_archiver` means here.** `archive_command` only copies into the spool, so `last_archived_time` proves the copy, not the upload. The monitor also checks the age of the oldest file in the spool (read from the postgres container, so it still works when `walg` is down) and that `walg` is running.

**Failure modes the monitor guards:** the copy fails (WAL piles up in `pg_wal`, `failed_count` rises), the upload fails or `walg` is down (files pile up in the spool), the owner forgot `UBYHOST_PG_ARCHIVE=on` (never archived). Both `pg_wal` (default limit 5 GB) and the spool (default 2 GB) sizes are checked so a full disk is seen before it happens. Known false alarm: with no database writes at all for 30 minutes, no segment is archived; raise `WALG_MAX_ARCHIVE_AGE_S` if that happens.

**Retention (`docs/privacy/RETENTION.md`, row "Encrypted backups": 30 days local/off-site):** WAL and base backups keep 7 days: `wal-g delete retain FULL 7 --confirm` after each daily base backup, plus an S3 lifecycle rule deleting objects older than 10 days as a safety net. Spool files live minutes (deleted after upload). Drill volumes are deleted the same day. A point-in-time restore brings back data that was erased after the restore point; the retention job must run before the restored database serves guests.

**Cost:** about USD 0.05 a month in PUT requests plus a few cents of storage and LIST. The monitor must not call S3 at all (no `wal-g wal-verify`, `backup-list` or `backup-fetch`).

**Cron times** (after 0995: local backup 03:00, S3 copy 03:30, Drive Sunday 04:00 UTC): WAL-G base backup daily 04:30 UTC, check every 10 minutes.

**Anchor A, `deploy/lightsail/scripts/backup.sh`, the dead-man style to follow (unchanged by 0995):**

```
if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: backup succeeded but the ping to UBYHOST_BACKUP_PING_URL failed" >&2
fi
```

**Anchor B, `docs/OPERATIONS.md`, the line to insert before (still there after 0995 and 0996, which only edit bullets above it):**

```
### Purging pre-OPS-1 plaintext backups (operator, one-time)
```

**Anchor C, `docs/privacy/RETENTION.md`, the row to put the new row after (0995 and 0996 do not change RETENTION.md):**

```
| Encrypted backups | `/data/backups`, Drive, S3 | snapshot age | 30 days local/off-site (G-D3) | `backup_data.sh` `UBYHOST_BACKUP_RETENTION_DAYS`; S3 lifecycle | Disaster recovery |
```

**Anchor D, `deploy/lightsail/docker-compose.yml` (from 0997):**

```
    command: ["/usr/local/bin/walg-ship.sh"]
```

**Anchor E, `docs/ENVIRONMENT.md`, the row to put the new rows after (0995 and 0996 do not change this row):**

```
| `UBYHOST_BACKUP_PING_URL` | unset | `deploy/lightsail/scripts/backup.sh` — pinged after each successful daily backup. Required in production: `preflight.sh` refuses to deploy while it is empty. |
```

**Anchor F, `docs/LIGHTSAIL.md`, the heading to insert before (0995 adds text above it, 0996 edits text below it; the heading itself stays):**

```
## Restore runbook (same instance)
```

**Context-rollout upload (orchestrator):** put files flat in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/walg-check.sh | create | monitor: walg running, archiver age, failed count, spool age and size, pg_wal size, ping |
| deploy/lightsail/scripts/walg-backup.sh | create | daily `wal-g backup-push`, then `delete retain FULL 7 --confirm`, then ping |
| App/tests/test_pg_backup_scripts.py | edit | append stub tests for the two scripts |
| docs/OPERATIONS.md | edit | one new subsection in "Backup and restore" |
| docs/privacy/RETENTION.md | edit | one row for WAL archives and base backups |
| docs/ENVIRONMENT.md | edit | three rows |
| docs/LIGHTSAIL.md | edit | the two cron lines and a link |

No other file may change.

## 4. Steps

1. Confirm 0997 is merged and the anchors exist. Command: `grep -c 'walg-ship.sh' deploy/lightsail/docker-compose.yml; grep -c 'Purging pre-OPS-1' docs/OPERATIONS.md; grep -c '^| Encrypted backups' docs/privacy/RETENTION.md; grep -c '^| `UBYHOST_BACKUP_PING_URL` | unset |' docs/ENVIRONMENT.md; grep -c '^## Restore runbook (same instance)' docs/LIGHTSAIL.md; grep -c 'UBYHOST_BACKUP_PING_URL}" >/dev/null' deploy/lightsail/scripts/backup.sh` (one command line, `; ` between). Expected: six numbers, each `1` or more. Any `0`: STOP.

2. Create `deploy/lightsail/scripts/walg-check.sh` with this content:

```bash
#!/usr/bin/env bash
# 0998: monitor for WAL-G archiving. Exits 1 (and does NOT ping the dead-man URL)
# when the walg container is down, archiving is late or failing, a file is stuck
# in the spool, or pg_wal or the spool is large (the disk would fill up).
# Cron every 10 minutes: docs/LIGHTSAIL.md. Runbook: docs/OPERATIONS.md.
# Reads only pg_stat_archiver, file ages and directory sizes. It never calls S3.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

MAX_AGE_S="${WALG_MAX_ARCHIVE_AGE_S:-1800}"      # 30 minutes
MAX_SPOOL_AGE_S="${WALG_MAX_SPOOL_AGE_S:-1800}"  # 30 minutes
PGWAL_MAX_MB="${WALG_PGWAL_MAX_MB:-5120}"        # 5 GB
SPOOL_MAX_MB="${WALG_SPOOL_MAX_MB:-2048}"        # 2 GB
STATE="${WALG_CHECK_STATE:-/var/tmp/ubyhost-walg-check.state}"

problems=()

if [ -z "$(docker compose ps -q --status running walg 2>/dev/null)" ]; then
  problems+=("the walg container is not running (COMPOSE_PROFILES must contain walg): nothing is shipped to S3")
fi

row="$(docker compose exec -T postgres psql -U ubyhost -d ubyhost -Atc \
  "SELECT COALESCE(EXTRACT(EPOCH FROM now() - last_archived_time)::bigint, -1), failed_count FROM pg_stat_archiver" 2>/dev/null | tr -d '\r')"
if [ -z "${row}" ]; then
  problems+=("cannot read pg_stat_archiver (is the postgres container running?)")
else
  age="${row%%|*}"
  failed="${row##*|}"
  if [ "${age}" -lt 0 ] 2>/dev/null; then
    problems+=("pg_stat_archiver has never archived a WAL file (is UBYHOST_PG_ARCHIVE=on in .env?)")
  elif [ "${age}" -gt "${MAX_AGE_S}" ] 2>/dev/null; then
    problems+=("last WAL archived ${age}s ago (limit ${MAX_AGE_S}s)")
  fi
  prev=0
  [ -f "${STATE}" ] && prev="$(cat "${STATE}" 2>/dev/null || echo 0)"
  if [ "${failed}" -gt "${prev}" ] 2>/dev/null; then
    problems+=("failed_count rose from ${prev} to ${failed}: archive_command fails (docker compose logs --tail 50 postgres)")
  fi
  printf '%s' "${failed}" > "${STATE}" 2>/dev/null || true
fi

oldest="$(docker compose exec -T postgres sh -c \
  'find /walspool -maxdepth 1 -type f ! -name "*.tmp" -exec stat -c %Y {} \; | sort -n | head -1' 2>/dev/null | tr -d '\r')"
if [ -n "${oldest}" ]; then
  spool_age=$(( $(date +%s) - oldest ))
  if [ "${spool_age}" -gt "${MAX_SPOOL_AGE_S}" ]; then
    problems+=("oldest WAL file in the spool is ${spool_age}s old: the upload to S3 is stuck (docker compose logs --tail 50 walg)")
  fi
fi

spool_mb="$(docker compose exec -T postgres sh -c 'du -sm /walspool | cut -f1' 2>/dev/null | tr -d '\r')"
if [ -n "${spool_mb}" ] && [ "${spool_mb}" -gt "${SPOOL_MAX_MB}" ] 2>/dev/null; then
  problems+=("the spool holds ${spool_mb} MB (limit ${SPOOL_MAX_MB} MB): uploads are failing and the disk is filling")
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

Command: `chmod +x deploy/lightsail/scripts/walg-check.sh && bash -n deploy/lightsail/scripts/walg-check.sh && echo ok | tail -30`. Expected: `ok`.

3. Create `deploy/lightsail/scripts/walg-backup.sh`:

```bash
#!/usr/bin/env bash
# 0998: daily WAL-G base backup, then keep the newest 7 (7 days). Cron 04:30 UTC,
# after backup.sh and the S3 copy (docs/LIGHTSAIL.md). The pg_dump backup stays
# the primary copy; this is the point-in-time path. Runbook: docs/OPERATIONS.md.
# A failed backup-push stops here: nothing is deleted and no ping is sent.
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

if [ -n "${UBYHOST_WALG_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_WALG_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: base backup succeeded but the ping to UBYHOST_WALG_BACKUP_PING_URL failed" >&2
fi
echo "WAL-G base backup done; kept the newest 7."
```

Command: `chmod +x deploy/lightsail/scripts/walg-backup.sh && bash -n deploy/lightsail/scripts/walg-backup.sh && echo ok | tail -30`. Expected: `ok`.

4. Append tests to the end of `App/tests/test_pg_backup_scripts.py` (`shutil`, `os`, `subprocess`, `pytest`, `SCRIPTS` and `calls` already exist in the file; the file's `make_tree` copies only two scripts, so these tests build their own tree):

```python
CHECK_DOCKER_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
case "$*" in
  *"ps -q --status running walg"*) [ "${WALG_RUNNING:-1}" = 1 ] && echo walgid ;;
  *pg_stat_archiver*) echo "${ARCH_ROW:-60|0}" ;;
  *"stat -c %Y"*) [ -n "${SPOOL_MTIME:-}" ] && echo "$SPOOL_MTIME" ;;
  *"du -sm /walspool"*) echo "${SPOOL_MB:-1}" ;;
  *"du -sm /var/lib/postgresql/data/pg_wal"*) echo "${PGWAL_MB:-100}" ;;
  *"backup-push"*) [ "${BACKUP_FAIL:-0}" = 1 ] && exit 1 ;;
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


def run_walg(script, tmp_path, extra=None):
    root, bindir, log = make_check_tree(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "WALG_CHECK_STATE": str(tmp_path / "state"),
           "UBYHOST_WALG_PING_URL": "https://ping.invalid/check",
           "UBYHOST_WALG_BACKUP_PING_URL": "https://ping.invalid/base"}
    env.update(extra or {})
    result = subprocess.run(["bash", str(root / "scripts" / script)], cwd=root, env=env,
                            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    return result, calls(log)


@pytest.mark.parametrize("script", ["walg-check.sh", "walg-backup.sh"])
def test_walg_scripts_pass_bash_syntax(script):
    result = subprocess.run(["bash", "-n", str(SCRIPTS / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("extra,expected_fail", [
    ({}, False),
    ({"ARCH_ROW": "4000|0"}, True),      # last archive older than 30 minutes
    ({"ARCH_ROW": "-1|0"}, True),        # never archived (UBYHOST_PG_ARCHIVE not on)
    ({"PGWAL_MB": "6000"}, True),        # pg_wal over 5 GB
    ({"SPOOL_MB": "3000"}, True),        # spool over 2 GB
    ({"SPOOL_MTIME": "1000"}, True),     # spool file from 1970: upload stuck
    ({"WALG_RUNNING": "0"}, True),       # sidecar down
])
def test_walg_check_exit_codes(tmp_path, extra, expected_fail):
    result, recorded = run_walg("walg-check.sh", tmp_path, extra)
    assert (result.returncode != 0) == expected_fail, result.stderr
    assert ("ping.invalid/check" in recorded) == (not expected_fail)  # dead-man ping only when healthy
    assert "wal-g" not in recorded  # the monitor never calls WAL-G or S3


def test_walg_check_flags_rising_failed_count(tmp_path):
    (tmp_path / "state").write_text("2")
    result, _ = run_walg("walg-check.sh", tmp_path, {"ARCH_ROW": "60|5"})
    assert result.returncode == 1
    assert "failed_count rose" in result.stderr


def test_walg_backup_pushes_then_retains_seven_then_pings(tmp_path):
    result, recorded = run_walg("walg-backup.sh", tmp_path)
    assert result.returncode == 0, result.stderr
    push = recorded.index("exec -T walg wal-g backup-push /var/lib/postgresql/data")
    delete = recorded.index("exec -T walg wal-g delete retain FULL 7 --confirm")
    assert push < delete < recorded.index("ping.invalid/base")


def test_walg_backup_failure_deletes_nothing_and_does_not_ping(tmp_path):
    result, recorded = run_walg("walg-backup.sh", tmp_path, {"BACKUP_FAIL": "1"})
    assert result.returncode != 0
    assert "delete retain" not in recorded
    assert "ping.invalid" not in recorded
```

Command: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. If a stub pattern does not match, fix only the stub, once; a second failure: STOP.

5. `docs/privacy/RETENTION.md`: insert directly after the anchor C row this single row:

```
| WAL archives and base backups (WAL-G) | S3 eu-central-1, a dedicated bucket, encrypted on the server before upload; local spool volume `ubyhost-walspool` until uploaded | base backup age | 7 days (`wal-g delete retain FULL 7`); S3 lifecycle deletes objects older than 10 days as a safety net; spool files are deleted right after a confirmed upload | `deploy/lightsail/scripts/walg-backup.sh`; `deploy/lightsail/walg/walg-ship.sh`; S3 lifecycle rule | Disaster recovery |
```

Command: `grep -c 'WAL-G' docs/privacy/RETENTION.md | tail -30`. Expected: `1`.

6. `docs/ENVIRONMENT.md`: directly after the anchor E row, insert these three rows:

```
| `UBYHOST_PG_ARCHIVE` | `off` | `deploy/lightsail/docker-compose.yml` postgres `archive_mode`. Production sets `on` together with `walg` in `COMPOSE_PROFILES` (runbook: OPERATIONS.md, "WAL-G continuous archiving and point-in-time recovery"). Changing it restarts Postgres. |
| `UBYHOST_WALG_PING_URL` | unset | `deploy/lightsail/scripts/walg-check.sh` — pinged only when archiving is healthy (every 10 minutes); its own dead-man check, separate from the backup one. |
| `UBYHOST_WALG_BACKUP_PING_URL` | unset | `deploy/lightsail/scripts/walg-backup.sh` — pinged after each successful daily WAL-G base backup; a third dead-man check (daily period). |
```

Command: `grep -c 'UBYHOST_PG_ARCHIVE\|UBYHOST_WALG_PING_URL\|UBYHOST_WALG_BACKUP_PING_URL' docs/ENVIRONMENT.md | tail -30`. Expected: `3`.

7. `docs/LIGHTSAIL.md`: directly before the anchor F heading, insert this block (with one blank line after it):

````markdown
WAL-G point-in-time recovery (production only, after the rollout in [OPERATIONS](OPERATIONS.md#wal-g-continuous-archiving-and-point-in-time-recovery)): daily base backup 04:30 UTC and a check every 10 minutes:

```bash
(crontab -l 2>/dev/null; echo "30 4 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/walg-backup.sh >> /var/log/ubyhost-walg-backup.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "*/10 * * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/walg-check.sh >> /var/log/ubyhost-walg-check.log 2>&1") | crontab -
```
````

(The outer four-backtick fence is only for this brief; insert the sentence and the inner ```` ```bash ```` block.) Command: `grep -c 'walg-backup.sh >> /var/log\|walg-check.sh >> /var/log' docs/LIGHTSAIL.md | tail -30`. Expected: `2`.

8. `docs/OPERATIONS.md`: insert the new subsection below directly before the anchor B line. Write it exactly (the outer five-backtick fence is only for this brief):

`````markdown
### WAL-G continuous archiving and point-in-time recovery

The daily age-encrypted `pg_dump` (above) stays the primary backup. WAL-G adds point-in-time recovery for the last 7 days; at most about 5 minutes of writes can be lost (`archive_timeout=300`). Downtime is acceptable here; losing data is not. Postgres keeps its pinned Alpine image and has no network: `archive_command` copies each finished WAL file durably into the `ubyhost-walspool` volume, and the `walg` container (profile `walg`, Debian Postgres 16 image with WAL-G) uploads it to S3 and deletes the local copy only after the upload succeeded (briefs 0997, 0998). The daily base backup runs in `walg` through the Postgres socket and a read-only data mount.

- **Cost.** About USD 0.05 a month in PUT requests plus a few cents of storage. WAL-G does not read back in normal running and `walg-check.sh` never calls S3. Check Cost Explorer after 7 days; expect under USD 1 a month.
- **Retention.** 7 days: `wal-g delete retain FULL 7 --confirm` after each daily base backup, plus an S3 lifecycle rule at 10 days (see the RETENTION table row).
- **Encryption and key custody.** WAL-G encrypts on the server before upload with `WALG_LIBSODIUM_KEY` (32 random bytes as 64 hex characters, `openssl rand -hex 32`). It is a different key from the age identity. Keep it in the password manager plus one offline copy; it is also in `.env.walg` on the server (mode 600, root). Never in the repo or a chat. Whoever holds it and the S3 keys can read the archives; if it is lost, every archive is unreadable and only the pg_dump backups remain.
- **Alarms.** `walg-check.sh` (cron every 10 minutes) fails when `walg` is not running, the last archive is older than 30 minutes, `failed_count` rises, a file sits in the spool longer than 30 minutes, the spool is over 2 GB or `pg_wal` is over 5 GB. It pings `UBYHOST_WALG_PING_URL` only when healthy; `walg-backup.sh` pings `UBYHOST_WALG_BACKUP_PING_URL` only after a good base backup. A missing ping is the alarm. On an alarm: `./scripts/walg-check.sh`, then `docker compose logs --tail 50 walg` and `docker compose logs --tail 50 postgres`. With no database writes for 30 minutes no WAL is archived: a false alarm; raise `WALG_MAX_ARCHIVE_AGE_S` in `.env` if it repeats. **Never delete files from `pg_wal` by hand.**

#### Owner rollout (once; in a quiet hour; about 60 minutes)

Order matters: AWS, key and `.env.walg` come before the deploy; the drills come before you rely on it.

AWS (about 15 minutes):

1. Sign in to the AWS console. Top right, choose region **Europe (Frankfurt) eu-central-1**.
2. Open **S3**, click **Create bucket**. Name: `ubyhost-wal-` plus 8 random lowercase letters (no account id in the name). Keep **Block all public access** ticked, **Versioning** off, default encryption SSE-S3. Click **Create bucket**. Use a separate bucket from the pg_dump copies, so the rule below cannot touch them. Write the name in the password manager, not in the repo.
3. Open the new bucket, tab **Management**, **Create lifecycle rule**. Name `expire-wal`. Scope: **Apply to all objects in the bucket**, tick the confirmation box. Actions: tick **Expire current versions of objects** with **Days after object creation: 10**, and tick **Delete expired object delete markers or incomplete multipart uploads**, then **Delete incomplete multipart uploads**, **Number of days: 1**. Click **Create rule**.
4. Open **IAM**, **Policies**, **Create policy**, tab **JSON**, paste this (replace both `BUCKET` with your bucket name), click **Next**, name it `ubyhost-walg`, click **Create policy**:

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

5. **IAM**, **Users**, **Create user**, name `ubyhost-walg`, no console access, **Attach policies directly**: tick `ubyhost-walg`, **Create user**. Open the user, tab **Security credentials**, **Create access key**, choose **Application running outside AWS**, copy both values into the password manager (the secret is shown once).

Key and dead-man checks (about 5 minutes):

6. On your laptop: `openssl rand -hex 32`. Save the 64 characters in the password manager and in your offline copy now.
7. In your dead-man service (healthchecks.io) create two new checks: `ubyhost-walg-check` (period 10 minutes, grace 30 minutes) and `ubyhost-walg-backup` (period 1 day, grace 2 hours). Copy both ping URLs.

Server, before the deploy (about 15 minutes; `cd /opt/ubyhost/deploy/lightsail` first):

8. Make sure 0997 and 0998 are merged and pulled: `git log --oneline -3`.
9. Create the secrets file: `sudo install -m 600 -o root -g root /dev/null .env.walg && sudo nano .env.walg`, paste this, fill in the four values, save (Ctrl+O, Enter, Ctrl+X):

```
WALG_S3_PREFIX=s3://BUCKET/postgres-wal
AWS_REGION=eu-central-1
AWS_ACCESS_KEY_ID=<from step 5>
AWS_SECRET_ACCESS_KEY=<from step 5>
WALG_COMPRESSION_METHOD=zstd
WALG_LIBSODIUM_KEY=<from step 6>
WALG_LIBSODIUM_KEY_TRANSFORM=hex
WALG_UPLOAD_CONCURRENCY=2
PGHOST=/var/run/postgresql
PGUSER=ubyhost
PGDATABASE=ubyhost
```

   `.env.*` is git-ignored. Check: `ls -l .env.walg` shows `-rw------- 1 root root`.
10. Create the spool volume owned by the postgres user (uid 70) of the production image: `docker volume create ubyhost-walspool && docker run --rm --network none --user root -v ubyhost-walspool:/walspool postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab sh -c 'chown 70:70 /walspool && chmod 700 /walspool && sync /walspool && ls -ldn /walspool'`. Expected: a line starting `drwx------` with `70 70`. Compose later warns that this volume "already exists but was not created by Docker Compose": harmless. (If `sync /walspool` errors here, stop and tell the orchestrator: the `archive_command` needs it.)
11. Edit `.env` (`sudo nano .env`): add `UBYHOST_PG_ARCHIVE=on`, `UBYHOST_WALG_PING_URL=<check URL>` and `UBYHOST_WALG_BACKUP_PING_URL=<backup URL>` from step 7. If a `COMPOSE_PROFILES=` line exists, add `,walg` to its end (for example `COMPOSE_PROFILES=monitoring,walg`); if not, add `COMPOSE_PROFILES=walg`. Save.
12. Build the sidecar and test the S3 keys before anything changes in Postgres: `docker compose build walg 2>&1 | tail -5`, then `docker compose run --rm --no-deps walg wal-g backup-list 2>&1 | tail -5`. Expected: no error, a message that no backups were found. An `AccessDenied` or `NoSuchBucket` error: fix `.env.walg` and repeat; do not deploy.
13. Deploy: `./scripts/deploy.sh 2>&1 | tail -30`. It takes the mandatory pre-deploy pg_dump first (the output shows "Mandatory pre-deploy backup" and a stamp: write the stamp down). Postgres restarts once, because `archive_mode` only changes on restart; the app is unavailable for well under a minute.

Verify (about 10 minutes):

14. Wait 10 minutes, then `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT archived_count, failed_count, last_archived_time FROM pg_stat_archiver;"`. Expected: `archived_count` above 0 and `failed_count` 0. Then `docker compose logs --tail 20 walg` (no errors; an error with "read-only file system" or "libsodium": run the rollback below and tell the orchestrator) and `docker compose exec -T postgres ls /walspool` (empty or one or two files).
15. First base backup by hand: `./scripts/walg-backup.sh 2>&1 | tail -10`, then `docker compose exec -T walg wal-g backup-list`. Expected: one backup.
16. Add the two cron lines from [LIGHTSAIL](LIGHTSAIL.md) (WAL-G point-in-time recovery), then `./scripts/walg-check.sh`. Expected: `walg-check ok`, and the healthchecks.io check turns green.
17. Do drill 1 and, at least 20 minutes after step 15, drill 2 below. **Do not rely on WAL-G until drill 2 has passed once.** Write the date and result of each drill in the password manager note.

#### Shared step: the row-count query (both drills)

Run once per drill session, from `/opt/ubyhost/deploy/lightsail`. It writes a query file and the production counts, one line per table: `table rows`.

```
cat > /dev/shm/counts.sql <<'SQL'
SELECT c.relname, (xpath('/row/n/text()', query_to_xml(format('SELECT count(*) AS n FROM %I.%I', n.nspname, c.relname), false, true, '')))[1]::text
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = 'public' ORDER BY 1;
SQL
docker compose exec -T postgres psql -U ubyhost -d ubyhost -At -F ' ' < /dev/shm/counts.sql | LC_ALL=C sort > /dev/shm/counts-prod.txt
wc -l /dev/shm/counts-prod.txt
```

Compare a drill's counts file (`/dev/shm/counts-drill.txt`) with production:

```
LC_ALL=C join -v 1 /dev/shm/counts-prod.txt /dev/shm/counts-drill.txt
LC_ALL=C join /dev/shm/counts-prod.txt /dev/shm/counts-drill.txt > /dev/shm/counts-both.txt
awk '$2 > 0 && $3 == 0 {print "EMPTY IN RESTORE:", $1; bad=1} END {exit bad}' /dev/shm/counts-both.txt && echo "counts ok"
cat /dev/shm/counts-both.txt
```

Pass: the first command prints nothing (no table is missing), the third prints `counts ok`, and each line (`table production restored`) shows close numbers, in particular for `user_account`, `legal_entity`, `apartment`, `reservation`, `guest` and `submission` (the tables `deploy.sh` counts). Differences are only the writes and retention deletions since the restore point.

#### Drill 1: restore the daily pg_dump (mandatory; quarterly, and after any backup change)

This is the only test of the primary backup. Production is not touched: the dump is restored into a throwaway container with the production image and no network. The age identity is needed for this drill only; it stays in memory (`/dev/shm`) and is shredded at the end.

```
cd /opt/ubyhost/deploy/lightsail
STAMP="$(docker compose exec -T ubyhost sh -c 'ls -1 /data/backups | sort -r | sed -n 1p' | tr -d '\r')"; echo "$STAMP"
docker cp "$(docker compose ps -q ubyhost)":/data/backups/"$STAMP"/ubyhost-pg.dump.age /dev/shm/drill.dump.age
ls -l /dev/shm/drill.dump.age
(umask 077; cat > /dev/shm/drill.agekey)
```

After the last line, paste the private age identity from the password manager (the `AGE-SECRET-KEY-1...` line), press Enter, then Ctrl+D. Then:

```
docker run -d --name pgdump-drill --network none -e POSTGRES_USER=ubyhost -e POSTGRES_DB=ubyhost -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab
until docker logs pgdump-drill 2>&1 | grep -q 'PostgreSQL init process complete'; do sleep 2; done; sleep 5
docker exec pgdump-drill pg_isready -U ubyhost -d ubyhost
set -o pipefail; age -d -i /dev/shm/drill.agekey /dev/shm/drill.dump.age | docker exec -i pgdump-drill pg_restore -U ubyhost -d ubyhost --no-owner --exit-on-error --single-transaction && echo "restore ok"
docker exec -i pgdump-drill psql -U ubyhost -d ubyhost -At -F ' ' < /dev/shm/counts.sql | LC_ALL=C sort > /dev/shm/counts-drill.txt
```

Pass: `pg_isready` says "accepting connections", the restore prints `restore ok` and the row-count comparison above passes (the dump is from the night, so production may have a few more rows). Clean up, always, also after a failure:

```
docker rm -f pgdump-drill; shred -u /dev/shm/drill.agekey; rm -f /dev/shm/drill.dump.age /dev/shm/counts-drill.txt /dev/shm/counts-both.txt
```

If decryption fails, the identity does not match `UBYHOST_BACKUP_AGE_RECIPIENT`: stop and treat every encrypted backup as unreadable until fixed (OPERATIONS, key custody above).

#### Drill 2: point-in-time restore from WAL-G (mandatory once; then quarterly with drill 1)

Restores into a scratch volume with the `walg` image, which has network and WAL-G; production is not touched. The target is 15 minutes ago, so a base backup must have finished before that (`docker compose exec -T walg wal-g backup-list --detail`).

```
cd /opt/ubyhost/deploy/lightsail
TARGET="$(date -u -d '15 minutes ago' '+%Y-%m-%d %H:%M:%S+00')"; echo "$TARGET"
docker volume create walg-drill
docker run --rm --user root --env-file .env.walg -v walg-drill:/restore ubyhost-walg:local wal-g backup-fetch /restore LATEST
cat > /dev/shm/walg-recovery.conf <<EOF
restore_command = 'wal-g wal-fetch %f %p'
recovery_target_time = '${TARGET}'
recovery_target_action = 'promote'
EOF
docker run --rm --user root -v walg-drill:/restore -v /dev/shm/walg-recovery.conf:/r.conf:ro ubyhost-walg:local \
  sh -c 'cat /r.conf >> /restore/postgresql.auto.conf && touch /restore/recovery.signal && chown -R postgres:postgres /restore && chmod 700 /restore'
docker run -d --name walg-drill-pg --env-file .env.walg -v walg-drill:/var/lib/postgresql/data ubyhost-walg:local \
  postgres -c listen_addresses= -c archive_mode=off
for i in $(seq 1 60); do docker exec walg-drill-pg psql -U ubyhost -d ubyhost -Atc 'SELECT pg_is_in_recovery()' 2>/dev/null | grep -qx f && break; sleep 10; done
docker logs walg-drill-pg 2>&1 | grep -E 'recovery stopping|database system is ready|FATAL' | tail -5
docker exec walg-drill-pg psql -U ubyhost -d ubyhost -Atc "SELECT pg_is_in_recovery(), pg_last_xact_replay_timestamp(), datcollate FROM pg_database WHERE datname = 'ubyhost';"
docker exec -i walg-drill-pg psql -U ubyhost -d ubyhost -At -F ' ' < /dev/shm/counts.sql | LC_ALL=C sort > /dev/shm/counts-drill.txt
```

Pass: the log shows `recovery stopping before commit ... time ...` and `database system is ready to accept connections`; the query shows `f`, a replay time just before `TARGET` (within a few minutes), and the database locale; the row-count comparison above passes (counts as of 15 minutes ago). A `FATAL` such as "recovery ended before configured recovery target was reached" means WAL is missing in S3: WAL-G is not usable; tell the orchestrator. "database locale is incompatible with operating system" also goes to the orchestrator. Clean up, always:

```
docker rm -f walg-drill-pg; docker volume rm walg-drill; rm -f /dev/shm/walg-recovery.conf /dev/shm/counts-*.txt /dev/shm/counts.sql
```

#### Real point-in-time restore (only with the owner's decision)

The production data directory is never replaced by hand. Recover in the scratch container, then load the result into production as a pg_dump through the tested `pg-restore.sh` path. The app is down for a few minutes during `pg-restore.sh`.

1. Choose `TARGET` in UTC, a minute before the bad change. `./scripts/backup.sh` first: it saves today's state, so this restore can be undone with `pg-restore.sh <that stamp>`.
2. Run drill 2 with `TARGET="YYYY-MM-DD HH:MM:SS+00"` (your time) instead of "15 minutes ago", and stop before its clean-up. Check its pass conditions.
3. Put the age identity into `/dev/shm/drill.agekey` as in drill 1. Then:

```
set -o pipefail
RECIPIENT="$(grep '^UBYHOST_BACKUP_AGE_RECIPIENT=' .env | cut -d= -f2-)"
PITR_STAMP="$(date -u +%Y%m%dT%H%M%SZ)-9"; echo "$PITR_STAMP"
docker exec walg-drill-pg pg_dump -U ubyhost -Fc ubyhost | age -r "$RECIPIENT" \
  | docker compose exec -T ubyhost sh -c "mkdir -p /data/backups/$PITR_STAMP && cat > /data/backups/$PITR_STAMP/ubyhost-pg.dump.age" && echo "export ok"
AGE_IDENTITY_FILE=/dev/shm/drill.agekey ./scripts/pg-restore.sh "$PITR_STAMP"
```

4. Sign in, open one stay. Then run the retention job once before guests use the site, because the restore brought back data erased after `TARGET` (see "Retention and what is actually deleted").
5. Clean up as in drill 2, and `shred -u /dev/shm/drill.agekey`.

#### Rollback (if the deploy or archiving misbehaves)

The production Postgres image and data directory are unchanged by WAL-G, so rollback is configuration only:

1. `cd /opt/ubyhost/deploy/lightsail && docker compose stop walg && docker compose rm -f walg`.
2. In `.env` set `UBYHOST_PG_ARCHIVE=off` and remove `walg` from `COMPOSE_PROFILES` (`sudo nano .env`).
3. `docker compose up -d postgres` (one short restart, archiving off). Check `docker compose ps`: postgres `healthy`, app up.
4. Remove the two WAL-G cron lines: `crontab -e`, delete the lines with `walg-`, save. Pause the two healthchecks.io checks.
5. If Postgres does not come up: `docker compose logs --tail 50 postgres`, then put the age identity into `/dev/shm/drill.agekey` as in drill 1 and restore the pre-deploy dump: `AGE_IDENTITY_FILE=/dev/shm/drill.agekey ./scripts/pg-restore.sh <stamp from step 13>`.
6. Files left in the spool are copies; after the rollback they may be deleted with `docker volume rm ubyhost-walspool` (only once `UBYHOST_PG_ARCHIVE=off` is live). Never delete files from `pg_wal` by hand.
7. If you stop using WAL-G: delete the IAM access key in the console. The S3 objects expire by lifecycle within 10 days.
`````

Command: `grep -n '^### WAL-G continuous archiving\|^#### ' docs/OPERATIONS.md | tail -30`. Expected: the `###` heading and six `####` headings (Owner rollout, Shared step, Drill 1, Drill 2, Real point-in-time restore, Rollback), all just above `### Purging pre-OPS-1`.

9. Lint and tests. Commands: `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no new error; the link `OPERATIONS.md#wal-g-continuous-archiving-and-point-in-time-recovery` must resolve), `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` (the test-map row for deploy scripts; expected no output; if shellcheck is missing, say so), and `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`.

## 5. Do not touch

`backup.sh`, `pg-restore.sh`, `deploy.sh`, `preflight.sh`, `docker-compose.yml`, `deploy/lightsail/walg/*` (0997), all `.env*` files, `.gitignore`, `App/app/`. Rules 3 (no real bucket name, keys, account id or key value anywhere; placeholders only) and 9 apply. Do not run docker, aws or wal-g.

## 6. Commands

The pytest line, `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`, `python3 scripts/context_lint.py 2>&1 | tail -30`. Never the full suite.

## 7. Acceptance

- [ ] `walg-check.sh` exits 1 and does not ping for: walg down, archive older than 30 minutes, never archived, pg_wal over 5 GB, spool over 2 GB, a stale spool file, a rising `failed_count`; exits 0 and pings when healthy (tests pass).
- [ ] `walg-backup.sh` runs `backup-push`, then `delete retain FULL 7 --confirm`, then the ping; a failed push deletes nothing and does not ping (tests pass).
- [ ] OPERATIONS.md has, in one subsection: cost, retention, key custody, alarms, the IAM policy JSON, the numbered rollout (AWS, key, `.env.walg`, spool volume, `.env`, build and S3 test, deploy with the pre-deploy dump, verify, first base backup, cron), drill 1 (pg_dump decrypt and restore with row counts), drill 2 (`recovery_target_time`), real restore via `pg-restore.sh`, rollback.
- [ ] RETENTION.md has the WAL-G row; ENVIRONMENT.md has the three rows; LIGHTSAIL.md has both cron lines (04:30 and every 10 minutes) and the link.
- [ ] `grep -rn 'AKIA\|LIBSODIUM_KEY=[0-9a-f]\{8\}\|AGE-SECRET-KEY-1[0-9A-Z]' docs deploy | tail -30` shows nothing.
- [ ] Pytest line, shellcheck and context lint pass.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor (A to F) is not found, or 0997 is not merged;
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
6. Owner steps left: the "Owner rollout" in OPERATIONS.md, steps 1 to 17, including both drills.

PR text, for rule 2: new outbound requests are the two dead-man pings (`UBYHOST_WALG_PING_URL`, `UBYHOST_WALG_BACKUP_PING_URL`), so a stopped archive or base backup is noticed; no personal data is sent.

## Risk list (for the reviewer)

`deploy/lightsail/scripts/walg-check.sh` (alarm logic, ping only when healthy, never S3), `walg-backup.sh` (`delete retain` deletes data; must not run after a failed push), the IAM JSON and lifecycle days in `docs/OPERATIONS.md`, the drill commands (they must never write to production: drill 1 has `--network none` and its own container; drill 2 its own volume), the rollback order, and the RETENTION row.

## Owner steps

All in `docs/OPERATIONS.md`, "WAL-G continuous archiving and point-in-time recovery", written by step 8. Summary for the PR description: (1) AWS bucket, 10-day lifecycle, least-privilege IAM user; (2) libsodium key in the password manager and offline; (3) `.env.walg` (mode 600), spool volume, `.env` lines and `docker compose build walg` with the S3 test, all **before** the deploy; (4) deploy in a quiet hour (pre-deploy pg_dump runs first; one short Postgres restart); (5) verify, first base backup, cron; (6) drill 1 (pg_dump) and drill 2 (point in time) must pass before relying on WAL-G; rollback is `.env` only.
