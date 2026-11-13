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

Before any rebuild step, make sure the old server cannot file. Removing `submit` from the job lists is not enough: with `submit` in neither list, the Python worker files guests itself. Only a stopped server, or `UBYHOST_ENABLE_SCHEDULER=0`, stops scheduled filing; only a stopped server stops all filing.

1. On the **old** server, stop it: `docker compose stop`. Or, if it must keep running, set `UBYHOST_ENABLE_SCHEDULER=0` in its `.env`, remove `submit` from `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS`, and run `./scripts/deploy.sh`.
2. On the **new** box, before the first deploy (rebuild step 4), turn scheduled filing off in `.env`: set `UBYHOST_ENABLE_SCHEDULER=0` and give both variables a value without `submit` (for example `UBYHOST_GO_JOB_KINDS=ical,push`). Keep both lines in `.env`, never delete them: without the line, a value from the shell reaches the containers. Check `.env`, and check that the shell exports neither variable (the second command prints nothing):

```bash
grep -n 'UBYHOST_ENABLE_SCHEDULER\|UBYHOST_GO_JOB_KINDS\|UBYHOST_JOB_QUEUE_KINDS' .env
env | grep 'UBYHOST_GO_JOB_KINDS\|UBYHOST_JOB_QUEUE_KINDS'
```

3. The restore (rebuild step 12) checks that scheduled filing is off, then writes the marker file `.restored-box` next to `.env`. While it exists, `pg-restore.sh --file` and `./scripts/deploy.sh` stop with `RESTORED BOX` if scheduled filing is on. Leave filing off until the owner is sure the old server is off. The guard only proves that scheduled filing is off; apartments in immediate mode still file when a guest or host saves. So keep Cloudflare pointed away from the new box (the "we're down" page stays on) until the marker is removed.
4. When sure (the old server is stopped, or deleted in its provider console), acknowledge it on the new box:

```bash
rm .restored-box
```

5. Point Cloudflare at the new box (that section, steps 1 to 4). Only then turn filing back on: in `.env` set `UBYHOST_ENABLE_SCHEDULER=1` and add `submit` back to both variables (as on the old server). Then deploy. This is the first deploy whose public check can pass (rebuild step 10):

```bash
./scripts/deploy.sh
```

Override for one run, only when the owner knows the old server cannot file and the marker must stay: prefix it on that one command, `UBYHOST_FILING_GUARD_OVERRIDE=1 ./scripts/deploy.sh`. Never `export` it and never put it in `.env` (the guard refuses `.env`).

## Show the "we're down" page

Use this while the server is gone and the rebuild runs, so hosts and guests see a clear message instead of a Cloudflare error. The page is the Worker in `deploy/cloudflare/down-page-worker.js`. It never contacts any server. Steps 1 and 2 can be done ahead of time and kept.

1. In Cloudflare, open Workers & Pages, Create, Worker. Name it `ubyhost-down` and click Deploy.
2. Click Edit code, delete the sample code, paste the whole content of `deploy/cloudflare/down-page-worker.js`, and click Deploy. The Free plan is enough.
3. Open the Worker, Settings, Domains & Routes, Add, Route. Zone `ubyhost.com`, route `ubyhost.com/*`. Repeat with `www.ubyhost.com/*` if that host exists.
4. Open the site in a private window and check that the "we're down" page shows.
5. Keep working on the rebuild. The `curl --resolve` checks below bypass Cloudflare, so they still reach the new box.

The page is turned off in "Point Cloudflare at the new box", step 4.

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

4. Copy `.env` into `/opt/ubyhost/deploy/lightsail/.env` and the origin certificates into `caddy/certs/`. Set `UBYHOST_SECRET_KEY` in `.env` **before the first deploy**. Without it the restored data cannot be decrypted. Turn automatic filing off in the same `.env` (see "Two servers never file at once", step 2).
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

Until Cloudflare points at the new box, every `./scripts/deploy.sh` here ends with `The public site does not answer after the restart.` and `Rolling back`, and exits 1. That is expected: its public `/healthz` check goes through Cloudflare and gets the "we're down" page, not this box. The containers are already up with the current `.env` (the rollback starts them again). Check it: the first command shows `ubyhost`, `worker`, `postgres` and `caddy` as `Up`; the second prints `ok`. Any other error is real: stop and read it.

```bash
docker compose ps
docker compose exec -T ubyhost python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3); print('ok')"
```

11. The dump from step 8 is already on the server in `restore-in`. Keep it outside the volume: the restore reads it straight from the host and writes no plaintext file. If you downloaded it elsewhere, copy it to the server first (any path ending in `.age` works).

12. Restore the database from that file. The script refuses while `.env` contains `UBYHOST_DB=`, and while scheduled filing is on (then it changes nothing). Otherwise it writes the marker `.restored-box` (see "Two servers never file at once"), stops the app, the worker and the Go service, restores, and starts every service again with the current `.env`:

```bash
RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh --file ./restore-in/ubyhost-pg.dump.age
```

If it stops with `RESTORED BOX`: fix `.env` ("Two servers never file at once", step 2), run `./scripts/deploy.sh` so the running containers get the new `.env` (it ends with `Rolling back`, as in step 10), then run the restore command again.

13. Delete the identity file from the server:

```bash
sudo shred -u /root/ubyhost-backup.agekey
```

14. Check the stack:

```bash
./scripts/status.sh
```

15. Open one stay and one Doručenka in a browser, with a hosts-file entry that points the domain to `<NEW_IP>`. Look only: never save anything while `.restored-box` exists. In immediate mode a save files the guest with the police, and the old server may file the same guest. Command-line check:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' --resolve <DOMAIN>:443:<NEW_IP> https://<DOMAIN>/
```

If curl reports a certificate error, use the browser check. Never add `-k`.

## Point Cloudflare at the new box

Only after `.restored-box` is removed ("Two servers never file at once", step 4): until then no guest or host may reach the new box.

1. In Cloudflare, DNS: change the A record for the domain to `<NEW_IP>`. Keep it proxied (orange cloud).
2. SSL/TLS: keep Full (strict).
3. Check that `.env` has `CLOUDFLARE_PROXY=1`.
4. Turn off the "we're down" page: in Cloudflare, Workers & Pages, `ubyhost-down`, Settings, Domains & Routes, delete the route(s). Then open the site in a private window and check the normal start page loads.
5. Turn filing back on and deploy ("Two servers never file at once", step 5). This deploy must end without `Rolling back`.

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
2. Check the stay and the Doručenka with the browser check (rebuild step 15: look only, never save).
3. Stop the timer. Write the minutes in [status](context/status.md).
4. Delete the throwaway server.
