# Disaster recovery runbook

Rebuild UbyHost on a new EU Ubuntu server from the Google Drive backup. No AWS login is needed. Hetzner is the example provider; any EU provider works the same way. Background: [LIGHTSAIL](LIGHTSAIL.md) (restore section), [OPERATIONS](OPERATIONS.md) (backup section). Commands run in `/opt/ubyhost/deploy/lightsail` unless a step says otherwise.

## When to use this

Use it when the AWS account or the Lightsail server has been unreachable for more than a few hours. Filing deadline: 3 working days. If the rebuild cannot finish in time, the last fallback is filing by hand in the police portal.

## Before you start: the offline pack

Keep these in the password manager and one offline copy. None of them lives on the server. Values are never written into any file.

1. The age identity file (backup decryption key).
2. The `.env` file from the production server.
3. The value of `UBYHOST_SECRET_KEY`.
4. The origin certificates `caddy/certs/origin*.pem`.
5. Access to the Google account that owns the rclone `gdrive` remote.
6. The Cloudflare login.
7. The domain registrar login.

If the pack is missing, stop here and use the fallback in "When to use this".

## Two servers never file at once

Before any rebuild step, make sure the old server cannot file.

1. On the **old** server, stop it: `docker compose stop`. Or, if it must keep running, remove `submit` from `UBYHOST_GO_JOB_KINDS` in its `.env` and run `./scripts/deploy.sh`.
2. On the **new** box, check that `submit` is in neither variable:

```bash
grep -n 'UBYHOST_GO_JOB_KINDS\|UBYHOST_JOB_QUEUE_KINDS' .env
```

3. Leave it that way until the owner is sure the old server is off.
4. When sure, add `submit` to both variables on the new box, then run `./scripts/deploy.sh`.

## Rebuild on a new box

1. Create an EU Ubuntu server with ports 22, 80 and 443 open. In the Hetzner Cloud console: Servers, Add server, Location in Germany or Finland, Ubuntu LTS, then add the firewall rules. Note the new public IP as `<NEW_IP>`.
2. Log in over SSH and clone the repo:

```bash
sudo git clone <REPO_URL> /opt/ubyhost
cd /opt/ubyhost/deploy/lightsail
```

3. Run the server setup:

```bash
./scripts/setup-server.sh
```

4. Copy `.env` into `/opt/ubyhost/deploy/lightsail/.env` and the origin certificates into `caddy/certs/`. Set `UBYHOST_SECRET_KEY` in `.env` **before the first deploy**. Without it the restored data cannot be decrypted.
5. Install the tools:

```bash
sudo apt-get install -y rclone age
```

6. Configure the Drive remote. Name it `gdrive`, choose Google Drive, and sign in with the owner's Google account:

```bash
rclone config
```

7. List the backup folders and note the newest `<stamp>`:

```bash
rclone lsd gdrive:UbyHost-backups
```

8. Download the dump into the current folder (the folder must be `/opt/ubyhost/deploy/lightsail`):

```bash
rclone copy gdrive:UbyHost-backups/<stamp> ./restore-in
```

9. Copy the age identity file from the pack to `/root/ubyhost-backup.agekey` (chmod 600). Never place it inside the volume.
10. Start the stack so the volume exists:

```bash
./scripts/deploy.sh
```

11. Place the dump in the volume (workaround until brief for a restore-from-file option):

```bash
docker run --rm -v ubyhost-data:/data -v "$PWD/restore-in":/in alpine sh -c 'mkdir -p /data/backups/<stamp> && cp /in/ubyhost-pg.dump.age /data/backups/<stamp>/'
```

12. Restore the database. The script refuses while `.env` contains `UBYHOST_DB=`:

```bash
RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh <stamp>
```

13. Delete the identity file from the server:

```bash
sudo shred -u /root/ubyhost-backup.agekey
```

14. Check the stack:

```bash
./scripts/status.sh
```

15. Open one stay and one Doručenka in a browser, with a hosts-file entry that points the domain to `<NEW_IP>`. Command-line check:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' --resolve <DOMAIN>:443:<NEW_IP> https://<DOMAIN>/
```

If curl reports a certificate error, use the browser check. Never add `-k`.

## Point Cloudflare at the new box

1. In Cloudflare, DNS: change the A record for the domain to `<NEW_IP>`. Keep it proxied (orange cloud).
2. SSL/TLS: keep Full (strict).
3. Check that `.env` has `CLOUDFLARE_PROXY=1`.

## What AWS gave us and what happens without it

| AWS service | Without it | Action |
|---|---|---|
| SES mail | Outbox queues mail and waits until SES is reachable | Wait. An SMTP switch is a later brief. |
| S3 copies and WAL-G | Gone. Drive is the only source. Point-in-time recovery is not available after a rebuild until it is set up again. | Re-set WAL-G later, or accept the daily Drive copy. |
| Lightsail snapshots | Not needed; the Drive backup replaces them | None |
| Static IP | New IP | Update Cloudflare (above) |
| UbyPort | Not on AWS; unaffected | None |

The data may be up to 1 day old, because the Drive copy is daily (04:00 UTC). Guests filed since the last backup may need checking against police receipts.

## After the move

1. Re-enable the cron lines: `crontab -e`, then add the daily backup at 03:00 (`backup.sh`) and the daily Drive copy at 04:00 (`backup-gdrive.sh`).
2. Run the backup once: `./scripts/backup.sh`.
3. Owner or lawyer: add the new provider to the `/subprocessors` register and to `docs/privacy/ROPA.md`. The provider must be in the EU. Do this before real guest data moves if time allows, otherwise the same day.

## Drill

Run this every 3 months with the restore drill.

1. Start a timer. Run the rebuild steps on a throwaway server. Skip the Cloudflare step.
2. Check the stay and the Doručenka with the browser check.
3. Stop the timer. Write the minutes in [status](context/status.md).
4. Delete the throwaway server.
