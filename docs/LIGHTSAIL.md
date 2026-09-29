# AWS Lightsail deployment (Docker)

**Production** for UbyHost runs here (e.g. **ubyhost.com**). Use **Render
`ubyhost-staging`** only for mock staging — see [DEPLOYMENT.md](DEPLOYMENT.md).

Lightsail gives you Docker Compose, HTTPS (Caddy), and a persistent SQLite volume
on a small Frankfurt VM.

## Recommended Lightsail plan

| Your scale | Plan | Price (IPv4) | RAM |
|------------|------|--------------|-----|
| **~10 properties, busy weeks** | **Micro** | **$7/mo** | 1 GB |
| Growing toward 25+ properties | Small | $12/mo | 2 GB |
| **Not supported** | Nano | $5/mo | 512 MB — the app container has `mem_limit: 768m` |

Use **Frankfurt (`eu-central-1`)** or your nearest EU region. Enable the **static
IP** (included). Do **not** buy Lightsail managed MySQL — UbyHost uses SQLite on
disk.

**Recommended domain setup:** register on **Cloudflare** (or point `.cz`
nameservers there) and follow **[CLOUDFLARE.md](CLOUDFLARE.md)** for proxied DNS,
origin TLS, and `CLOUDFLARE_PROXY=1` in `.env`.

## Architecture

```
Internet → :443 Caddy (auto TLS) → ubyhost:8080 (FastAPI)
                                      ↓
                              volume: ubyhost-data
                              (ubyhost.db, photos, backups)
```

## One-time setup

### 1. Create the instance

1. [Lightsail](https://lightsail.aws.amazon.com/) → **Create instance**
2. **Linux / Ubuntu 24.04**
3. **Micro** (1 GB) or Small (2 GB)
4. Attach a **static IP**
5. Open firewall: **HTTP 80**, **HTTPS 443**, **SSH**

### 2. Point DNS

Create a **proxied** A record in Cloudflare → static IP (see
**[CLOUDFLARE.md](CLOUDFLARE.md)**). Wait for DNS to propagate before the first
deploy.

### 3. Bootstrap the server

SSH in, then:

```bash
sudo bash deploy/lightsail/scripts/setup-server.sh
```

Or clone first:

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/jsfpechar-ops/jsfpecharoperations.git /opt/ubyhost
cd /opt/ubyhost
sudo bash deploy/lightsail/scripts/setup-server.sh
```

Log out and back in so Docker group membership applies (if using `ubuntu` user).

### 4. Configure environment

```bash
cd /opt/ubyhost/deploy/lightsail
cp .env.example .env
nano .env
```

Required in `.env`:

| Variable | Example |
|----------|---------|
| `UBYHOST_DOMAIN` | `ubyhost.yourdomain.cz` |
| `ACME_EMAIL` | `you@yourdomain.cz` |
| `UBYHOST_PUBLIC_BASE_URL` | `https://ubyhost.yourdomain.cz` |
| `UBYHOST_ADMIN_PASSWORD` | long random password |
| `UBYHOST_UBYPORT_ENV` | `test` (then `prod` after validation) |

`deploy.sh` generates `UBYHOST_SECRET_KEY` automatically if left empty.

### 5. Deploy

```bash
chmod +x scripts/*.sh
./scripts/deploy.sh
```

Verify:

```bash
./scripts/status.sh
curl -sS "https://YOUR_DOMAIN/healthz"
```

Sign in, complete the [production checklist](PRODUCTION_CHECKLIST.md), and enter
UbyPort credentials per property.

## Environment variables (what breaks if wrong)

Filled from `deploy/lightsail/.env.example`. `deploy.sh` runs `scripts/preflight.sh`
before the image build.

| Variable | Required | If missing / wrong |
|----------|----------|--------------------|
| `UBYHOST_DOMAIN` | yes | Caddy TLS host wrong; preflight fails |
| `ACME_EMAIL` | yes | Let's Encrypt contact / Caddy env empty |
| `UBYHOST_PUBLIC_BASE_URL` | yes | Guest permalinks and cookies point at the wrong origin |
| `UBYHOST_ADMIN_PASSWORD` | yes | Bootstrap admin cannot log in (or a one-time file is written in `/data`) |
| `UBYHOST_DEPLOYMENT` | yes (`production`) | Settings / logs show the wrong tier; `prod` UbyPort is refused unless this is `production` |
| `UBYHOST_UBYPORT_ENV` | yes (`test` then `prod`) | `mock` reports nowhere; `prod` on Render or without `production` **refuses to start** |
| `UBYHOST_SECRET_KEY` | auto-generated if empty | Must be ≥32 chars. **Losing it** invalidates sessions and encrypted UBY-WS passwords |
| `CLOUDFLARE_PROXY` | `1` on ubyhost.com | `1` without origin certs → deploy abort; `0` uses Let's Encrypt (needs grey-cloud DNS) |
| `UBYHOST_GUEST_PIN` | `1` | `0` on production: preflight **warns**; permalinks are open to anyone with the URL |
| `UBYHOST_ENABLE_SCHEDULER` | `1` | `0`: no iCal poll, no auto-submit sweep, no deadline watch, no 12h photo purge |
| `TURNSTILE_SECRET` | production login | Host login bot check disabled if empty |
| `UBYHOST_ICAL_ALLOW_PRIVATE` | must stay unset/`0` | Preflight **fails** on production (SSRF) |

`UBYHOST_DATA_DIR` is forced to `/data` by Compose. Do not point it at the git tree.

## Data on the Docker volume `ubyhost-data`

Mounted at `/data` inside `ubyhost` (uid **10001**):

| Path | What |
|------|------|
| `/data/ubyhost.db` | SQLite (stays, guests, submissions, encrypted WS passwords) |
| `/data/ubyhost.db-wal` / `-shm` | WAL files while the app is running — use `sqlite3 .backup`, not a raw `cp` of a live DB |
| `/data/secret_key` | Fallback signing/encryption key if env `UBYHOST_SECRET_KEY` is empty |
| `/data/initial_admin_credentials` | One-time bootstrap password if env password was empty |
| `/data/passport_photos/` | Temporary ID uploads (not included in `backup_data.sh`; they expire after verification / sweep) |
| `/data/backups/<stamp>/` | Snapshots are age-encrypted (`ubyhost-backup.tar.age`) with time-based retention; see `deploy/lightsail/README.md` |

Volume is **not** replaced on `./scripts/deploy.sh`. Code updates only.

## Deploy path and failure modes

```
GitHub Actions (optional)
  workflow Deploy production
    → SSH ubuntu@LIGHTSAIL_HOST
    → git fetch + git reset --hard origin/main
    → cd deploy/lightsail && ./scripts/deploy.sh
         → preflight.sh
         → docker compose build --pull
         → docker compose up -d
         → internal /healthz
         → smoke-remote.sh (public; warnings only if DNS/TLS fail)
Caddy :443 → ubyhost:8080
```

| Failure | What you see | Fix |
|---------|--------------|-----|
| No git at `/opt/ubyhost` | CI bootstraps if the lightsail layout exists; otherwise aborts | Clone as in setup, or let CI bootstrap |
| Wrong branch / stale tree | `git reset --hard origin/main` **discards local edits** | Keep `.env` and `caddy/certs/` outside git (already gitignored) |
| Stale image | Compose builds `ubyhost:local` each deploy with `--pull` of base images | If a layer looks cached wrongly: `docker compose build --no-cache` |
| Automatic deploy after every green CI | Not offered — deploys never run on their own | Production deploys are manual: Actions → Deploy production → Run workflow, type DEPLOY |
| App starts but public HTTPS fails | Internal healthz OK; `smoke-remote.sh` warns | Cloudflare Full (strict), origin certs, Lightsail :443 |

Rollback **code** (data stays):

```bash
cd /opt/ubyhost
git fetch origin main
git reset --hard <known-good-sha>
cd deploy/lightsail && ./scripts/deploy.sh
```

Rollback **UbyPort target** (test ↔ prod): edit `.env` `UBYHOST_UBYPORT_ENV`, then `./scripts/deploy.sh`.

## Day-to-day commands

All from `deploy/lightsail/`:

| Command | Purpose |
|---------|---------|
| `./scripts/preflight.sh` | Validate `.env` without building |
| `./scripts/deploy.sh` | Rebuild image and restart after `git pull` |
| `./scripts/status.sh` | Containers, **internal** env (`deployment` / `ubyport_env`), public healthz, `df` |
| `./scripts/smoke-remote.sh` | Curl `/healthz`, `/login`, `/legal`, `/privacy` |
| `./scripts/logs.sh` | Tail all logs |
| `./scripts/logs.sh ubyhost` | App logs only |
| `./scripts/backup.sh` | Age-encrypted snapshot with time-based retention |
| `./scripts/restore.sh <stamp>` | Stop app, replace DB from a volume snapshot, start, wait for health |
| `./scripts/backup-gdrive.sh` | Snapshot + rclone copy newest folder to Google Drive |

Public `GET /healthz` in **production** returns `status`, `version`, `data_dir_writable` only (no env labels). Confirm `ubyport_env` with `./scripts/status.sh` or Settings.

### Automatic backups

Daily on-volume snapshot (03:00 UTC):

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh >> /var/log/ubyhost-backup.log 2>&1") | crontab -
```

Weekly off-site (Sunday 04:00 UTC) after `rclone config` remote **`gdrive`**:

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh >> /var/log/ubyhost-gdrive.log 2>&1") | crontab -
```

`backup.sh` runs `sqlite3 … '.backup'` **inside the running container**, so a concurrent write is snapshotted consistently (SQLite hot backup). A raw `cp ubyhost.db` while the app is up can capture a torn file — do not do that.

**Retention:** snapshots are age-encrypted (`ubyhost-backup.tar.age`) with time-based retention; see `deploy/lightsail/README.md`. Older points exist only if you copied them off-site (Drive/S3) **before** they aged out. Drive uploads do not prune.

Passport photos are **not** in the DB backup. After restore, unverified uploads may be missing; hosts re-check IDs if needed.

## Restore runbook (same instance)

1. `AGE_IDENTITY_FILE=/path/on/host ./scripts/restore.sh <stamp>` — the age identity must be on the host, never on the volume.
2. List stamps: `docker compose exec ubyhost ls -1 /data/backups | sort -r`
3. `cd /opt/ubyhost/deploy/lightsail && ./scripts/restore.sh 20260915T030000Z`
4. Type `yes`. The script stops `ubyhost`, copies `ubyhost.db` (+ `secret_key` if present), `chown 10001:10001`, starts the service, waits for `/healthz`.
5. Sign in. Open **one stay** and **Reports** — confirm guests and a known Doručenka still exist.
6. If login fails after restore, `UBYHOST_SECRET_KEY` in `.env` does not match the restored `secret_key` / Fernet key. Set `.env` to the key that was in force when the backup was taken, then `./scripts/deploy.sh`.

### Restore onto a **new** Lightsail instance

1. Create instance, static IP, firewall 22/80/443. Run `setup-server.sh`. Clone repo to `/opt/ubyhost`.
2. Copy `.env` (do not commit it) and `caddy/certs/origin*.pem` from the old host or a secrets store.
3. `./scripts/deploy.sh` once so volume `ubyhost-data` exists.
4. `docker compose stop ubyhost`
5. Place backup files on the host (from Drive): `ubyhost.db` and `secret_key`.

```bash
docker run --rm -v ubyhost-data:/data -v "$PWD/restore-in":/backup alpine \
  sh -c 'cp /backup/ubyhost.db /data/ubyhost.db
         cp /backup/secret_key /data/secret_key
         chown 10001:10001 /data/ubyhost.db /data/secret_key
         chmod 600 /data/ubyhost.db /data/secret_key'
```

6. If `UBYHOST_SECRET_KEY` is empty and `/data/secret_key` exists, deploy.sh uses the file. Never replace the key on a server that already has data.
7. `./scripts/deploy.sh` then `./scripts/status.sh` and a login test.
8. Point Cloudflare A record at the **new** static IP. Keep Full (strict).

## Scheduler

`UBYHOST_ENABLE_SCHEDULER=1` (default) starts APScheduler:

| Job | Interval |
|-----|----------|
| iCal sync | `UBYHOST_ICAL_POLL_MINUTES` (60) |
| UbyPort submit sweep | `UBYHOST_SUBMIT_SWEEP_MINUTES` (10) |
| Deadline alerts | 30 min |
| Guest e-mail (`mail`) | 5 min |
| Stale passport photo purge | 12 h |

If you deploy with the scheduler **off**, calendars and automatic sends freeze until you set `1` and redeploy. Manual **Submit** still works. CI/smoke sets the scheduler off on purpose.

## Disk, logs, photos

Micro is **1 GB RAM / small root disk**. Watch:

```bash
df -h
docker system df
docker compose exec ubyhost du -sh /data /data/passport_photos /data/backups
```

Photos grow until hosts verify IDs or the 30-day stale sweep runs. Snapshots are age-encrypted with time-based retention; see `deploy/lightsail/README.md`. Docker logs: `docker compose logs --since 24h ubyhost`. Install `/etc/logrotate.d/ubyhost` as printed by `setup-server.sh` for `/var/log/ubyhost-*.log`.

Lightsail **snapshots** of the whole instance are a useful extra (not a substitute for `backup.sh` + Drive).

## Updating after code changes

```bash
cd /opt/ubyhost
git pull origin main
cd deploy/lightsail
./scripts/deploy.sh
```

The database volume is **not** replaced on deploy — only application code updates.

### Deploy from GitHub Actions

Production deploys are manual: Actions → Deploy production → Run workflow, type DEPLOY.

Workflow **Deploy production** pins the run to the current `main` revision, verifies CI is green for it, then SSHs and runs `git reset --hard` + `./scripts/deploy.sh`.

| Secret | Purpose |
|--------|---------|
| `LIGHTSAIL_HOST` | Static IP |
| `LIGHTSAIL_SSH_PRIVATE_KEY` | Ubuntu user key |

Without the host/key secrets, the job skips.

## Migrating from Render

1. On Render: download `ubyhost.db` from the persistent disk (Shell or backup).
2. On Lightsail: deploy once so the volume exists.
3. Stop the stack: `docker compose down`
4. Copy the database into the volume:

   ```bash
   docker run --rm -v ubyhost-data:/data -v "$PWD":/backup alpine \
     sh -c 'cp /backup/ubyhost.db /data/ubyhost.db && chown 10001:10001 /data/ubyhost.db'
   ```

5. Copy `secret_key` from Render `data/` too if you have it (keeps encrypted
   UbyPort passwords working). Otherwise re-enter UbyPort logins per apartment.
6. `./scripts/deploy.sh`
7. Set the **same** `UBYHOST_SECRET_KEY` in `.env` as on Render if you copied
   `secret_key`.

## Go-live on UbyPort

Do **not** set `prod` until the test-submission report in [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) is signed.

1. `.env`: `UBYHOST_DEPLOYMENT=production`, `UBYHOST_UBYPORT_ENV=test`.
2. Complete one controlled stay on the **test** SOAP endpoint; archive Doručenka.
3. Change to `UBYHOST_UBYPORT_ENV=prod` and run `./scripts/deploy.sh`.
4. Settings must show the red **prod** badge. Submit one real guest batch.

If a wrong **prod** batch went out: do not spam retries. Download Doručenka, follow [error mapping](PRODUCTION_CHECKLIST.md#ubyport-errors-host-actions). Contact Foreign Police (`reguby@pcr.cz` / data box `ybndqw9`) only if the register holds incorrect personal data you cannot correct in-app. Roll the app back to `test` only to **stop further live sends**; that does not un-report what already succeeded.

## Scaling the instance

When you outgrow 1 GB (heavy PDF ZIPs, 20+ properties):

1. Lightsail → instance → **Change plan** → Small (2 GB).
2. Reboot if prompted — the Docker volume survives.

No code changes required.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **HTTPS hangs**; `curl http://YOUR_IP/healthz` returns **308** but `https://your-host/healthz` never connects | Open **HTTPS (443)** in the **Lightsail** instance **Networking → IPv4 firewall** (not only `ufw` on the VM). Keep **HTTP (80)** for Let's Encrypt. |
| Caddy / SSL errors | Cloudflare: Full (strict) + origin certs; or `CLOUDFLARE_PROXY=0` for Let's Encrypt |
| Need to know `ubyport_env` | Public `/healthz` omits it in production. Use `./scripts/status.sh` or Settings |
| `status.sh` shows `deployment=local` | Set `UBYHOST_DEPLOYMENT=production` in `.env`, redeploy |
| Out of memory | Upgrade to Small plan or export PDFs in smaller date ranges |
| Guest links wrong host | `UBYHOST_PUBLIC_BASE_URL` must match your HTTPS domain exactly |
| Container exits immediately | `UBYHOST_UBYPORT_ENV=prod` on Render-like env or without `production` — read `./scripts/logs.sh ubyhost` |

## Cost summary

| Item | Monthly |
|------|---------|
| Lightsail Micro (1 GB) | $7 |
| Static IP | included |
| Managed database | **not needed** |
| **Typical total** | **~$7–9** (optional snapshots ~$1) |

Compare with Render Starter (~$7 + disk) — Lightsail Micro gives **2× RAM** and
**2 burstable vCPUs** for similar money.
