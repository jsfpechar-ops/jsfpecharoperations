# 1151 report: Google Drive copy daily

Status: review

## Files changed
- deploy/lightsail/scripts/backup-gdrive.sh (steps 1, earlier session)
- deploy/lightsail/scripts/setup-server.sh (step 2)
- docs/LIGHTSAIL.md (step 3)
- docs/OPERATIONS.md (step 4)
- docs/DISASTER_RECOVERY.md (step 5)
- deploy/lightsail/README.md (step 6)
- docs/plans/portable-disaster-recovery.md (step 7)
- docs/tasks/1151-report.md (this file)

Commits: `1151 step 1` (753ceaed) to `1151 step 7` (03f8c902).

## Commands (last 5 lines)
- `bash -n deploy/lightsail/scripts/backup-gdrive.sh deploy/lightsail/scripts/setup-server.sh`: no output, exit 0.
- `shellcheck -S error ...`: not run, shellcheck is not installed in this environment.
- `grep -rnE 'weekly|Sunday' deploy/lightsail/scripts/backup-gdrive.sh docs/LIGHTSAIL.md docs/DISASTER_RECOVERY.md deploy/lightsail/README.md`: no output.
- `python3 scripts/context_lint.py 2>&1 | tail -5`: 2 WARN (test names in open briefs, not related to 1151), 1 WARN (2 commits touched App/ after last status.md update), `next free: task 1135 | migration 0046`, `context lint: OK`.

## Section 7 (acceptance)
- [x] backup-gdrive.sh no longer runs ./scripts/backup.sh (it only mentions it in the error text) and has the today-check. Shellcheck NOT run (not installed), so "shellcheck clean" is unverified.
- [x] Cron lines in setup-server.sh, LIGHTSAIL.md and README.md read `0 4 * * *`.
- [x] No doc says the Drive copy is weekly, Sunday or 7 days old (grep empty).
- [x] Lint has no ERROR for 1151.
- [x] Seven commits `1151 step 1` to `1151 step 7`.

## Deviations
- Step 6 README: also changed "once a week" to "once a day" and added `./scripts/backup.sh` before the manual test (owner-accepted by orchestrator).
- Step 7: the brief's "Old" text for the Drive line is a prefix of a longer line; the trailing " S3 copy: daily, `backup-s3.sh`." was kept.
- shellcheck not installed; only `bash -n` ran.
- Session 1 hit the tool cap after step 5; this continuation did steps 6 and 7 and the report.

## Questions
- None.

## Owner steps (after the PR is merged and deployed)
1. On the server, look at the current Drive cron line. You should see one line ending in `backup-gdrive.sh`, starting with `0 4 * * 0`:
```bash
crontab -l | grep backup-gdrive
```
2. Swap the Sunday-only schedule for daily, touching only that line:
```bash
crontab -l | sed '/backup-gdrive\.sh/ s/^0 4 \* \* 0 /0 4 * * * /' | crontab -
```
Check it again with the command from step 1: the line must now start with `0 4 * * *`. If step 1 printed nothing, add the cron with the command in `deploy/lightsail/README.md` section "Daily backup to Google Drive", step 4.
3. Take a fresh snapshot, then run the Drive copy once by hand:
```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh 2>&1 | tail -5
```
```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh 2>&1 | tail -10
```
The last line must read `Uploaded to gdrive:UbyHost-backups/<date>`.
4. Tomorrow after 04:05 UTC, read the cron log and confirm a new dated folder appeared:
```bash
tail -20 /var/log/ubyhost-gdrive.log
```
```bash
rclone lsd gdrive:UbyHost-backups | tail -5
```
5. Check Drive usage:
```bash
rclone about gdrive:
```
```bash
rclone size gdrive:UbyHost-backups
```
If it grows past what you want to keep, tell the orchestrator: lowering `UBYHOST_BACKUP_RETENTION_DAYS` for this cron line is a one-line change.
