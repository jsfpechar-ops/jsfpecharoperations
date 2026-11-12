# 1151: Google Drive copy daily instead of weekly

> Renumbered from 1134 on 2026-11-12: main took 1134 (#933). Commits made before the rename say "1134".

Status: review
Depends on: none | Base commit: current HEAD of the branch | Branch: claude/fervent-cray-1qsrfa
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner decision 2026-11-12: the off-AWS Google Drive copy runs daily, not weekly, while it stays cheap. The cron line moves to `0 4 * * *`, `backup-gdrive.sh` stops taking its own second dump, and every doc that says weekly or Sunday is corrected.

## 2. Context

- `backup.sh` runs from cron at 03:00 UTC daily. `backup-s3.sh` runs at 03:30. The Drive job runs at 04:00 (today: Sundays only, `0 4 * * 0`).
- `deploy/lightsail/scripts/backup-gdrive.sh` line 2 says "snapshot DB on the server" and line 36 is `./scripts/backup.sh`. So run daily at 04:00 it would take a second pg_dump and a second snapshot folder every day, 60 minutes after the 03:00 one.
- Decision (smallest exact diff): delete line 36 and instead refuse to upload when the newest snapshot folder is not from today (UTC). The folder name starts with `YYYYMMDDTHHMMSSZ` (`App/scripts/backup_data.sh` line 19), so `${LATEST%%T*}` is the date. If the 03:00 backup failed there is no fresh folder, so the job fails loudly instead of re-uploading yesterday's. The pre-deploy snapshots are also folders of the same shape and are fine to upload.
- Consequence for a manual run: before 03:00 UTC, or after a failed backup, the owner first runs `./scripts/backup.sh` (owner step 3).
- Retention: `RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"` in `backup-gdrive.sh` (line 21) is the default, and the script prunes with `rclone delete --min-age "${RETENTION_DAYS}d"` then `rclone rmdirs --leave-root`. Drive is bounded to about 30 days. Production `.env` sets the variable to `7` for local snapshots, and cron does not load `.env`, so the Drive job keeps 30 unless the owner exports the variable. Daily at 30 days means about 30 to 31 folders on Drive. Size is archive size (`ubyhost-backup.tar.age` plus `ubyhost-pg.dump.age`) times 30. The archive size is unknown here; the owner checks it (owner step 5). Example: a 50 MB folder is about 1.5 GB, inside the free 15 GB.
- Rclone remote used by the script: `gdrive:`, folder `UbyHost-backups` (`RCLONE_REMOTE`, `RCLONE_BACKUP_FOLDER` defaults).
- If any "old" text below is not found verbatim in its file: STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/backup-gdrive.sh | edit | header comment, drop own backup, add freshness guard |
| deploy/lightsail/scripts/setup-server.sh | edit | cron hint lines 75-76 |
| docs/LIGHTSAIL.md | edit | lines 236, 223, 239, 267 |
| docs/OPERATIONS.md | edit | line 642 |
| docs/DISASTER_RECOVERY.md | edit | lines 128, 133, 137 |
| deploy/lightsail/README.md | edit | lines 56 and 85-89 |
| docs/plans/portable-disaster-recovery.md | edit | lines 13, 20, 45 |

No other file may change. Do not edit `App/` or `go/`. Note: `docs/plans/portable-disaster-recovery.md` may already show as modified before you start; edit it anyway and let step 7 commit it.

## 4. Steps

Commit each step as `1151 step k` (`git add <that file>`, `git commit -m "1151 step k"`). No push, no PR. Use the Edit tool for each replacement; "old" must match exactly.

### Step 1: backup-gdrive.sh

1a. Old: `# Weekly: snapshot DB on the server, copy the newest encrypted archive to` / `# Google Drive (rclone), and prune Drive copies older than the retention window.`
New:
```
# Daily (04:00 UTC, after backup.sh at 03:00): copy the newest encrypted snapshot,
# already made by backup.sh, to Google Drive (rclone), and prune Drive copies
# older than the retention window. It takes no snapshot of its own.
```
1b. Old (the single line, with the blank lines around it left alone): `./scripts/backup.sh`
New: nothing, delete the line and one of its two neighbouring blank lines so there is a single blank line between the `fi` and `LATEST=`.

1c. Old:
```
if [ -z "${LATEST}" ]; then
  echo "No backup folder in container /data/backups" >&2
  exit 1
fi
```
New:
```
if [ -z "${LATEST}" ]; then
  echo "No backup folder in container /data/backups" >&2
  exit 1
fi

# backup.sh runs at 03:00 UTC. A newest folder from another day means that run
# failed or has not run; do not quietly upload an old snapshot as if it were new.
if [ "${LATEST%%T*}" != "$(date -u +%Y%m%d)" ]; then
  echo "Newest snapshot ${LATEST} is not from today (UTC). Run ./scripts/backup.sh first." >&2
  exit 1
fi
```
Verify: `bash -n deploy/lightsail/scripts/backup-gdrive.sh && shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30; grep -c 'scripts/backup.sh$' deploy/lightsail/scripts/backup-gdrive.sh` (expected: no shellcheck output; count 0; the stderr message line ends `first.` so it does not match). If shellcheck is not installed, run `bash -n` only and say so in the report.

### Step 2: setup-server.sh (lines 75-76)

Old: `  6. Optional — weekly Google Drive off-site copy (Sunday 04:00 UTC), after rclone config:`
New: `  6. Optional — daily Google Drive off-site copy (04:00 UTC, after the 03:00 backup), after rclone config:`

Old: `echo "0 4 * * 0 cd ${INSTALL_DIR}/deploy/lightsail`
New: `echo "0 4 * * * cd ${INSTALL_DIR}/deploy/lightsail`

Verify: `grep -n '0 4 \* \*' deploy/lightsail/scripts/setup-server.sh | tail -5` (one line, `0 4 * * *`); `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`. Leave the `weekly` in the logrotate block (line 87): that is the log rotation, not the backup.

### Step 3: docs/LIGHTSAIL.md

Old: `| `./scripts/backup-gdrive.sh` | Snapshot + rclone copy newest folder to Google Drive |`
New: `| `./scripts/backup-gdrive.sh` | rclone copy of today's snapshot folder (made by `backup.sh`) to Google Drive |`

Old: `Weekly off-site (Sunday 04:00 UTC) after `rclone config` remote **`gdrive`**:`
New: `Daily off-site to Google Drive (04:00 UTC, after the 03:00 local backup) after `rclone config` remote **`gdrive`**. `backup-gdrive.sh` takes no snapshot of its own: it uploads today's folder from `backup.sh` and fails if there is none:`

Old: `echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh`
New: `echo "0 4 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh`

Old: `| `backup-gdrive.sh` | weekly | 30 days | second copy outside AWS |`
New: `| `backup-gdrive.sh` | daily 04:00 UTC | 30 days | second copy outside AWS |`

Verify: `grep -nE 'weekly|Weekly|Sunday|\* \* 0' docs/LIGHTSAIL.md | tail -30` (no line about Drive).

### Step 4: docs/OPERATIONS.md line 642

Old: `the weekly Drive copy and the daily S3 copy`
New: `the daily Drive copy and the daily S3 copy`

Verify: `grep -n 'Drive copy' docs/OPERATIONS.md | tail -5`.

### Step 5: docs/DISASTER_RECOVERY.md

Old: `Re-set WAL-G later, or accept daily and weekly copies.`
New: `Re-set WAL-G later, or accept the daily Drive copy.`

Old: `The data may be up to 7 days old, because the Drive copy is weekly.`
New: `The data may be up to 1 day old, because the Drive copy is daily (04:00 UTC).`

Old: `and the Drive copy on Sunday at 04:00 (`backup-gdrive.sh`)`
New: `and the daily Drive copy at 04:00 (`backup-gdrive.sh`)`

Verify: `grep -nE 'weekly|Sunday|7 days' docs/DISASTER_RECOVERY.md | tail -10` (no Drive line).

### Step 6: deploy/lightsail/README.md

Old: `## Weekly backup to Google Drive (bare minimum)`
New: `## Daily backup to Google Drive (bare minimum)`

Old: `4. Weekly cron (Sundays 04:00 UTC):`
New: `4. Daily cron (04:00 UTC, after the 03:00 `backup.sh`; the Drive job takes no snapshot of its own):`

Old: `echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh`
New: `echo "0 4 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh`

Old: `the weekly Google Drive copy and the daily S3 copy`
New: `the daily Google Drive copy and the daily S3 copy`

Verify: `grep -nE 'Weekly|weekly|Sunday|\* \* 0' deploy/lightsail/README.md | tail -10` (no Drive line). If the section 56-90 mentions a manual run that expects the script to snapshot, change that sentence to say "run ./scripts/backup.sh first", and note it in the report.

### Step 7: docs/plans/portable-disaster-recovery.md

Old: `- Drive copy: weekly, Sunday 04:00 UTC, optional cron, `*.age` only, 30-day retention (`backup-gdrive.sh:53-58`, `setup-server.sh:75`).`
New: `- Drive copy: daily, 04:00 UTC (changed from weekly by brief 1151, 2026-11-12), optional cron, `*.age` only, 30-day retention, no snapshot of its own (`backup-gdrive.sh`, `setup-server.sh:75`).`

Old: `1. Off-AWS data can be 7 days old (Drive is weekly). Whether the Sunday cron is installed in production is unverified.`
New: `1. Off-AWS data is up to 1 day old once brief 1151 is live (Drive is daily). Whether the 04:00 cron is installed in production is unverified until the owner checks `crontab -l`.`

Old: `| 4 | Drive copy daily instead of weekly (cron line change, doc) | S | Haiku brief + owner | 2 |`
New: `| 4 | Drive copy daily instead of weekly (cron line change, doc) (brief 1151) | S | Haiku brief + owner | 2 |`

Verify: `git diff --stat | tail -30`.

## 5. Do not touch

`App/`, `go/`, `backup.sh`, `backup-s3.sh`, `docs/context/` (the orchestrator logs the decision), any secret or `.env`. Hard rules 3 (no secrets) and 8 (never push to `main`) apply.

## 6. Commands

```bash
bash -n deploy/lightsail/scripts/backup-gdrive.sh 2>&1 | tail -30
shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
grep -rnE 'weekly|Sunday' deploy/lightsail/scripts/backup-gdrive.sh docs/LIGHTSAIL.md docs/DISASTER_RECOVERY.md deploy/lightsail/README.md 2>&1 | tail -30
```
Expected: no output from the first two; lint shows no ERROR for this file; the last grep shows no line about Drive (the logrotate `weekly` in setup-server.sh is not in the list). The test-map row is "Deploy scripts": shellcheck above. No pytest needed (no `App/` change).

## 7. Acceptance

- [ ] `backup-gdrive.sh` no longer calls `./scripts/backup.sh` and has the today-check; shellcheck clean.
- [ ] Both cron lines (setup-server.sh, LIGHTSAIL.md, README.md) read `0 4 * * *`.
- [ ] No doc says the Drive copy is weekly, Sunday or 7 days old.
- [ ] Lint has no ERROR for 1151.
- [ ] Seven commits `1151 step 1` to `1151 step 7`.

## 8. Stop and ask

Stop, and write the report, if an old text is not found, shellcheck fails twice, you reach 25 tool calls, a file outside §3 needs a change, or you need push, SSH or secrets.

## 9. Report

Write `docs/tasks/1151-report.md` (600 tokens at most), set `Status: review` in this file, and include the owner steps below verbatim.

### Owner steps (after the PR is merged and deployed; plain words)

1. On the server, look at the current Drive cron line. You should see one line ending in `backup-gdrive.sh`, starting with `0 4 * * 0`:
```bash
crontab -l | grep backup-gdrive
```
2. Swap the Sunday-only schedule for daily, touching only that line. This changes `0 4 * * 0` to `0 4 * * *`:
```bash
crontab -l | sed '/backup-gdrive\.sh/ s/^0 4 \* \* 0 /0 4 * * * /' | crontab -
```
Check it again with the command from step 1: the line must now start with `0 4 * * *`. If step 1 printed nothing, the cron was never installed: add it with the command in `deploy/lightsail/README.md` section "Daily backup to Google Drive", step 4.
3. Take a fresh snapshot, then run the Drive copy once by hand and read the end of the log:
```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh 2>&1 | tail -5
```
```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh 2>&1 | tail -10
```
The last line must read `Uploaded to gdrive:UbyHost-backups/<date>`. If it says the snapshot is not from today, step 3's first command did not finish; read its output.
4. Tomorrow after 04:05 UTC, read the cron log and confirm a new dated folder appeared:
```bash
tail -20 /var/log/ubyhost-gdrive.log
```
```bash
rclone lsd gdrive:UbyHost-backups | tail -5
```
(The log may be in `/home/<deploy user>/ubyhost-gdrive.log` if the server was set up with `setup-server.sh`.)
5. Check how much space Drive uses. The first command shows the account total, the second the backup folder (count of files and total size); expect about 30 folders after a month:
```bash
rclone about gdrive:
```
```bash
rclone size gdrive:UbyHost-backups
```
Archive size is not known to the author. Total size is roughly 30 times one daily folder. If it grows past what you want to keep on Drive, tell the orchestrator: lowering `UBYHOST_BACKUP_RETENTION_DAYS` for this cron line is a one-line change.
