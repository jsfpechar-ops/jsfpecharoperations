# SQLite rollback-path retirement plan (owner + SSH AI)

Written 2026-11-17 from `main` (`336acd2`). Docs only: nothing here was run. Companion: [Python retirement plan](python-retirement-plan.md) (same owner, shared dates). Decisions: [go-sqlite-final §6](go-sqlite-final.md) (answered 2026-11-15), [sqlite-retirement §7](sqlite-retirement.md). Steps S1-S10 of [sqlite-retirement](sqlite-retirement.md) are done (S8, `UBYHOST_SCHEMA_APPLY=go`, since 11-14). This plan runs S11, S12, S13 and the SQLite half of S14, plus the proofs of S10. Briefs: [1473](../tasks/1473-pg-schema-dump-and-proofs.md) (proofs), [1476](../tasks/1476-end-sqlite-rollback-path.md), [1477](../tasks/1477-docs-postgresql-only.md), [1478](../tasks/1478-delete-pg-schema-py.md), [1480](../tasks/1480-sqlite-archive-delete-runbook.md), [1479](../tasks/1479-delete-sqlite-runtime.md).

## 0. Read this first

**What ends:** the way back to SQLite. Production runs on PostgreSQL (WAL-G 7-day point-in-time, nightly age-encrypted dumps to S3 and Drive). What remains of SQLite is a rollback copy, the scripts that use it, and the Python test database.

**Why it is risky:** after S12 the old SQLite file, which holds the same guest data, exists nowhere except the PostgreSQL backups. The decision is therefore tied to proof that those backups restore. No proof, no deletion.

**Dates (decided):** rollback path ends **Tue 2026-12-15**. The four proofs must be recorded by **2026-12-01**; each day of delay moves S11 by one day. The offline copy is deleted **2027-01-14**.

**Privacy:** the SQLite file and old SQLite snapshots contain guest personal data. Deleting them is part of the retention duty, so the schedule below is a firm end date, not a convenience. Keep nothing in notes, mail or chat.

**Coupling with Python retirement:** (1) the Python containers are the only thing that can run on SQLite, so they stay until S11 is merged (12-15). (2) Today `backup.sh`, `backup-s3.sh`, `backup-gdrive.sh`, `pg-restore.sh` and proof B step 4 run inside the `ubyhost` container; the Python plan's stage A (brief 1780) moves them to Go. **Proof B must be run twice if 1780 lands in between**: the proofs of 12-01 count only if the backup chain they tested is the chain that will be live on 12-15. Re-run proofs A and B quickly (30 minutes) after stage A, before S11.

## 1. Who does what

| Who | Does |
|---|---|
| **Josef** | proofs A (on his computer, with the key), the offline copy (d), merge decisions, deletion approval, calendar entries |
| **SSH AI** | proofs B and C on the servers, the S12 deletion, state file `/opt/ubyhost/retirement-state.md` (no secrets, shared with the Python plan) |
| **Orchestrator / Haiku** | exact-diff passes and PRs for 1476, 1477, 1478, 1480, 1479 |

## 2. Timeline

| Date (Prague) | Step | Who | Gate |
|---|---|---|---|
| Tue 11-17 | Q0: read-only check of what is on the server (below) | SSH AI | none |
| by Fri 11-20 | Proof A (decrypt) and (d) offline copy | Josef | none |
| by Wed 11-25 | Proof C (S3 and Drive current; fix IAM and lifecycle if open) | SSH AI | none |
| by Fri 11-27 | Proof B (restore drill into a scratch database on production, counts match) | SSH AI | approved 11-17 |
| **Tue 12-01** | all four proofs recorded in `docs/OPERATIONS.md` with dates (deadline) | orchestrator writes `Done` | P-gate |
| 12-02 to 12-10 | 1476, 1477, 1478 exact-diff passes; PRs open as drafts | orchestrator, Haiku | none |
| 12-08 to 12-11 | Re-run proofs A and B after the Python plan's stage A (if 1780 deployed) | Josef, SSH AI | P-gate again |
| **Tue 12-15** | S11: merge 1476; deploy; scripts gone | Josef, SSH AI | G-S11 |
| Wed 12-16 | S13: merge 1477 (docs) | Josef | none |
| 12-16 to 12-23 | S9 (1478) merge when two goose migrations are applied by Go | Josef | G-S9 |
| Fri 2027-01-08 | Josef confirms deletion list (2 days' notice) | Josef | none |
| **Thu 2027-01-14** | S12: delete the SQLite file and old SQLite snapshots on server, S3, Drive; delete the offline copy | SSH AI and Josef | G-S12 |
| on or after Mon 2027-01-18 | SQLite half of S14: 1479 (`App/` goes, see Python plan stage 5) | Josef | Python plan G9 |

## 3. Gates

| Gate | Passes when |
|---|---|
| P-gate | all four proofs below say `Done` with a date within the last 30 days, **tested on the backup chain that is live now** |
| G-S11 | P-gate; 1476 CI green; Josef has said "end rollback" in the thread on or after 12-15; a fresh `backup.sh` and its S3 and Drive copies ran ok the night before; `pg_dump` restore (proof B) done on the newest snapshot, not a week-old one |
| G-S9 | S8 is live (yes), two goose migrations applied by Go on production (SSH AI lists `goose_db_version`) |
| G-S12 | 30 days since S11 deploy, no PostgreSQL incident in that time, a fresh proof B passed within the last 7 days, Josef approves the file list |

## 4. The four proofs (S10)

Full click-by-click for Josef is in `docs/OPERATIONS.md`, "Proofs before the SQLite rollback path ends" (A, B, C). Status in the repo today: all four "not yet". **Q0 first**, because notes from 11-16 say nightly S3 and Drive backups were fine and the doc may be behind:

```
You are the server operator for UbyHost. READ ONLY.
cd /opt/ubyhost/deploy/lightsail
1. tail -n 3 /var/log/ubyhost-s3.log /var/log/ubyhost-gdrive.log
2. rclone lsf gdrive:UbyHost-backups | tail -n 7 ; (S3 bucket name from crontab, never print keys) rclone lsf s3:<bucket>/UbyHost-backups | tail -n 7
3. docker compose exec -T ubyhost sh -c 'ls -1 /data/backups | sort | tail -3'   (Python chain today)
4. ls -l the SQLite file(s): docker compose exec -T ubyhost sh -c 'ls -l /data/ubyhost.db* /data/pg-cutover 2>&1; ls /data | head -30'
6. WAL-G: ./scripts/walg-check.sh 2>&1 | tail -5
7. df -h / | tail -1
Report in 20 lines. Write /opt/ubyhost/sqlite-q0-2026-11-17.md.
```

| Proof | Meaning | Who | Pass line | If it fails |
|---|---|---|---|---|
| (a) | One `.age` dump and the tar decrypt with Josef's key on his own computer (never on a server) | Josef | `wc -c` above 10000, file names listed, no `age:` error | the key is wrong or lost: **stop everything**; S11 and S12 never happen until a key that decrypts is stored in two places |
| (b) | Fresh dump restores into scratch database, row counts equal production | SSH AI via `pg-restore.sh` / OPERATIONS B | `exit: 0 0`, `COUNTS MATCH`, `CLEAN` | bring the diff lines (table names and numbers only) to the orchestrator; no S11 |
| (c) | Drive and S3 copies current, daily | SSH AI | newest folder today or yesterday on both; no 403 line in `/var/log/ubyhost-s3.log` | the known cause is the IAM policy lacking `s3:GetObjectVersion` (Josef adds it in the AWS console; no delete rights); S3 lifecycle rule and the `_probe/` objects are also Josef's console steps |
| (d) | One age-encrypted offline copy of the last SQLite file and `secret_key`, on media not synced to any cloud | Josef | label with date; listing with `age --decrypt ... \| tar -t` shows `ubyhost.db` | redo from a fresh `backup-tar.age` snapshot while it still contains the file |

**No staging server (confirmed by Josef 2026-11-17).** Proof B uses a scratch database on production only (approved): `createdb ubyhost_restoretest` on the production Postgres container, restore, compare counts, drop. It reads backups and writes only to the scratch database, which the app never uses. The scratch database holds guest data for a few minutes and is dropped by the `CLEAN` step.

**One sentence to Josef for each proof when done:** write the letter, date and the last lines in the thread; the orchestrator writes `Done` in OPERATIONS.

## 5. Steps

### S11. End the rollback path (Tue 12-15)

Preconditions: G-S11. Python plan stage 3 must not have deleted `ubyhost` before this PR merges.

1. Orchestrator/Haiku: [1476](../tasks/1476-end-sqlite-rollback-path.md) exact-diff pass: delete `pg-cutover.sh`; `restore.sh` becomes a thin pointer to `pg-restore.sh`; `deploy.sh` loses the SQLite backup and `integrity_check` branch (merge carefully with the Python plan's 1780 and 1782b changes to the same file: run 1480/1476 **after** 1780, and tell them to share one base); `setup-server.sh` and `preflight.sh` and `deploy-preflight.yml` lose `sqlite3`; README says PostgreSQL only.
2. Josef: merge on 12-15 (draft to ready, merge script) after the 1-line go in the thread.
3. SSH AI paste (after the normal deploy):

```
cd /opt/ubyhost/deploy/lightsail
Watch the whole deploy end to end. Read the state file; stop if "S11 kept" is there.
ls scripts | grep -E 'pg-cutover|restore.sh'      # pg-cutover.sh gone
grep -c sqlite3 scripts/*.sh                       # all 0
docker compose ps                                  # everything healthy
./scripts/backup.sh 2>&1 | tail -3                 # still ok
Write "S11 kept <date>" to /opt/ubyhost/retirement-state.md
NOTE: the SQLite file in /data and the archived copy are NOT touched here.
```
Rollback: revert the PR, redeploy; the SQLite file is still in `/data` and the offline copy exists. Valid until S12.

### S13. Docs say PostgreSQL only (12-16)
[1477](../tasks/1477-docs-postgresql-only.md): `ENVIRONMENT` (`UBYHOST_DB`), `LIGHTSAIL`, `OPERATIONS` backup section (also the proof section becomes history), `SECURITY`, `rules`. Docs only; revert if wrong. No server step.

### S9. Delete `pg_schema.py` and Python's schema apply (after 12-16)
[1478](../tasks/1478-delete-pg-schema-py.md). Precondition G-S9. SSH AI check before merge: `docker compose --profile go run --rm --no-deps -T ubyhost-go migrate check --expect-database ubyhost` prints `PostgreSQL schema check OK`, and the goose table lists at least two rows applied by Go since 11-14. Rollback: revert PR; `UBYHOST_SCHEMA_APPLY=python` is no longer valid after merge, so S8 rollback ends here too (accepted by the decisions).

### S12. Archive and delete the SQLite file (Thu 2027-01-14)

Precondition G-S12. Brief [1480](../tasks/1480-sqlite-archive-delete-runbook.md) writes the click-by-click into `docs/OPERATIONS.md` (docs only, merged by 12-20). On the date, Josef gives the go in the thread; SSH AI pastes:

```
cd /opt/ubyhost/deploy/lightsail
Read the state file: "S11 kept" must be there, and a proof B within 7 days (run OPERATIONS B first if not).
LIST FIRST, delete nothing: 
  the SQLite file(s) in the data volume (names, sizes), any pg-cutover folder, old snapshot folders that contain ubyhost.db in /data/backups (ls only),
  Drive and S3 folders older than the S11 date that contain a tar.age with ubyhost.db (names only).
Print the list and STOP. Josef replies "delete list OK" with the list he saw.
Only after that: delete exactly those names. No wildcards beyond the printed list. No docker volume rm, no prune.
Afterwards: run backup.sh once; verify the newest snapshot still has the dump and the secret_key.
Write "S12 kept <date>" to the state file.
```
Josef then: deletes the offline copy (shred or physical destruction), removes the calendar reminder. Rollback: **none after the offline copy is gone, by decision.** Until then, the offline copy restores the SQLite file on a scratch machine (not production).

### S14 (SQLite half). Delete the SQLite runtime together with `App/`
Same PR as Python stage 5 ([1479](../tasks/1479-delete-sqlite-runtime.md)): `db.py`, `db_postgres.py` translation, `App/app/migrations/`, `sqlite_to_postgres.py`, encrypt scripts, `sqlite_only` tests, CI shards on SQLite, `docs`. The Python test DB dies with Python. Date and rollback: see the Python plan.

## 6. Risks

| Risk | Prevented by |
|---|---|
| Backups cannot be decrypted (key lost or wrong) | proof A before anything; key in the password manager and the offline copy |
| Backups restore but are old or partial | proof B uses a snapshot taken minutes before; counts compared to production |
| Backup chain changes mid-plan (Python plan, 1780) | re-run A and B after that change (section 0) |
| S3 copy silently failing (403 on read-back, no prune) | proof C; IAM `s3:GetObjectVersion`; lifecycle rule by Josef |
| Deleting too much | list-first step in S12, no wildcards, `STOP` for Josef's reply |
| Retention duty missed | firm end date 2027-01-14 |
| `deploy.sh` edited by three PRs | one base: 1780 first, then 1476, then 1782b |

## 7. Decisions (answered by Josef, 2026-11-17)

1. **Offline copy:** deleted on **2027-01-14 together with the server file** (S12). Nothing else keeps SQLite after that day; the PostgreSQL backups are the only copy.
2. **No staging server exists.** Proof B runs into a scratch database on production, approved by Josef. Rules: it only reads the backup file and the live database is never written (no `pg_restore` target but `ubyhost_restoretest`, `--exit-on-error`, `--single-transaction`; counts are read with the read-only `pg-schema-dump.sh --counts`); the scratch database is dropped in the same session (`CLEAN` line) and the decrypted dump never touches disk unencrypted. Run it outside 03:00-07:30 Prague.
3. **Unported routes:** decided later (Python plan, gate G5).
