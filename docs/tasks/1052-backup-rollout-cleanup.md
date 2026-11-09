# 1052: Backup rollout corrections (WAL-G runbook, backup-s3 flag, Litestream leftovers)

Status: todo
Depends on: none | Base commit: 9d2bad19 | Branch: claude/eloquent-mendel-vd8mfi
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Correct the WAL-G owner runbook and the backup scripts with what broke in the real production rollout on 2026-11-08/09, and remove the factual Litestream leftovers from the operational docs. The runbook was written without being run; the next restore drill must not hit the same errors.

## 2. Context

Rules: AGENTS.md hard rules 3 and 9 (no real bucket names or secrets in the repo; short sentences, one explanation in one place). Litestream was retired on 2026-11-07. Backups now: age-encrypted `pg_dump` (daily and pre-deploy), weekly Drive copy, daily S3 copy, plus WAL-G point-in-time recovery.

Use the Edit tool, one edit per step. Every `old_string` below is a verbatim excerpt. If one is not found, STOP (§8). Line numbers are hints only.

Real findings: Docker Compose runs as the `ubuntu` user, so a root-owned `.env.walg` fails with `open .env.walg: permission denied`. A bucket name alone in `WALG_S3_PREFIX` fails with `missing url scheme`. `WALG_UPLOAD_CONCURRENCY=2` logs `Error of parallel upload: open /walspool/archive_status: no such file or directory` on every push. Cron silently skips a command when the redirect log file cannot be opened. WAL-G refuses `Directory /restore for delta base must be empty`. The rclone upload gets a 403 on the first attempt and succeeds on the second.

Test note: the `backup-s3.sh` tests live in `App/tests/test_backup_offsite.py` (fake `rclone` writes its arguments to `FAKE_RCLONE_LOG`), not in `test_pg_backup_scripts.py`. The fake is:

```
printf '%s\\n' "$*" >> "${FAKE_RCLONE_LOG}"
```

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/OPERATIONS.md | edit | WAL-G rollout steps 4, 9, 11, 16, drill 2, harmless-log note, key custody; Litestream line fix |
| docs/LIGHTSAIL.md | edit | create the two cron log files first |
| deploy/lightsail/scripts/backup-s3.sh | edit | `--s3-no-check-bucket`; header comment |
| App/tests/test_backup_offsite.py | edit | one test for the flag |
| docs/architecture.md | edit | Litestream diagram nodes, source note, table row |
| docs/UBYPORT_CORE.md | edit | two Litestream mentions |

No other file may change. `WALG_UPLOAD_CONCURRENCY` exists only once in the repo (docs/OPERATIONS.md); step 3 re-checks.

## 4. Steps

Part A: docs/OPERATIONS.md (all edits in this one file).

1. Step 9 command. Edit `old_string`: `sudo install -m 600 -o root -g root /dev/null .env.walg && sudo nano .env.walg`. `new_string`: `sudo touch .env.walg && sudo chown ubuntu:ubuntu .env.walg && sudo chmod 600 .env.walg && sudo nano .env.walg`. Expected: Edit succeeds.
2. Step 9 check paragraph. `old_string`: `` `.env.*` is git-ignored. Check: `ls -l .env.walg` shows `-rw------- 1 root root`. ``. `new_string`: `` `.env.*` is git-ignored. The owner must be `ubuntu`: Docker Compose runs as that user and fails with `open .env.walg: permission denied` on a root-owned file. Check: `ls -l .env.walg` shows `-rw------- 1 ubuntu ubuntu`. `WALG_S3_PREFIX` is the full URL `s3://BUCKET/postgres-wal` with your real bucket name; the bucket name alone fails with `missing url scheme`. ``. Expected: Edit succeeds.
3. Concurrency. `old_string`: `WALG_UPLOAD_CONCURRENCY=2`. `new_string`: `WALG_UPLOAD_CONCURRENCY=1`. Then run `grep -rn "WALG_UPLOAD_CONCURRENCY" /home/user/jsfpecharoperations/deploy /home/user/jsfpecharoperations/docs/ENVIRONMENT.md /home/user/jsfpecharoperations/docs/OPERATIONS.md | tail -10`. Expected: only the one OPERATIONS.md line, value `1`. If another line shows `=2`, change it to `1` too and add that file to the report (deviation).
4. IAM step warning (step 4 of the runbook). `old_string`: `(replace both `BUCKET` with your bucket name)`. `new_string`: `(replace every `BUCKET` in the JSON, three places, with your bucket name; a missed one makes AWS answer AccessDenied on ListBucket)`. Expected: Edit succeeds.
5. Step 11 profiles. `old_string`: `If a `COMPOSE_PROFILES=` line exists, add `,walg` to its end (for example `COMPOSE_PROFILES=monitoring,walg`); if not, add `COMPOSE_PROFILES=walg`.` `new_string`: `If a `COMPOSE_PROFILES=` line exists, replace the word `litestream` with `walg` and keep every other profile (for example `litestream,monitoring,go` becomes `monitoring,go,walg`; dropping `go` would switch off a service); if there is no such line, add `COMPOSE_PROFILES=walg`.` Expected: Edit succeeds.
6. Step 16 cron logs. `old_string`: `16. Add the two cron lines from [LIGHTSAIL](LIGHTSAIL.md) (WAL-G point-in-time recovery), then`. `new_string`: `16. First create the two log files, or cron silently skips the commands because it cannot open the redirect file: `sudo touch /var/log/ubyhost-walg-backup.log /var/log/ubyhost-walg-check.log && sudo chown ubuntu:ubuntu /var/log/ubyhost-walg-backup.log /var/log/ubyhost-walg-check.log`. Then add the two cron lines from [LIGHTSAIL](LIGHTSAIL.md) (WAL-G point-in-time recovery), then`. Expected: Edit succeeds.
7. Drill 2 clean start. The text `docker volume create walg-drill` appears once in the drill 2 code block. Use this two-line anchor: `old_string`: `docker volume create walg-drill\ndocker run --rm --user root --env-file .env.walg -v walg-drill:/restore ubyhost-walg:local wal-g backup-fetch /restore LATEST` (a real newline between the lines). `new_string`: `docker rm -f walg-drill-pg 2>/dev/null; docker volume rm walg-drill 2>/dev/null\ndocker volume create walg-drill\ndocker run --rm --user root --env-file .env.walg -v walg-drill:/restore ubyhost-walg:local wal-g backup-fetch /restore LATEST`. If the Edit says the anchor is not unique, run `grep -n "docker volume create walg-drill" /home/user/jsfpecharoperations/docs/OPERATIONS.md | tail -5` and report; STOP. Expected: Edit succeeds. Reason (do not paste): WAL-G refuses `Directory /restore for delta base must be empty`.
8. Known-harmless note. In the Alarms bullet, `old_string`: `**Never delete files from `pg_wal` by hand.**` (first occurrence only: if the Edit reports several matches, add the preceding words `raise `WALG_MAX_ARCHIVE_AGE_S` in `.env` if it repeats. ` to make it unique). `new_string`: the same text followed by a new line `- **Known harmless log line.** The `walg` container logs `mkdir /var/lib/postgresql/data/pg_wal/walg_data: read-only file system` on each push although the WAL file uploads. Verify in S3: `docker compose exec -T walg wal-g st ls wal_005/`. `walg-check.sh` is the real health signal.` Expected: Edit succeeds.
9. Server-side owner of `.env.walg`. `old_string`: `(mode 600, root)`. `new_string`: `(mode 600, owner ubuntu)`. Expected: Edit succeeds.
10. Key custody (Backup and restore section). `old_string`: `can read every backup; if it is lost, every encrypted backup is unreadable.` `new_string`: `can read every backup; if it is lost, every encrypted backup is unreadable. The private identity (`AGE-SECRET-KEY-1...`) lives in the owner's password manager plus one offline copy, never in `.env` and never on the server; the restore drill proves it works.` Expected: Edit succeeds.
11. Command: `cd /home/user/jsfpecharoperations && git diff --stat | tail -5 && python3 scripts/context_lint.py 2>&1 | tail -5`. Expected: OPERATIONS.md changed; lint passes.

Part A, LIGHTSAIL.

12. docs/LIGHTSAIL.md. `old_string`: `WAL-G point-in-time recovery (production only, after the rollout in [OPERATIONS](OPERATIONS.md#wal-g-continuous-archiving-and-point-in-time-recovery)): daily base backup 04:30 UTC and a check every 10 minutes:`. `new_string`: the same text, with `Create the log files first, or cron silently skips both commands: `sudo touch /var/log/ubyhost-walg-backup.log /var/log/ubyhost-walg-check.log && sudo chown ubuntu:ubuntu /var/log/ubyhost-walg-backup.log /var/log/ubyhost-walg-check.log`.` added after the colon-ended sentence is turned into a full stop (the sentence now ends `10 minutes.` followed by the new sentence, then a blank line before the code block stays). Expected: Edit succeeds; the code block with `walg-check.sh` is unchanged.

Part B: backup-s3.sh and its test.

13. Upload flag. In deploy/lightsail/scripts/backup-s3.sh, `old_string`: `rclone copy "${TMP}/${LATEST}" "${DEST}" --include "*.age" --stats-one-line`. `new_string`: `rclone copy "${TMP}/${LATEST}" "${DEST}" --include "*.age" --stats-one-line --s3-no-check-bucket`. Expected: Edit succeeds. Reason (comment, optional one line above): the upload-only IAM user may not check or create the bucket; without the flag the first attempt got 403.
14. Header comment. `old_string`: `# lifecycle rule expiring objects after UBYHOST_BACKUP_RETENTION_DAYS, and an` `new_string`: `# lifecycle rule expiring objects after a fixed 30 days (prefix UbyHost-backups/, see docs/OPERATIONS.md Backup and restore), and an`. Expected: Edit succeeds.
15. Test. In App/tests/test_backup_offsite.py append after `test_s3_upload_copies_only_age_archives` (use `old_string` = the line `    assert "--include *.age" in log` and `new_string` = that line plus the new test below; if that line occurs twice, STOP):

```
    assert "--include *.age" in log


def test_s3_upload_skips_the_bucket_check(tmp_path: Path):
    result = _run(tmp_path, has_age=True)
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "rclone.log").read_text(encoding="utf-8")
    assert "--s3-no-check-bucket" in log
```

Expected: Edit succeeds.
16. Run: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_backup_offsite.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. Then `cd /home/user/jsfpecharoperations && shellcheck -S error deploy/lightsail/scripts/backup-s3.sh 2>&1 | tail -10`. Expected: no output (if shellcheck is missing, say so in the report).

Part C: Litestream leftovers (skip this part and report `blocked` if you are at 24 tool calls).

17. docs/architecture.md diagram. `old_string`: `  Litestream[litestream<br/>replicate] -->|reads WAL| DB\n  Litestream -->|S3| S3[(S3 bucket)]` (real newline). `new_string`: `  WalG[walg<br/>ship WAL files] -->|S3| S3[(S3 bucket)]`. Expected: Edit succeeds.
18. docs/architecture.md source note. `old_string`: `` `litestream` ~line 108; `` `new_string`: `` `walg` (profile `walg`); ``. Expected: Edit succeeds.
19. docs/architecture.md table row. `old_string`: `| litestream | `replicate -config /etc/litestream.yml` | — | n/a | `deploy/lightsail/docker-compose.yml` |`. `new_string`: `| walg (profile `walg`) | uploads archived WAL files to S3 (WAL-G) | — | n/a | `deploy/lightsail/docker-compose.yml` |`. Expected: Edit succeeds.
20. docs/UBYPORT_CORE.md. `old_string`: `(e.g. **Litestream off**, shorter backup retention)`. `new_string`: `(e.g. **WAL-G archiving off**, shorter backup retention)`. Expected: Edit succeeds.
21. docs/UBYPORT_CORE.md. `old_string`: `Backups and Litestream protect the database; they do **not** replace correct`. `new_string`: `Backups and WAL-G protect the database; they do **not** replace correct`. Expected: Edit succeeds.
22. Verify and commit. Run `cd /home/user/jsfpecharoperations && grep -n -i litestream docs/architecture.md docs/UBYPORT_CORE.md deploy/lightsail/README.md docs/LIGHTSAIL.md docs/OPERATIONS.md | cut -c1-120 | tail -10 && python3 scripts/context_lint.py 2>&1 | tail -5`. Expected: only the three correct "retired" notes (README.md 159 and 161, LIGHTSAIL.md 264, OPERATIONS.md 560) remain; lint passes. Then `git add docs/OPERATIONS.md docs/LIGHTSAIL.md docs/architecture.md docs/UBYPORT_CORE.md deploy/lightsail/scripts/backup-s3.sh App/tests/test_backup_offsite.py && git commit -m "docs+scripts: backup rollout corrections (brief 1052)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01Cjmb7MXpjDkcxapc9nNiJR" 2>&1 | tail -5`, then `git push -u origin claude/eloquent-mendel-vd8mfi 2>&1 | tail -5`. Expected: commit and push succeed. Do NOT open a PR. If the push is refused, STOP and put the exact command in the report for the owner.

## 5. Do not touch

- docs/context/decisions.md, docs/context/status.md, docs/context/known-issues.md (size caps; the orchestrator updates them).
- Litestream mentions deliberately left, for the owner to decide on the compliance records: docs/compliance.md, docs/UbyHost_workplan/**, docs/gap-report.md, docs/integrations/REFERENCES.md, docs/RETENTION*, docs/privacy/**, docs/archive/**, docs/plans/**, older briefs in docs/tasks/**, App/scripts/sqlite_to_postgres.py, App/tests/test_db_postgres.py.
- Already-correct "retired 2026-11-07" notes in deploy/lightsail/README.md, docs/LIGHTSAIL.md line 264 and docs/OPERATIONS.md line 560: leave as they are.
- Hard rules: 3 (no real bucket, key or host values anywhere), 9 (short sentences). No `.env` files, no new dependency.

## 6. Commands

- `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_backup_offsite.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` expects all passed.
- `cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -5` expects no errors.
- `shellcheck -S error deploy/lightsail/scripts/backup-s3.sh 2>&1 | tail -10` expects no output.

## 7. Acceptance

- [ ] `grep -n "install -m 600 -o root" docs/OPERATIONS.md | tail -3` prints nothing.
- [ ] `grep -n "WALG_UPLOAD_CONCURRENCY=1" docs/OPERATIONS.md | tail -3` prints one line.
- [ ] `grep -c "s3-no-check-bucket" deploy/lightsail/scripts/backup-s3.sh` prints 1 or more.
- [ ] `grep -n "walg-drill-pg 2>/dev/null" docs/OPERATIONS.md | tail -3` prints one line.
- [ ] `grep -n "ubyhost-walg-check.log" docs/OPERATIONS.md docs/LIGHTSAIL.md | tail -5` shows the `touch`/`chown` text in both files.
- [ ] Pytest and context lint green as in §6.
- [ ] Commit pushed to `claude/eloquent-mendel-vd8mfi`; no PR opened.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md; Part C is the part to drop);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1052-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- docs/OPERATIONS.md: the drill 2 block (step 7 anchor) and the step 9, 11 and 16 text; read the whole diff.
- deploy/lightsail/scripts/backup-s3.sh: the one-line rclone change.
- App/tests/test_backup_offsite.py: the new test only.
- docs/architecture.md still shows `SQLite ubyhost.db` in the diagram: outside this brief, flagged for the orchestrator.

## Owner steps

1. After the review, merge with `scripts/merge-pr-on-green.sh` (the orchestrator opens the PR).
2. On the server, if not done already: `sudo touch /var/log/ubyhost-walg-backup.log /var/log/ubyhost-walg-check.log && sudo chown ubuntu:ubuntu /var/log/ubyhost-walg-backup.log /var/log/ubyhost-walg-check.log`, and in `.env.walg` set `WALG_UPLOAD_CONCURRENCY=1`.
3. Decide whether the Litestream mentions in the compliance records (docs/compliance.md, docs/privacy/**, docs/RETENTION*, docs/UbyHost_workplan/**) need a correction; tell the orchestrator.
