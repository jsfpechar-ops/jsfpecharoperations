# Portable disaster recovery

Owner goal (2026-11-12): easy to move off AWS if Lightsail dies. One box, a current off-AWS backup, a tested rebuild.

## Goal

If AWS is gone, a fresh EU Ubuntu box (Hetzner as example, not a decision) runs UbyHost within hours, with the data at most 7 days old, and no AWS login needed.

## What exists today

- Daily `pg_dump`, age-encrypted, in `/data/backups/<stamp>/` inside the app volume (`deploy/lightsail/scripts/backup.sh:28-60`). Cron 03:00 (`setup-server.sh:73`).
- Encryption: age public recipient in `.env`; private identity in the password manager plus one offline copy, never on the server (`docs/OPERATIONS.md:596-615`).
- Drive copy: weekly, Sunday 04:00 UTC, optional cron, `*.age` only, 30-day retention (`backup-gdrive.sh:53-58`, `setup-server.sh:75`). S3 copy: daily, `backup-s3.sh`.
- WAL-G: S3 only, 7 days, key `WALG_LIBSODIUM_KEY` (separate from age) (`OPERATIONS.md:652-655`).
- Restore: `pg-restore.sh <stamp>` reads the dump from the app volume, not from a file (`pg-restore.sh:44-55`). Rebuild steps and a quarterly drill: `docs/LIGHTSAIL.md:286-310`.
- Cloudflare proxies the site (`CLOUDFLARE_PROXY=1`, `docs/CLOUDFLARE.md`).

## Gaps (most important first)

1. Off-AWS data can be 7 days old (Drive is weekly). Whether the Sunday cron is installed in production is unverified.
2. `pg-restore.sh` needs the dump inside the volume. From a Drive file there is no script path: a restore-from-file option is needed.
3. Drive upload token lives in rclone config on the server; not in the offline copy. Needs a note or a re-auth step.
4. The `.env`, `UBYHOST_SECRET_KEY` and Cloudflare origin certs must exist offline. Not checked anywhere.
5. `docs/runbook.md:37` cites `restore-drill.yml`; that workflow is not in `.github/workflows/`. The only drill is the manual one in LIGHTSAIL.md; no drill has been timed or run on a non-AWS box.
6. No guard against two servers filing. No "we're down" page (CLOUDFLARE.md has none).
7. No single provider-neutral runbook; steps are split across LIGHTSAIL.md, OPERATIONS.md, README.

AWS dependencies and what happens in an outage:

| Dependency | During the outage | Fallback |
|---|---|---|
| SES mail (`App/app/mail.py`, `UBYHOST_MAIL_BACKEND=ses`) | Mail queues in the outbox and waits | Outage is by definition a rebuild: switch to another SMTP provider only if mail is urgent (later brief); otherwise keep SES (account stays valid) |
| S3 (dump copy, WAL-G) | Lost with AWS | Drive copy is the source; point WAL-G elsewhere later |
| Lightsail snapshots | Lost with AWS | Not needed; rebuild from repo, dump, `.env` |
| Static IP, `eu-central-1` wording in docs | Gone | New IP in Cloudflare A record |
| UbyPort (police) | Not AWS, unaffected | Filing resumes on the new box |

## Steps

| # | Step | Size | Who | Depends on |
|---|---|---|---|---|
| 1 | Runbook `docs/DISASTER_RECOVERY.md` (brief 1133) | M | Haiku brief | none |
| 2 | Check Drive cron runs; list what is in Drive; confirm age key opens a Drive file | S | owner | none |
| 3 | `pg-restore.sh` option to restore from a local `.age` file (no volume stamp, no AWS) | M | Haiku brief | 1 |
| 4 | Drive copy daily instead of weekly (cron line change, doc) | S | Haiku brief + owner | 2 |
| 5 | Cloudflare "we're down" page (static, Worker or custom error page) | S | Haiku brief + owner | 1 |
| 6 | Filing guard: runbook step plus a check in `deploy.sh`/preflight that warns when `submit` is in `UBYHOST_GO_JOB_KINDS` on a restored box | M | Haiku brief | 3 |
| 7 | Choose EU provider; add to `/subprocessors` register and ROPA | S | owner + lawyer | none |
| 8 | Timed drill on a throwaway non-AWS box; record minutes in status | M | owner, repeat every 3 months with the restore drill | 3, 7 |
| 9 | Link runbook from LIGHTSAIL.md, OPERATIONS.md, status, AGENTS routing | S | orchestrator | 1 |

## Owner decisions needed

1. Move the Drive copy to daily? Recommend yes (loss from 7 days to 1).
2. Which EU provider to name in the register? Recommend Hetzner (Germany/Finland), pick before any drill.
3. Offline pack (age identity, `.env`, secret key, origin certs, rclone config) location and who else can open it? Recommend password manager plus one printed or USB copy.
4. Stop the old server first, always? Recommend yes: stop it, or remove `submit` from `UBYHOST_GO_JOB_KINDS`, before the new box files. Filing deadline is 3 working days, so a day of downtime is fine.
5. Last fallback: file by hand in the police portal. Recommend the runbook says so.

## Not doing

- Hot standby: two live copies could both file guests with the police (rule 1).
- Vercel: the app is a Docker stack with Postgres and a worker; it does not fit.
- Separate Postgres server: more to run and more to fail; one box with dumps is enough.
- MotherDuck: analytics store, no help for recovery.
