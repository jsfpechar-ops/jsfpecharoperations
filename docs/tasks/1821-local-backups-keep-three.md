# 1821: Local backups: keep the newest 3, backup on deploy only with a pending migration

Status: todo
Depends on: none | Base commit: current tip of the working branch | Branch: task/1821-local-backups-keep-three
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (backups and deploy gate; rule 1 and restore safety). Brief writer Opus or exact diff only; fresh reviewer reads the full diff.

## 1. Objective

The `ubyhost-data` volume holds only the newest 3 backup folders (today 1.34 GB in about 75 folders of 17 MB), and a deploy takes a backup only when a database migration is pending.

## 2. Context

Measured 2026-11-15 ([optimization-wins](../plans/optimization-wins.md) sections 1 and 7, lane E, brief 1821). Facts found in the files:

- **Where the folders are made and pruned:** `App/scripts/backup_data.sh` (shell). `deploy/lightsail/scripts/backup.sh` calls it (`docker compose exec -T ubyhost bash /app/scripts/backup_data.sh`) and then adds the age-encrypted PostgreSQL dump into the newest folder. `deploy.sh` and the nightly job both call `backup.sh`, so every run makes one folder.
- **Why there are 75 folders:** pruning is by time, not count. Production sets `UBYHOST_BACKUP_RETENTION_DAYS=7`, and each deploy adds a folder. Current code, `App/scripts/backup_data.sh` lines 108-127:

```
# Retention is by time, not by count: a snapshot older than the window is
# removed, but the newest one is always kept even if it is older than the
# window (so a host that stopped backing up does not lose their last copy).
newest="$(find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort | tail -n 1)"
cutoff="$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%dT%H%M%SZ 2>/dev/null || date -u -v-"${RETENTION_DAYS}"d +%Y%m%dT%H%M%SZ)"
for dir in "${BACKUP_ROOT}"/*/; do
  ...
  if [ "${stamp}" \< "${cutoff}" ]; then
    rm -rf "${dir}"
  fi
done
echo "Kept snapshots from the last ${RETENTION_DAYS} days under ${BACKUP_ROOT} (newest kept)"
```

  (Read the full range 105-130 before editing.) Folder names are `YYYYMMDDTHHMMSSZ` with an optional `-N` suffix (lines 19-25).
- **Deploy backup gate:** `deploy/lightsail/scripts/deploy.sh` lines 166-213. Line 166 `BACKUP_STAMP=""`; line 168 `if docker compose ps --status running --services 2>/dev/null | grep -qx ubyhost; then`; lines 170-171 `echo "==> Mandatory pre-deploy backup"` and `./scripts/backup.sh`; the stamp is read at 172-173; the block checks the age file (PG_MODE branch, lines 183-191), records `BEFORE_COUNTS` (lines 206-209) and ends with `echo "Backup ${BACKUP_STAMP} is valid; live row counts recorded."` (line 212). Later `if [ -n "${BACKUP_STAMP}" ]` at lines 290 (SQLite dry-run) and 431 (post-deploy checks) depend on the stamp.
- **Pending migrations:** the schema apply happens later, at deploy.sh line ~260 (`SCHEMA_APPLY` go or python). Goose files live in `App/migrations_pg/`. The deploy writes `.deployed-sha` at the end (line ~467: `git rev-parse HEAD > .deployed-sha`), so the previous deployed commit is known before the build.
- **Off-box upload is not tracked.** `backup-s3.sh` and `backup-gdrive.sh` run `./scripts/backup.sh`, then upload only the newest folder (`LATEST=... sort -r | head -1`, then `docker cp` and `rclone copy`). Neither writes an "uploaded" marker, and nothing deletes local folders. Folders made by deploys are never uploaded. So there is no flag to honour: the nightly folder is uploaded right after it is made, before any later prune.
- **Restore:** `deploy/lightsail/scripts/restore.sh` takes a stamp, or lists `ls -1 /data/backups | sort -r`, and reads `ubyhost-backup.tar.age` (or the legacy `ubyhost.db`). It needs no change as long as the folder layout and names stay.
- **Go-first (rule 11):** `go/cmd/ubyhost-web` has no backup subcommand, and brief 1780 states "`backup_data.sh` stays shell". The change therefore belongs in shell (`backup_data.sh`, `deploy.sh`), not Go. Do not add Go code.
- Hard rules: 1 filing correctness (the pre-deploy backup is the safety net for a migration, so it must still happen whenever a migration is pending); 3 no secrets or hostnames in the repo; 4 no new dependency.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/backup_data.sh` | edit | keep the newest N folders (default 3) instead of the time window |
| `deploy/lightsail/scripts/deploy.sh` | edit | take the pre-deploy backup only when a migration is pending |
| `App/tests/test_backup_data.py` | edit | adapt only the retention test(s) that the new rule breaks; add one test for "keeps 3" |
| `docs/OPERATIONS.md` | edit | the "Retention is by time, not count" bullet (line ~622) |
| `docs/tasks/1821-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root; anything else than the stated result: STOP).
   - `grep -nF 'RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"' App/scripts/backup_data.sh` prints line 29.
   - `grep -nF 'if [ "${stamp}" \< "${cutoff}" ]; then' App/scripts/backup_data.sh` prints one line.
   - `grep -nF 'echo "==> Mandatory pre-deploy backup"' deploy/lightsail/scripts/deploy.sh` prints one line.
   - `grep -nF 'git rev-parse HEAD > .deployed-sha' deploy/lightsail/scripts/deploy.sh` prints one line.
1. `backup_data.sh`: add `KEEP="${UBYHOST_BACKUP_KEEP:-3}"` next to line 29 and document it in the header comment (line ~11, same style as `UBYHOST_BACKUP_RETENTION_DAYS`). Replace the pruning loop (the `newest=`, `cutoff=` and `for dir` block and its echo) with a count rule: list the folders whose name matches `[0-9]{8}T[0-9]{6}Z(-[0-9]+)?`, sort ascending, and `rm -rf` every folder except the last `KEEP`. Never touch folders whose names do not match the pattern. Never remove the folder just written (`${DEST}`); it is always the newest because names sort by time. If `KEEP` is not a positive integer, use 3. Update the echo to `Kept the newest ${KEEP} snapshots under ${BACKUP_ROOT}`. Keep `RETENTION_DAYS` (it is still printed in the marker JSON at line ~135 and `test_wp32_container_sizing.py` expects the variable name in `.env.example` and the docs).
2. `deploy.sh`: before line 166 compute `MIGRATION_PENDING`: `1` when the committed goose files changed since the last deployed commit, else `0`. Exact rule: read `PREV_DEPLOYED="$(cat .deployed-sha 2>/dev/null || true)"`; if it is empty or `git cat-file -e "${PREV_DEPLOYED}^{commit}"` fails, set `MIGRATION_PENDING=1` (fail safe: take the backup); else `MIGRATION_PENDING=1` if `git diff --name-only "${PREV_DEPLOYED}" HEAD -- App/migrations_pg | grep -q .`, else `0`. Also honour `UBYHOST_FORCE_BACKUP=1` (set `MIGRATION_PENDING=1`). Change line 168 so the whole backup block runs only when `MIGRATION_PENDING` is `1` AND ubyhost is running (`if [ "${MIGRATION_PENDING}" = "1" ] && docker compose ps ... | grep -qx ubyhost; then`); add an `else` that echoes `==> No migration pending: pre-deploy backup skipped (the nightly backup covers the data).` (see open question 1 for what the checks at lines 290 and 431 then do: they already test `-n "${BACKUP_STAMP}"` and stay silent when it is empty).
3. `test_backup_data.py`: run the file, change only the assertion(s) that fail because of the new rule, and add one test that runs the script 5 times against a temp dir and asserts exactly 3 folders remain and the newest is among them.
4. `OPERATIONS.md`: replace the bullet "Retention is by time, not count." (line ~622) with two or three sentences: local keeps the newest `UBYHOST_BACKUP_KEEP` (default 3) folders; deploy backs up only when a migration is pending (or `UBYHOST_FORCE_BACKUP=1`); off-site copies stay 30 days. One sentence per fact, no tracking-cookie style copy needed.
5. Commands in §6; write the report.

## 5. Do not touch

`restore.sh`, `backup.sh`, `backup-s3.sh`, `backup-gdrive.sh`, anything under `go/`, `App/migrations_pg/`, filing code, `.env`, any server file. Do not change `UBYHOST_BACKUP_RETENTION_DAYS` semantics for the off-site scripts. Do not remove the integrity or age-file checks inside the backup block. No hostnames or IPs.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh App/scripts/*.sh 2>&1 | tail -30` is silent (test-map row: "Deploy scripts, Caddyfile, compose").
- `cd App && .venv/bin/python -m pytest tests/test_backup_data.py tests/test_pg_backup_scripts.py tests/test_wp32_container_sizing.py -q --tb=short -x 2>&1 | tail -30` passes.
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean.

## 7. Acceptance

- [ ] After 5 runs of `backup_data.sh` in a temp dir, exactly 3 folders remain (test).
- [ ] `restore.sh` is unchanged in `git diff --stat`.
- [ ] `deploy.sh` runs the backup block only when `MIGRATION_PENDING=1`; a missing or unknown `.deployed-sha` means `1`.
- [ ] `git diff --stat` lists only §3 paths; one commit per step (`1821 step k`).

Owner check after the merge (hand over in the report): after the next deploy, `docker compose exec ubyhost ls -1 /data/backups` lists 3 folders or fewer, and `./scripts/restore.sh` with no stamp lists the newest one (stop at the prompt, do not restore).

## 8. Stop and ask

Stop and write the report if: an anchor is not found; a test fails twice; 25 tool calls or about 50k tokens; a file outside §3 needs a change; the pending-migration rule in step 2 seems wrong for this deploy.sh; you need push, merge, SSH or deploy.

## 9. Report

`docs/tasks/1821-report.md`, 600 tokens at most: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Then set `Status: review` and open one PR.

## Risk list (for the reviewer)

`App/scripts/backup_data.sh` (deletes data), `deploy/lightsail/scripts/deploy.sh` (deploy gate).

## Open questions for the orchestrator

1. **Skipped backup and the row-count checks.** When the backup is skipped, `BACKUP_STAMP` is empty, so the post-deploy integrity and row-count comparison (deploy.sh ~431) does not run. Accept this, or should the row counts still be recorded without a backup? Needs an owner or orchestrator decision before executing.
2. **Pending-migration test.** The brief uses `git diff` of `App/migrations_pg` against `.deployed-sha`. Is a different rule wanted (for example asking the new Go image `migrate plan`, but that image is built after the backup point)? Default in this brief: git diff.
3. **Off-box tracking.** None exists (see §2). Confirm that deleting deploy-made folders beyond the newest 3 is acceptable, since only the nightly folder is uploaded. If an "uploaded" marker is wanted, that is a separate brief touching `backup-s3.sh` and `backup-gdrive.sh`.
4. **Default of `UBYHOST_BACKUP_KEEP`.** The plan says 3 copies; the code default is 3 here. Confirm that production `.env` needs no change (it sets `UBYHOST_BACKUP_RETENTION_DAYS=7`, which now only affects the marker).
