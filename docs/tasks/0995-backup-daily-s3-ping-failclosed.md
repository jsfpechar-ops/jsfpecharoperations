# 0995: Daily off-site S3 backup, fail-closed Postgres dump, dead-man ping docs

Status: review
Note: step 10 (the K-BKP-S3-403 known-issues line) and its grep in step 11 were NOT applied (known-issues cap); see 0995-fix-1. Skip them.
Depends on: none | Base commit: 47640cf | Branch: task/0995-backup-daily-s3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

In production, `backup.sh` must exit 1 (and send no ping) whenever no PostgreSQL dump can be taken: if postgres is not running it stops before taking or pruning any snapshot, so failed runs can never age out the last good dumps; if `UBYHOST_DATABASE_URL` is unset it keeps the snapshot but still fails. The docs must show the daily off-site S3 cron, the 30-day S3 lifecycle expiry, the dead-man ping and the true retention (7 days local in production, 30 days off-site). The owner does the server and AWS steps (see "Owner steps").

## 2. Context

Rules: AGENTS.md rule 2 (new outbound request needs its reason in the PR), rule 3 (no secrets, bucket names, account ids or ping URLs in the repo), rule 4 (no new dependency). RETENTION (`docs/privacy/RETENTION.md` line 44): encrypted backups are kept "30 days local/off-site (G-D3)"; off-site expiry on S3 is a bucket lifecycle rule. Production local retention is `UBYHOST_BACKUP_RETENTION_DAYS=7` (docs/LIGHTSAIL.md, backup-layers table). Postgres has been the live DB since 2026-10-31. Litestream is being retired by brief 0996, which runs AFTER this one: here only say "being retired", do not remove it.

Facts (checked against the scripts, do not re-check):

- `backup.sh` sources `.env`, runs `backup_data.sh` in the container (new snapshot folder, then deletes snapshots older than `UBYHOST_BACKUP_RETENTION_DAYS`, newest always kept), then the Postgres dump, then the ping. `set -euo pipefail`: any `exit 1` means no ping.
- `backup-s3.sh` and `backup-gdrive.sh` both run `./scripts/backup.sh` first, so a refused backup also stops the upload. Neither reads `.env`, so the S3 bucket must be on the cron line.
- `backup-s3.sh` never deletes; the bucket lifecycle rule bounds S3 retention (30 days). `backup-gdrive.sh` deletes Drive copies older than 30 days (`rclone delete --min-age`, its own default, because it does not read `.env`).
- `deploy.sh` runs `./scripts/backup.sh` under `set -e` before every deploy (when the app container runs) and already refuses to deploy without a valid `ubyhost-pg.dump.age`. A new `exit 1` in production stops the deploy the same way the existing "no age recipient" check does. Outside production (`UBYHOST_DEPLOYMENT` not `production`, as in dev and CI) nothing changes.
- Times (UTC): local `backup.sh` daily 03:00; S3 daily 03:30; Drive weekly Sunday 04:00.

Excerpt A0, `deploy/lightsail/scripts/backup.sh` (guard 1 goes directly above this line):

```
docker compose exec -T ubyhost bash /app/scripts/backup_data.sh
```

Excerpt A, `deploy/lightsail/scripts/backup.sh` (guard 2 goes directly above this line):

```
if [ -n "${UBYHOST_DATABASE_URL:-}" ] && [ -n "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
```

Excerpt B, `App/tests/test_pg_backup_scripts.py` (existing style; the new code goes at the end of the file, after this last existing test):

```
def test_backup_refuses_plaintext_dump_in_production(tmp_path):
    root, bindir, log = make_tree(tmp_path, "UBYHOST_DEPLOYMENT=production\n" + PG_ENV)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "pg_dump" not in calls(log)
```

Helpers already in that file: `make_tree(tmp_path, env_text)` returns `(root, bindir, log)`; `run_script("backup.sh", root, bindir, log, extra_env=...)`; `calls(log)`; `PG_ENV`. The docker stub writes its arguments (without the word `docker`) to `$STUB_LOG` and reports postgres as running only when `PG_RUNNING=1`.

Excerpt C, `docs/LIGHTSAIL.md` (the Drive cron block; insert after its closing fence):

```
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh >> /var/log/ubyhost-gdrive.log 2>&1") | crontab -
```

Excerpt D, `docs/LIGHTSAIL.md` (layers table, three consecutive lines):

```
| Litestream → S3 | continuous (default 60 s sync), full snapshot daily, check weekly | 7 days | main recovery, including a new instance |
| `backup.sh` on the volume | daily 03:00 UTC | `UBYHOST_BACKUP_RETENTION_DAYS` (set `7` in production `.env`) | quick restore on the same server |
| `backup-gdrive.sh` | weekly | 30 days | copy outside AWS |
```

Excerpt I, `docs/LIGHTSAIL.md` (end of the "**Retention:**" paragraph):

```
before** they aged out. Drive uploads do not prune.
```

Excerpt E, `deploy/lightsail/README.md` (retention step):

```
   Once Litestream replicates to S3, set **7**: Litestream plus S3 versioning
   is the long-term copy, and 30 local full copies only fill the disk.
```

Excerpt J, `deploy/lightsail/README.md` (lifecycle sentence, three lines):

```
   Add a **lifecycle rule** that expires objects after
   `UBYHOST_BACKUP_RETENTION_DAYS` days (default 30) — the bucket, not the
   script, bounds off-site retention.
```

Excerpt F, `deploy/lightsail/README.md` (S3 cron, heading line plus code block):

````
Weekly cron (example; set your bucket name):

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1") | crontab -
```
````

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
| `deploy/lightsail/scripts/backup.sh` | edit | Two production guards: exit 1 when no dump can be taken |
| `App/tests/test_pg_backup_scripts.py` | edit | One curl-stub helper and three new tests |
| `docs/LIGHTSAIL.md` | edit | Daily S3 cron, lifecycle and ping paragraphs, Drive pruning, layers table |
| `deploy/lightsail/README.md` | edit | Retention step, S3 lifecycle sentence, daily S3 cron |
| `docs/OPERATIONS.md` | edit | True local retention and off-site expiry |
| `docs/context/known-issues.md` | edit | Observation about the first S3 run 403 |

No other file may change, except this brief's `Status:` line and the new report `docs/tasks/0995-report.md`. Status (`docs/context/status.md`) is updated by the orchestrator, not you.

Tool-call budget: read each file once (a range of 150 lines or fewer around the excerpt), then edit. Steps 3 to 10 have no own command: step 11 checks them all in one command.

## 4. Steps

1. In `deploy/lightsail/scripts/backup.sh`, directly above Excerpt A0, insert this block (with a blank line after it):

```bash
# Brief 0995: in production on PostgreSQL, never take or prune a snapshot while postgres is down.
# A run without the dump would age out the last good dumps. Exits before backup_data.sh and before the ping.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ -n "${UBYHOST_DATABASE_URL:-}" ] \
  && [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
  echo "Refusing to finish: the postgres container is not running in production, so no PostgreSQL dump can be taken." >&2
  exit 1
fi

```

   Then, directly above Excerpt A, insert this block (with a blank line after it):

```bash
# Brief 0995: production must never finish without a PostgreSQL dump. The snapshot above is kept; no ping is sent.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    echo "Refusing to finish: UBYHOST_DATABASE_URL is unset in production, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
  if [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
    echo "Refusing to finish: the postgres container stopped during the backup, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
fi

```

   Command: `bash -n deploy/lightsail/scripts/backup.sh 2>&1 | tail -30; grep -n "Refusing to finish\|bash /app/scripts/backup_data.sh\|curl -fsS" deploy/lightsail/scripts/backup.sh | tail -30`. Expected: no syntax output; then, in this line order: "postgres container is not running", `backup_data.sh`, "UBYHOST_DATABASE_URL is unset", "stopped during the backup", `curl -fsS`.

2. In `App/tests/test_pg_backup_scripts.py`, append after the last line of Excerpt B (two blank lines before the new code), exactly:

```python
PROD_ENV = "UBYHOST_DEPLOYMENT=production\nUBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n" \
    "UBYHOST_BACKUP_PING_URL=https://ping.invalid/x\n"


def add_curl_stub(bindir):
    """A curl stub on PATH that records the ping instead of sending it."""
    curl = bindir / "curl"
    curl.write_text('#!/usr/bin/env bash\necho "curl $*" >> "$STUB_LOG"\n')
    curl.chmod(0o755)


def test_backup_fails_in_production_without_database_url_but_keeps_snapshot(tmp_path):
    root, bindir, log = make_tree(tmp_path, PROD_ENV)
    add_curl_stub(bindir)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "UBYHOST_DATABASE_URL is unset" in result.stderr
    recorded = calls(log)
    assert "backup_data.sh" in recorded
    assert "pg_dump" not in recorded
    assert "curl" not in recorded


def test_backup_fails_in_production_when_postgres_not_running_before_any_snapshot(tmp_path):
    root, bindir, log = make_tree(tmp_path, PROD_ENV + PG_ENV)
    add_curl_stub(bindir)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "0"})
    assert result.returncode == 1
    assert "postgres container is not running" in result.stderr
    recorded = calls(log)
    assert "backup_data.sh" not in recorded
    assert "pg_dump" not in recorded
    assert "curl" not in recorded


def test_backup_production_with_running_postgres_dumps_and_pings(tmp_path):
    root, bindir, log = make_tree(tmp_path, PROD_ENV + PG_ENV)
    add_curl_stub(bindir)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert "pg_dump -U ubyhost -Fc ubyhost" in recorded
    assert "curl -fsS -m 10 --retry 3 https://ping.invalid/x" in recorded
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, the old tests included (the non-production `running=0` case still exits 0).

3. `docs/LIGHTSAIL.md`: after the closing fence of the code block that holds Excerpt C, and before the paragraph that starts "`backup.sh` runs `sqlite3", insert exactly (blank line before and after):

````
Daily off-site to S3 (03:30 UTC, after the 03:00 local backup) after `rclone config` remote **`s3`**. `backup-s3.sh` first runs `backup.sh` itself (a fresh snapshot), so a failed backup also stops the upload:

```bash
(crontab -l 2>/dev/null; echo "30 3 * * * cd /opt/ubyhost/deploy/lightsail && UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1") | crontab -
```

`backup-s3.sh` never deletes old copies: an S3 lifecycle rule on the `UbyHost-backups/` prefix expires them after 30 days (the off-site window in `docs/privacy/RETENTION.md`). Check a run with `tail -30 /var/log/ubyhost-s3.log`; a good run ends with `Uploaded to`.

In production `backup.sh` exits 1 and sends no ping when no PostgreSQL dump can be taken: with postgres stopped it takes and prunes no snapshot; with `UBYHOST_DATABASE_URL` unset it keeps the snapshot but still fails. A failed pre-deploy backup stops `deploy.sh`. Dead-man ping: `UBYHOST_BACKUP_PING_URL` in `.env` holds the ping URL of a healthchecks.io check (period 1 day, grace 2 hours); `backup.sh` calls it only after a complete backup, so a missed or failed night raises an alert.
````

   Command: none (checked in step 11).

4. `docs/LIGHTSAIL.md`: replace the three lines of Excerpt D with these four lines (one Edit):

```
| Litestream → S3 (being retired, brief 0996; replicates the old SQLite file, not PostgreSQL) | continuous | 7 days | not a recovery path since the move to PostgreSQL |
| `backup.sh` on the volume | daily 03:00 UTC | `UBYHOST_BACKUP_RETENTION_DAYS` (set `7` in production `.env`) | quick restore on the same server |
| `backup-s3.sh` | daily 03:30 UTC | 30 days (bucket lifecycle rule) | main off-site copy, including a new instance |
| `backup-gdrive.sh` | weekly | 30 days | second copy outside AWS |
```

   (The S3 row is new.) Command: none (step 11).

5. `docs/LIGHTSAIL.md`: in Excerpt I, replace `Drive uploads do not prune.` with `` `backup-gdrive.sh` deletes Drive copies older than 30 days; the S3 lifecycle rule expires S3 copies after 30 days.`` Keep `before** they aged out. ` in front of it. Command: none (step 11).

6. `deploy/lightsail/README.md`: replace the two lines of Excerpt E with:

```
   Production uses **7**: the daily S3 copy (30 days, bucket lifecycle rule) is
   the long-term copy, and 30 local full copies only fill the disk.
```

   Command: none (step 11).

7. `deploy/lightsail/README.md`: replace the three lines of Excerpt J with:

```
   Add a **lifecycle rule** on the `UbyHost-backups/` prefix that expires
   objects after 30 days (the off-site window in `docs/privacy/RETENTION.md`;
   the local `UBYHOST_BACKUP_RETENTION_DAYS` is 7 in production) — the bucket,
   not the script, bounds off-site retention.
```

   Command: none (step 11).

8. `deploy/lightsail/README.md`: in Excerpt F, replace the heading line `Weekly cron (example; set your bucket name):` with `Daily cron (03:30 UTC, after the 03:00 local backup; example, set your bucket name):` and, in the crontab line, replace `echo "0 4 * * 0 cd` with `echo "30 3 * * * cd`. Change nothing else in that line. Command: none (step 11).

9. `docs/OPERATIONS.md`: replace the five lines of Excerpt G with:

```
- **Retention is by time, not count.** `UBYHOST_BACKUP_RETENTION_DAYS` is the
  local window (code default 30; **production sets 7**); snapshots older than it
  are removed on each run, and the newest snapshot is always kept even if it is
  older than the window. Off-site copies are kept 30 days: an S3 bucket
  lifecycle rule expires them (`backup-s3.sh` never deletes), and
  `backup-gdrive.sh` deletes Drive copies older than 30 days.
```

   Command: none (step 11).

10. `docs/context/known-issues.md`: directly after the line of Excerpt H, add this one line:

```
- K-BKP-S3-403: Observation (not a bug yet). The first S3 off-site run on 1 Nov got a 403, then succeeded on retry. Recheck the S3 log after the first daily runs (brief 0995); if the 403 repeats, check the IAM policy for the bucket and prefix.
```

   Command: none (step 11).

11. Check steps 3 to 10 in one command (repo root):

```
grep -n "30 3 \* \* \*\|main recovery\|Drive uploads do not prune\|Once Litestream replicates\|production sets 7\|K-BKP-S3-403\|on the \`UbyHost-backups/\` prefix\|backup-s3.sh\` | daily" docs/LIGHTSAIL.md deploy/lightsail/README.md docs/OPERATIONS.md docs/context/known-issues.md | tail -30
```

   Expected exactly these matches and no others: `docs/LIGHTSAIL.md` three times (`30 3 * * *` cron, lifecycle sentence `on the `UbyHost-backups/` prefix`, `backup-s3.sh` | daily row); `deploy/lightsail/README.md` twice (`on the `UbyHost-backups/` prefix`, `30 3 * * *` cron); `docs/OPERATIONS.md` once (`production sets 7`); `docs/context/known-issues.md` once (`K-BKP-S3-403`). Any `main recovery`, `Drive uploads do not prune` or `Once Litestream replicates` match means a step was missed.

12. Run the remaining commands of section 6.

## 5. Do not touch

`deploy/lightsail/scripts/backup-s3.sh`, `backup-gdrive.sh`, `deploy.sh`, `pg-cutover.sh`, `App/scripts/backup_data.sh`, `App/app/`, Litestream files and the `docs/LIGHTSAIL.md` restore sections (brief 0996 removes Litestream), `docs/context/status.md`, `docs/privacy/RETENTION.md`, `.env.example`. The Drive cron line stays `0 4 * * 0`. Rules 2-4 and 8 of AGENTS.md. No ping URL, bucket name or AWS account id anywhere in the repo (the test uses `https://ping.invalid/x`, which is not a real host).

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` -> all pass.
- `shellcheck -S error deploy/lightsail/scripts/backup.sh 2>&1 | tail -30` -> no output (if shellcheck is not installed, skip and say so in the report).
- `python3 scripts/context_lint.py 2>&1 | tail -30` (repo root) -> passes.
- `git diff -U0 -- docs deploy | grep -nE '^\+.*([0-9]{12}|hc-ping\.com/|ping\.invalid|s3://)' | tail -30` -> no output.
- `git status --short | tail -30` -> only the six files of section 3, this brief, and `docs/tasks/0995-report.md`.

## 7. Acceptance

- [ ] Step 1 grep shows the guard order: "not running" line < `backup_data.sh` line < "UBYHOST_DATABASE_URL is unset" < "stopped during the backup" < `curl -fsS`.
- [ ] `test_pg_backup_scripts.py`: the three new tests and all old tests pass.
- [ ] Step 11 grep shows exactly the seven expected matches.
- [ ] `git diff -- docs/LIGHTSAIL.md deploy/lightsail/README.md | grep -c "backup-gdrive.sh >>"` prints `0` (Drive cron unchanged).
- [ ] The secrets grep of section 6 prints nothing.
- [ ] Lint passes; shellcheck passes or is reported as not installed.

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

- `deploy/lightsail/scripts/backup.sh`: guard 1 must sit above `backup_data.sh` (no snapshot, no pruning while postgres is down), guard 2 above the dump `if`, both before the ping. Outside production nothing changes.
- Consequence the orchestrator accepted by sending this brief: a production server on SQLite (`UBYHOST_DATABASE_URL` unset, for example after `pg-cutover.sh rollback`) now gets a failing nightly backup (snapshot still kept, no ping, healthchecks alert), `deploy.sh` refuses to deploy, and `pg-cutover.sh rehearse`/`cutover` refuse in production. The cutover is done (2026-10-31), so this is the intended alarm.
- Doc fix for the orchestrator (not in this brief): `docs/privacy/RETENTION.md` line 44, "Kept" cell `30 days local/off-site (G-D3)` should read `7 days local in production (code default 30); 30 days off-site: S3 lifecycle rule, Drive pruned by backup-gdrive.sh (G-D3)`, and the enforcement cell should add `; backup-gdrive.sh rclone delete --min-age`. Also the header comment in `backup-s3.sh` (line 6) still says the lifecycle rule uses `UBYHOST_BACKUP_RETENTION_DAYS`; it should say 30 days.
- Brief 0996 later removes Litestream text from the same docs (overlapping files: 0995 goes first).
- PR text: add "New outbound request: dead-man ping to healthchecks.io after each successful backup, so a silently stopped backup is noticed. No new request is added by this PR's code; the ping already exists, this PR documents it and makes production fail before it when the PostgreSQL dump is missing."

## Owner steps

Do these after the PR is merged and you have deployed as usual. Numbered, plain words. Do B before A.

**B. Make old S3 copies expire after 30 days (one time, in AWS)**

Note: when the rule is on, AWS deletes every backup copy in that folder that is already older than 30 days, within about two days. That is what the privacy rules require.

1. Sign in to the AWS console. In the search box at the top type **S3** and click **S3**.
2. Click the name of your backup bucket (the name in your `backup-s3.sh` cron line).
3. Click the **Management** tab, then **Create lifecycle rule**.
4. **Lifecycle rule name:** `expire-backups-30d`.
5. Under **Choose a rule scope**, pick **Limit the scope of this rule using one or more filters**. In **Prefix** type `UbyHost-backups/` (with the slash at the end).
6. Under **Lifecycle rule actions** tick **Expire current versions of objects**. If the bucket has versioning on (bucket **Properties** tab, **Bucket Versioning: Enabled**), also tick **Permanently delete noncurrent versions of objects**.
7. In **Expire current versions of objects**, **Days after object creation**: type `30`.
8. Only if you ticked the second box: in **Permanently delete noncurrent versions of objects**, **Days after objects become noncurrent**: type `1`; leave **Number of newer versions to retain** empty.
9. Tick the box that confirms the rule applies to the prefix (if shown), then click **Create rule**. In the list it must show **Status: Enabled**.

**A. Run the S3 backup daily**

1. Log in to the server (your usual SSH command).
2. Type `crontab -l | grep backup-s3` and press Enter. Note the log file at the end of the line.
3. Type `crontab -e` and press Enter. If it asks which editor, type `1` (nano) and press Enter.
4. Find the line that contains `backup-s3.sh`. Replace only the first five fields (the time part before `cd`, for example `0 4 * * 0`) with `30 3 * * *`. Leave the rest of the line (bucket name, command, log file) exactly as it is. If there is no such line, add the line from `docs/LIGHTSAIL.md` ("Daily off-site to S3"), with your bucket name instead of `your-bucket-name`.
5. Do not change the `backup.sh` line (`0 3 * * *`) or the `backup-gdrive.sh` line (`0 4 * * 0`).
6. Save and close: Ctrl+O, Enter, Ctrl+X. Type `crontab -l | grep backup-s3`: the line must start with `30 3 * * *`.
7. Type `grep BACKUP_RETENTION_DAYS /opt/ubyhost/deploy/lightsail/.env`. It must show `UBYHOST_BACKUP_RETENTION_DAYS=7`. If it shows nothing or another number, tell the orchestrator chat; do not change it yourself.

**C. Check the dead-man ping (healthchecks.io, free plan)**

1. On the server type `grep -c '^UBYHOST_BACKUP_PING_URL=https' /opt/ubyhost/deploy/lightsail/.env`. If it prints `1`, the ping is already set: go to step 5.
2. Go to healthchecks.io and sign in (or sign up; the free plan is enough). Click **Add Check**. A new check appears.
3. Click the check's name, type `UbyHost nightly backup`, and click **Save**. Click **Change Schedule…**, set **Period** to `1 day` and **Grace Time** to `2 hours`, and click **Save**. Copy the ping URL shown on the check page. Do not paste it anywhere public or into the repo.
4. On the server type `nano /opt/ubyhost/deploy/lightsail/.env`. Set the line `UBYHOST_BACKUP_PING_URL=` to the URL you copied (no spaces, no quotes). Save and close: Ctrl+O, Enter, Ctrl+X.
5. In healthchecks.io open the check and make sure **Period** is 1 day and **Grace Time** about 2 hours (click **Change Schedule…** to change them). Under **Integrations** the e-mail to your address must be on.
6. On the server type `cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh 2>&1 | tail -30`. The output must not contain `Refusing`. In healthchecks.io the check shows a new ping (green) within a minute.
7. If the output says `Refusing to finish: the postgres container is not running`, type `docker compose ps` and send the output to the orchestrator chat. Do not deploy until it is fixed.

**D. Check the first daily S3 run**

1. The morning after step A, log in and type `tail -30` followed by the log file you noted in A2 (for example `tail -30 /var/log/ubyhost-s3.log`). A good run ends with `Uploaded to`.
2. If you see `403` or `AccessDenied`, copy those 30 lines to the orchestrator chat (known-issues K-BKP-S3-403).
3. In the S3 console, open the bucket and the `UbyHost-backups/` folder: there is a new folder dated today.
4. About 32 days after step B, check that no folder there is older than 30 days (proof the lifecycle rule works).
