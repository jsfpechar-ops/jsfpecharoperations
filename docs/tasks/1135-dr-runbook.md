# 1135: Disaster recovery runbook

> Renumbered from 1133 on 2026-11-12: 1133 was also used by the Go deadlines repoint brief (#934). Commits made before the rename say "1133".

Status: todo
Depends on: none | Base commit: HEAD of claude/fervent-cray-1qsrfa | Branch: claude/fervent-cray-1qsrfa
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Write `docs/DISASTER_RECOVERY.md`: one provider-neutral runbook to rebuild UbyHost on a fresh EU Ubuntu box (Hetzner as the example) from the Google Drive backup, with no AWS login. Docs only; plan: [portable-disaster-recovery](../plans/portable-disaster-recovery.md).

## 2. Context

Facts, each verified by the orchestrator (grep to confirm; if one is missing, STOP, section 8):

- Backups: `deploy/lightsail/scripts/backup.sh` writes `ubyhost-pg.dump.age` into `/data/backups/<stamp>/` (volume `ubyhost-data`), age-encrypted. `backup-gdrive.sh` copies only `*.age` to Drive folder `UbyHost-backups/<stamp>` through rclone remote `gdrive`, weekly (Sunday 04:00 UTC), 30-day retention.
- Age identity: password manager plus one offline copy, never on the server (`docs/OPERATIONS.md`, "Key custody").
- `pg-restore.sh <stamp>` needs `AGE_IDENTITY_FILE`, a running `postgres` service, and the dump inside the volume at `/data/backups/<stamp>/`. It refuses while `.env` has `UBYHOST_DB=`. It stops `worker` and `ubyhost`, pipes `age -d` into `pg_restore --clean --if-exists --single-transaction`.
- Existing rebuild steps: `docs/LIGHTSAIL.md` section "Restore onto a **new** Lightsail instance" (about lines 286-310), incl. `UBYHOST_SECRET_KEY` before first deploy and origin certs `caddy/certs/origin*.pem`.
- Cloudflare: `docs/CLOUDFLARE.md`, `CLOUDFLARE_PROXY=1`, Full (strict).
- Filing: job kind `submit` runs in the Go service only when in `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` (`docs/ENVIRONMENT.md` line ~53). Filing deadline 3 working days.
- Mail: `UBYHOST_MAIL_BACKEND=ses`, region eu-central-1; outbox queues when SES is unreachable.
- WAL-G and S3 are AWS-only; the runbook does not depend on them.

Gap known to the runbook: `pg-restore.sh` cannot read a file straight from Drive. Until a later brief adds it, the runbook uses this workaround, which you write exactly as the owner's steps: download `<stamp>/ubyhost-pg.dump.age` with `rclone copy gdrive:UbyHost-backups/<stamp> ./restore-in`, run `./scripts/deploy.sh` once so the volume exists, then place the file with
`docker run --rm -v ubyhost-data:/data -v "$PWD/restore-in":/in alpine sh -c 'mkdir -p /data/backups/<stamp> && cp /in/ubyhost-pg.dump.age /data/backups/<stamp>/'`
and run `pg-restore.sh <stamp>`. Mark this block "(workaround until brief for a restore-from-file option)".

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/DISASTER_RECOVERY.md | create | the runbook, at most 2,500 tokens |
| docs/tasks/1135-report.md | create | report (section 9) |

No other file may change.

## 4. Steps

1. Run `grep -n 'Restore onto a' docs/LIGHTSAIL.md | tail -3`, then read 40 lines from that line. Expected: the restore list. Run `grep -n 'GO_JOB_KINDS' docs/ENVIRONMENT.md | tail -3`.
2. Create `docs/DISASTER_RECOVERY.md` with these sections, in this order, plain words, every command in its own fenced block, numbered owner steps:
   - **When to use this** (AWS or Lightsail unreachable for more than a few hours; filing deadline is 3 working days; last fallback is filing by hand in the police portal).
   - **Before you start: the offline pack** (list, no values: age identity file, `.env`, `UBYHOST_SECRET_KEY`, `caddy/certs/origin*.pem`, rclone `gdrive` access via the Google account, Cloudflare login, domain). Say: if the pack is missing, stop and see the fallback.
   - **Two servers never file at once** (stop the old server or remove `submit` from `UBYHOST_GO_JOB_KINDS` there first; on the new box confirm `submit` is in neither variable until the owner is sure the old one is off; then enable and restart). Own steps and commands.
   - **Rebuild on a new box** (numbered): create an EU Ubuntu box with ports 22, 80, 443 (Hetzner Cloud console as example); `git clone` the repo to `/opt/ubyhost`; run `setup-server.sh`; copy `.env` and origin certs from the pack; install rclone and age; `rclone config` for `gdrive`; list Drive with `rclone lsd gdrive:UbyHost-backups`; download the newest stamp; `./scripts/deploy.sh`; the workaround block from section 2; `./scripts/pg-restore.sh <stamp>`; `./scripts/status.sh`; open one stay and one Doručenka via `curl --resolve`.
   - **Point Cloudflare at the new box** (A record to the new IP, proxied, Full (strict); `CLOUDFLARE_PROXY=1`).
   - **What AWS gave us and what happens without it**: a 5-row table: SES mail (queues and waits; optional SMTP switch is a later brief), S3 copies and WAL-G (gone; Drive is the source; PITR is not available after a rebuild until re-set), Lightsail snapshots (not needed), static IP (new IP in Cloudflare), UbyPort (not AWS, unaffected). State plainly: data may be up to 7 days old; guests filed since may need re-checking against police receipts.
   - **After the move**: re-enable cron lines (backup 03:00, Drive Sunday 04:00), run `backup.sh` once, name the new provider in the `/subprocessors` register and `docs/privacy/ROPA.md` (owner/lawyer step; the provider must be EU; do this before real guest data moves if time allows, otherwise the same day).
   - **Drill** (every 3 months with the restore drill; time it; write minutes in status; delete the box after; skip the Cloudflare step).
3. Run `wc -c docs/DISASTER_RECOVERY.md` (expect under 10000) and `python3 scripts/context_lint.py 2>&1 | tail -15`. Fix any ERROR for your files.
4. `git add docs/DISASTER_RECOVERY.md && git commit -m "docs: disaster recovery runbook (1135)"`. Never push.
5. Write `docs/tasks/1135-report.md`, set `Status: review`, commit it with `git commit -m "docs: 1135 report"`.

## 5. Do not touch

`App/`, `go/`, `deploy/`, any existing file. No secrets, hostnames from `.env`, IPs or guest data in the text (use placeholders like `<NEW_IP>`). Rule 3 (public repo). No push, PR or merge.

## 6. Commands

- `test -f docs/DISASTER_RECOVERY.md && echo ok | tail -30` expect `ok`.
- `python3 scripts/context_lint.py 2>&1 | tail -15` expect no ERROR naming your files.
- `git status --short | tail -30` expect clean after commits.

## 7. Acceptance

- [ ] Runbook has all 8 sections; every command is in its own block.
- [ ] No AWS login is needed in any rebuild step.
- [ ] The two-servers guard appears before the rebuild steps.
- [ ] Lint shows no ERROR for the two files.
- [ ] Two commits on the branch, nothing pushed.

## 8. Stop and ask

Stop and write the report as `blocked` if a fact in section 2 cannot be confirmed by grep, the lint fails twice, you reach 25 tool calls, or you would need a file outside section 3.

## 9. Report

`docs/tasks/1135-report.md` (600 tokens at most): files changed, each command with last 5 lines, section 7 ticked, deviations. End with "Files that should link to the runbook (orchestrator adds the links)": `docs/LIGHTSAIL.md` (rebuild section), `docs/OPERATIONS.md` (backup section), `docs/context/status.md`, `AGENTS.md` routing "Deploy, server, backups" row.
