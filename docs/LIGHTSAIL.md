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
| Absolute minimum (tight) | Nano | $5/mo | 512 MB |

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

## Day-to-day commands

All from `deploy/lightsail/`:

| Command | Purpose |
|---------|---------|
| `./scripts/deploy.sh` | Rebuild image and restart after `git pull` |
| `./scripts/status.sh` | Container status + public healthz |
| `./scripts/logs.sh` | Tail all logs |
| `./scripts/logs.sh ubyhost` | App logs only |
| `./scripts/backup.sh` | SQLite snapshot (keeps last 10 on disk) |

### Automatic backups

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh >> /var/log/ubyhost-backup.log 2>&1") | crontab -
```

Copy `ubyhost-data` backups off the server weekly (S3, Google Drive, etc.).

## Updating after code changes

```bash
cd /opt/ubyhost
git pull origin main
cd deploy/lightsail
./scripts/deploy.sh
```

The database volume is **not** replaced on deploy — only application code updates.

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

1. Start with `UBYHOST_UBYPORT_ENV=test` in `.env`.
2. Submit one real stay; confirm Doručenka in Reports.
3. Change to `UBYHOST_UBYPORT_ENV=prod` and run `./scripts/deploy.sh`.

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
| `healthz` shows `deployment: local` | Set `UBYHOST_DEPLOYMENT=production` in `.env`, redeploy |
| Out of memory | Upgrade to Small plan or export PDFs in smaller date ranges |
| Guest links wrong host | `UBYHOST_PUBLIC_BASE_URL` must match your HTTPS domain exactly |

## Cost summary

| Item | Monthly |
|------|---------|
| Lightsail Micro (1 GB) | $7 |
| Static IP | included |
| Managed database | **not needed** |
| **Typical total** | **~$7–9** (optional snapshots ~$1) |

Compare with Render Starter (~$7 + disk) — Lightsail Micro gives **2× RAM** and
**2 burstable vCPUs** for similar money.
