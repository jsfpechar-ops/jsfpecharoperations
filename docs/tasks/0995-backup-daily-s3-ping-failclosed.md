# 0995: Daily off-site S3 backup, fail-closed Postgres dump, dead-man ping docs

Status: todo
Depends on: none | Base commit: 47640cf | Branch: task/0995-backup-daily-s3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`backup.sh` must exit non-zero (and send no ping) in production when the Postgres dump is skipped because `UBYHOST_DATABASE_URL` is unset or the postgres container is not running. The docs must show a daily off-site S3 cron, the 30-day S3 lifecycle expiry, the dead-man ping setup, and the true local retention (7 days in production). The owner does the server and AWS steps (see "Owner steps").

## 2. Context

Rules: AGENTS.md rule 2 (new outbound request needs its reason in the PR), rule 3 (no secrets, bucket names or URLs in the repo), rule 4 (no new dependency). RETENTION (`docs/privacy/RETENTION.md` line 44): encrypted backups are kept "30 days local/off-site (G-D3)"; off-site expiry is an S3 lifecycle rule. Production local retention is `UBYHOST_BACKUP_RETENTION_DAYS=7` (docs/LIGHTSAIL.md, backup-layers table). Postgres has been the live DB since 2026-10-31. Litestream is being retired by brief 0996, which runs AFTER this one: here only say "being retired", do not remove it.

Facts the docs must end up stating: local `backup.sh` daily 03:00 UTC; S3 daily 03:30 UTC; Drive weekly Sunday 04:00 UTC; `backup-s3.sh` never deletes old copies, so the bucket lifecycle rule bounds off-site retention (30 days).

Excerpt A, `deploy/lightsail/scripts/backup.sh` (the guard goes directly above this line):

```
if [ -n "${UBYHOST_DATABASE_URL:-}" ] && [ -n "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
```

Excerpt B, `App/tests/test_pg_backup_scripts.py` (existing style; the new tests go at the end of the file, after this last existing test):

```
def test_backup_refuses_plaintext_dump_in_production(tmp_path):
    root, bindir, log = make_tree(tmp_path, "UBYHOST_DEPLOYMENT=production\n" + PG_ENV)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "pg_dump" not in calls(log)
```

Helpers already in that file: `make_tree(tmp_path, env_text)` returns `(root, bindir, log)`; `run_script("backup.sh", root, bindir, log, extra_env=...)`; `calls(log)`; `PG_ENV`. The docker stub only reports postgres as running when `PG_RUNNING=1`.

Excerpt C, `docs/LIGHTSAIL.md` (cron block):

```
Weekly off-site (Sunday 04:00 UTC) after `rclone config` remote **`gdrive`**:
```

Excerpt D, `docs/LIGHTSAIL.md` (layers table, two rows):

```
| Litestream → S3 | continuous (default 60 s sync), full snapshot daily, check weekly | 7 days | main recovery, including a new instance |
```

```
| `backup-gdrive.sh` | weekly | 30 days | copy outside AWS |
```

Excerpt E, `deploy/lightsail/README.md` (retention step):

```
   Once Litestream replicates to S3, set **7**: Litestream plus S3 versioning
   is the long-term copy, and 30 local full copies only fill the disk.
```

Excerpt F, `deploy/lightsail/README.md` (S3 cron):

```
Weekly cron (example; set your bucket name):
```

```
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1") | crontab -
```

Excerpt G, `docs/OPERATIONS.md` (about line 535):

```
- **Retention is by time, not count.** `UBYHOST_BACKUP_RETENTION_DAYS` (default
  30) is the window; snapshots older than it are removed on each run, and the
  newest snapshot is always kept even if it is older than the window. The
  off-site copies must expire on the same window — OPS-2 adds that to the
  Drive/S3 jobs.
```

Excerpt H, `docs/context/known-issues.md`:

```
- K-PG-ORDER: goose tests fail after icalsync locally; CI OK.
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/backup.sh` | edit | Production guard: exit 1 if the dump would be skipped |
| `App/tests/test_pg_backup_scripts.py` | edit | Three new tests |
| `docs/LIGHTSAIL.md` | edit | Daily S3 cron, lifecycle and ping paragraphs, layers table |
| `deploy/lightsail/README.md` | edit | Retention step, S3 lifecycle line, daily S3 cron |
| `docs/OPERATIONS.md` | edit | True local retention and off-site expiry |
| `docs/context/known-issues.md` | edit | Observation about the first S3 run 403 |

No other file may change. Status (`docs/context/status.md`) is updated by the orchestrator, not you.

## 4. Steps

1. In `deploy/lightsail/scripts/backup.sh`, directly above Excerpt A, insert this block (keep a blank line after it). Command: `bash -n deploy/lightsail/scripts/backup.sh 2>&1 | tail -30`. Expected: no output.

```bash
# Production must never skip the PostgreSQL dump silently: no dump means no usable backup, so fail before the ping.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    echo "Refusing to finish: UBYHOST_DATABASE_URL is unset in production, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
  if [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
    echo "Refusing to finish: the postgres container is not running in production, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
fi

```

2. In `App/tests/test_pg_backup_scripts.py`, append after the last line of Excerpt B (blank line between tests), exactly:

```python
def test_backup_fails_in_production_without_database_url(tmp_path):
    root, bindir, log = make_tree(
        tmp_path, "UBYHOST_DEPLOYMENT=production\nUBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n")
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "UBYHOST_DATABASE_URL is unset" in result.stderr
    assert "pg_dump" not in calls(log)


def test_backup_fails_in_production_when_postgres_not_running_and_sends_no_ping(tmp_path):
    root, bindir, log = make_tree(
        tmp_path,
        "UBYHOST_DEPLOYMENT=production\nUBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n"
        "UBYHOST_BACKUP_PING_URL=https://ping.invalid/x\n" + PG_ENV)
    curl = bindir / "curl"
    curl.write_text('#!/usr/bin/env bash\necho "curl $*" >> "$STUB_LOG"\n')
    curl.chmod(0o755)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "0"})
    assert result.returncode == 1
    assert "postgres container is not running" in result.stderr
    assert "curl" not in calls(log)


def test_backup_production_with_running_postgres_still_pings(tmp_path):
    root, bindir, log = make_tree(
        tmp_path,
        "UBYHOST_DEPLOYMENT=production\nUBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n"
        "UBYHOST_BACKUP_PING_URL=https://ping.invalid/x\n" + PG_ENV)
    curl = bindir / "curl"
    curl.write_text('#!/usr/bin/env bash\necho "curl $*" >> "$STUB_LOG"\n')
    curl.chmod(0o755)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 0, result.stderr
    assert "pg_dump" in calls(log)
    assert "curl" in calls(log)
```

Command: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (existing tests included, including the non-production `running=0` case that still exits 0).

3. `docs/LIGHTSAIL.md`: after the Drive cron code block (the closing fence that follows the `backup-gdrive.sh` crontab line), and before the paragraph starting "`backup.sh` runs `sqlite3", insert exactly:

````
Daily off-site to S3 (03:30 UTC, after the 03:00 local backup). Edit the crontab with `crontab -e`; the line is:

```
30 3 * * * cd /opt/ubyhost/deploy/lightsail && UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1
```

`backup-s3.sh` never deletes old copies. Set an S3 lifecycle rule on the backup prefix that expires objects after 30 days (the off-site window in `docs/privacy/RETENTION.md`). Check a run with `tail -30 /var/log/ubyhost-s3.log`.

`backup.sh` exits non-zero and sends no ping in production when the PostgreSQL dump was skipped (`UBYHOST_DATABASE_URL` unset or postgres not running). Dead-man ping: set `UBYHOST_BACKUP_PING_URL` in `.env` to a free healthchecks.io check (daily period); `backup.sh` calls it only after a complete successful backup, so a missed or failed backup raises an alert. Reason for this outbound request: it is the only way to learn that the nightly backup silently stopped.
````

Command: `grep -n "30 3 \* \* \*" docs/LIGHTSAIL.md | tail -30`. Expected: one match.

4. `docs/LIGHTSAIL.md`: replace Excerpt D's first row with:
`| Litestream → S3 (being retired, brief 0996; replicates the old SQLite file, not Postgres) | continuous | 7 days | not a recovery path since the move to PostgreSQL |`
Then replace Excerpt D's second row with these two rows:
`| `backup-s3.sh` | daily 03:30 UTC | 30 days (bucket lifecycle rule) | main off-site copy outside the server, including a new instance |`
`| `backup-gdrive.sh` | weekly | 30 days | second copy outside AWS |`
Command: `grep -n "main recovery" docs/LIGHTSAIL.md | tail -30`. Expected: no output.

5. `deploy/lightsail/README.md`: replace Excerpt E (the two lines) with:
`   Production uses **7**: the daily S3 copy (30 days, bucket lifecycle rule) is the`
`   long-term copy, and 30 local full copies only fill the disk.`
Command: `grep -n "Once Litestream replicates" deploy/lightsail/README.md | tail -30`. Expected: no output.

6. `deploy/lightsail/README.md`: replace Excerpt F's heading line with `Daily cron (03:30 UTC, after the 03:00 local backup; example, set your bucket name):` and in the crontab line replace the text `0 4 * * 0 cd` with `30 3 * * * cd`. Command: `grep -n "30 3 \* \* \*" deploy/lightsail/README.md | tail -30`. Expected: one match.

7. `deploy/lightsail/README.md`: in the lifecycle sentence ("Add a **lifecycle rule** that expires objects after `UBYHOST_BACKUP_RETENTION_DAYS` days (default 30) — the bucket, not the script, bounds off-site retention."), replace "`UBYHOST_BACKUP_RETENTION_DAYS` days (default 30)" with "30 days (the off-site window in RETENTION.md; the local `UBYHOST_BACKUP_RETENTION_DAYS` is 7 in production)". Keep the rest of the sentence. Command: `grep -n "off-site window in RETENTION" deploy/lightsail/README.md | tail -30`. Expected: one match.

8. `docs/OPERATIONS.md`: replace Excerpt G with:

```
- **Retention is by time, not count.** `UBYHOST_BACKUP_RETENTION_DAYS` is the
  local window (code default 30; **production sets 7**); snapshots older than it
  are removed on each run, and the newest snapshot is always kept even if it is
  older than the window. The off-site S3 copies expire after 30 days through a
  bucket lifecycle rule (`backup-s3.sh` never deletes), the Drive copies are
  not pruned.
```

Command: `grep -n "production sets 7" docs/OPERATIONS.md | tail -30`. Expected: one match.

9. `docs/context/known-issues.md`: after Excerpt H add a new line:
`- K-BKP-S3-403: Observation (not a bug yet). The first S3 off-site run on 1 Nov got a 403, then succeeded on retry. Recheck `/var/log/ubyhost-s3.log` after the first daily runs (brief 0995); if 403 repeats, check the IAM policy for the bucket and prefix.`
Command: `grep -n "K-BKP-S3-403" docs/context/known-issues.md | tail -30`. Expected: one match.

10. Run the lint and shellcheck (Section 6).

## 5. Do not touch

`deploy/lightsail/scripts/backup-s3.sh`, `backup_data.sh`, `App/app/`, Litestream files and `docs/LIGHTSAIL.md` restore sections (brief 0996 removes Litestream), `docs/context/status.md`, `docs/privacy/RETENTION.md`, `.env.example`. Rules 2-4 and 8 of AGENTS.md. No URL value, bucket name or account id anywhere in the repo.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` -> all pass.
- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` -> no output (skip and note in the report if shellcheck is not installed).
- `python3 scripts/context_lint.py 2>&1 | tail -30` (repo root) -> passes.
- `git diff --stat | tail -30` -> only the six files of section 3 plus the report.

## 7. Acceptance

- [ ] `grep -n "UBYHOST_DEPLOYMENT:-}\" = \"production\"" deploy/lightsail/scripts/backup.sh | tail -30` shows two matches (the old one and the new guard).
- [ ] The three new tests and all old tests in the file pass.
- [ ] `grep -n "main recovery" docs/LIGHTSAIL.md | tail -30` returns nothing.
- [ ] Both cron examples read `30 3 * * *`; the Drive cron is unchanged.
- [ ] `grep -rn "ping.invalid\|852064978767" docs deploy | tail -30` returns nothing.
- [ ] Lint and shellcheck pass.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0995-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`deploy/lightsail/scripts/backup.sh` (the guard must sit before the dump `if`, and before the ping), the three new tests, `docs/LIGHTSAIL.md` cron and layers table. Note for the orchestrator: `docs/privacy/RETENTION.md` line 44 says "30 days local/off-site" but production local retention is 7; this brief does not change RETENTION.md. Brief 0996 later removes Litestream text from the same docs (overlapping files: tell the owner 0995 goes first). PR text: add "New outbound request: dead-man ping to healthchecks.io after each successful daily backup, so a silently stopped backup is noticed."

## Owner steps

Do these after the PR is merged and you have deployed as usual. Numbered, plain words.

**A. Change the S3 backup from monthly to daily**

1. Open a terminal and log in to the server (your usual SSH command).
2. Type `crontab -e` and press Enter. An editor opens.
3. Find the line that contains `backup-s3.sh`. It starts with `0 5 1 * *`.
4. Replace only those first five fields `0 5 1 * *` with `30 3 * * *`. Leave everything after them (the bucket name, the command, the log file) exactly as it is.
5. Do not touch the other two lines (`0 3 * * *` local backup, `0 4 * * 0` Drive).
6. Save and close (in nano: Ctrl+O, Enter, Ctrl+X). Check with `crontab -l | grep backup-s3`: it must start with `30 3 * * *`.
7. Check the local retention: `grep BACKUP_RETENTION_DAYS /opt/ubyhost/deploy/lightsail/.env` must show `=7`.

**B. Make old S3 copies expire after 30 days (one time, in AWS)**

1. Open the AWS console, search for **S3**, open it, and click your backup bucket (the one named in the cron line).
2. Click the **Management** tab, then **Create lifecycle rule**.
3. Rule name: `expire-backups-30d`.
4. Choose **Limit the scope of this rule using one or more filters**. In **Prefix** type `UbyHost-backups/`.
5. Under **Lifecycle rule actions** tick only **Expire current versions of objects**.
6. In **Days after object creation** type `30`. If the bucket has versioning on, also tick **Permanently delete noncurrent versions of objects** and type `1`.
7. Click **Create rule**. The rule must show as **Enabled**.

**C. Turn on the dead-man ping (healthchecks.io, free tier)**

1. Go to healthchecks.io and sign in (or create a free account).
2. Click **Add Check**. Name it `UbyHost nightly backup`. Set **Period** to 1 day and **Grace Time** to 2 hours. Save.
3. Copy the ping URL the page shows. Do not paste it anywhere public or into the repo.
4. On the server: `nano /opt/ubyhost/deploy/lightsail/.env`. Set the line `UBYHOST_BACKUP_PING_URL=` to the URL you copied (no spaces, no quotes). Save and close.
5. Run once by hand: `cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh 2>&1 | tail -30`. The last output must not say "Refusing to finish". In healthchecks.io the check turns green within a minute.
6. If the line says "Refusing to finish", the Postgres dump was skipped: run `docker compose ps` and start postgres, then repeat step 5.

**D. Check that the first daily S3 run worked**

1. The morning after step A, log in and run `tail -30 /var/log/ubyhost-s3.log`. A good run ends with an upload message and no error text.
2. If you see `403` or `AccessDenied`, copy the last 30 lines to the orchestrator chat. (The 1 Nov run got a 403 and then succeeded on retry; this is recorded in known-issues as K-BKP-S3-403 for a recheck.)
3. In the S3 console, open the bucket and the `UbyHost-backups/` folder: you should see a new object dated today.
4. After 30 days, check that the oldest objects are gone (proof the lifecycle rule works).
