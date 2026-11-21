# PROMPT — provision the UbyHost Lightsail STAGING server (paste this whole file to the SSH AI)

You are an executor agent with SSH access to one fresh AWS Lightsail instance. Set up
the UbyHost staging server exactly as below: the same production stack (Caddy HTTPS,
PostgreSQL 16 on a local socket, the Go app, the mock UbyPort), but on a small bundle
with monthly local backups only and no off-site copies. The repo is already cloned
at `/opt/ubyhost` (clone it first if not). Read `deploy/lightsail/README.md` ("Staging
server (Step 0)"), `docs/LIGHTSAIL.md`, and `deploy/lightsail/scripts/preflight.sh`
before changing anything.

## Inputs the owner gives you (fill the placeholders; nothing else)

- `STAGING_DOMAIN` — e.g. `staging.example.com` (its own DNS name, never the prod domain)
- `ACME_EMAIL` — for Let's Encrypt if not using Cloudflare
- `STAGING_STATIC_IP` — the static IP attached to the instance
- `OWNER_EMAIL` — admin e-mail for the staging instance
- `STAGING_AGE_RECIPIENT` — optional public `age1...` recipient for encrypted snapshots
- Cloudflare choice: proxied DNS + origin certs, or plain ACME

## Hard rules (violating any of these fails the task)

1. Never print, log, commit, or paste a secret: no `.env` values, no SSH keys, no age
   private identity, no tokens. Reference secrets by variable name only. `.env` stays
   `chmod 600` and untracked (`deploy/lightsail/.gitignore` covers it).
2. Open only ports 22, 80, 443 (ufw). Never disable the firewall, never add other
   public ports, never set up tunnels or reverse proxies.
3. PostgreSQL must keep `network_mode: none` in `docker-compose.yml` — never expose
   port 5432. Do not edit the compose file; everything is driven by `.env`.
4. On this instance `UBYHOST_DEPLOYMENT=staging`, always. Never set it to `production`.
   Never enable the `walg` or `monitoring` compose profiles here.
5. Staging never holds real guest data: never copy a production backup or database
   onto this server (staging data policy LD-10, `docs/DEPLOYMENT.md`).
6. The age private identity never goes on the server; only the public recipient in `.env`.
7. End every command you show with `| tail -30` (or `head -50`); never dump full logs.

## Step 1 — instance checklist (owner does the console part; you verify)

- Lightsail, region Frankfurt `eu-central-1`, **Linux / Ubuntu 24.04**, bundle
  **Micro (1 GB RAM, ~$7/mo)** — supported for staging via `UBYHOST_ALLOW_SMALL_HOST=1`
  (`preflight.sh` refuses < 1.7 GB without it; `docs/LIGHTSAIL.md` "Recommended plan").
  If the box OOMs later (`dmesg | grep -i oom`, `docker stats --no-stream`), the owner
  moves it to the Small 2 GB bundle — note this in your report. (Caveat: the postgres
  container's `mem_limit: 1g` is hardcoded in compose; caps are ceilings, real usage
  is far lower.)
- Attach a **static IP**; firewall: SSH 22, HTTP 80, HTTPS 443 only.
- **Automatic instance snapshots: OFF** (backups here are the monthly cron in step 7;
  the owner may take one manual instance snapshot on the 1st of each month instead).

## Step 2 — DNS

Create an A record `STAGING_DOMAIN` → `STAGING_STATIC_IP`. Preferred: Cloudflare,
proxied, SSL/TLS Full (strict), Authenticated Origin Pulls cert — then copy
`origin.pem` and `origin-key.pem` into `deploy/lightsail/caddy/certs/` and set
`CLOUDFLARE_PROXY=1` (see `docs/CLOUDFLARE.md`). Simpler alternative: plain
(unproxied) A record, `CLOUDFLARE_PROXY=0`, Caddy gets a Let's Encrypt cert via ACME
(`deploy.sh` picks `caddy/Caddyfile.acme` automatically). Wait for DNS before deploy.

## Step 3 — bootstrap the server

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/jsfpechar-ops/jsfpecharoperations.git /opt/ubyhost
cd /opt/ubyhost && git checkout main
sudo bash deploy/lightsail/scripts/setup-server.sh
```

Log out/in so the `ubuntu` user is in the `docker` group. Then, as root, cap the
journal (`docs/LIGHTSAIL.md` "Disk, logs, photos") and install
`/etc/logrotate.d/ubyhost` exactly as printed by `setup-server.sh`.

## Step 4 — write `deploy/lightsail/.env` (chmod 600)

Start from `.env.example`, then set the staging block (production-only requirements
age recipient / backup ping do NOT apply to staging; heartbeats stay empty):

```bash
UBYHOST_DEPLOYMENT=staging
UBYHOST_UBYPORT_ENV=mock
COMPOSE_PROFILES=staging
UBYHOST_MOCK_URL=http://mock-ubyport:8081/ws_uby/ws_uby.svc
UBYHOST_DOMAIN=STAGING_DOMAIN
ACME_EMAIL=ACME_EMAIL
UBYHOST_PUBLIC_BASE_URL=https://STAGING_DOMAIN
UBYHOST_ADMIN_EMAIL=OWNER_EMAIL
UBYHOST_BOOTSTRAP_ADMIN=1
UBYHOST_MAIL_BACKEND=console
UBYHOST_ALLOW_SMALL_HOST=1
UBYHOST_GO_MEM=128m
UBYHOST_CADDY_MEM=128m
UBYHOST_DATABASE_URL=postgresql://ubyhost@/ubyhost?host=/var/run/postgresql
UBYHOST_BACKUP_RETENTION_DAYS=370
# UBYHOST_BACKUP_AGE_RECIPIENT=STAGING_AGE_RECIPIENT   # recommended: keeps snapshots encrypted
# CLOUDFLARE_PROXY=1  + origin certs in caddy/certs/     # or 0 for ACME
# UBYHOST_TRUSTED_PROXY_CIDRS=172.16.0.0/12              # only when CLOUDFLARE_PROXY=1
```

Leave empty: `UBYHOST_SECRET_KEY` (deploy.sh generates it into `/data/secret_key`),
`UBYHOST_BACKUP_PING_URL`, all heartbeat URLs, SES keys, S3/Drive/rclone, `UBYHOST_PG_ARCHIVE`
(stays `off` — no walg here). Leave `TURNSTILE_SECRET` empty on staging. Do NOT add
`walg` or `monitoring` to `COMPOSE_PROFILES`.

## Step 5 — preflight and first deploy

```bash
cd /opt/ubyhost/deploy/lightsail
chmod +x scripts/*.sh
./scripts/preflight.sh | tail -30        # must end "Preflight OK (deployment=staging ...)"
./scripts/deploy.sh | tail -30
```

`deploy.sh` runs the mandatory pre-deploy backup, applies the PostgreSQL goose
migrations, starts the Go slot beside the old one, reloads Caddy, and smoke-tests.

## Step 6 — verify

```bash
./scripts/status.sh | tail -30
./scripts/smoke-remote.sh | tail -30
curl -sS https://STAGING_DOMAIN/healthz
docker compose ps | tail -30
```

Expected running: `postgres`, `ubyhost-go` (one live slot), `caddy`, `mock-ubyport`.
NOT running: `walg`, `alloy`, `node-exporter`, `cadvisor`. First admin login link is
in `/data/initial_admin_login`; with `UBYHOST_MAIL_BACKEND=console` claim links appear
in Settings.

## Step 7 — backups: monthly, local only

One cron line, 1st of the month 03:00 UTC (retention 370 days keeps ~a year of monthly
snapshots; the pre-deploy backup inside `deploy.sh` still runs on every deploy):

```bash
(crontab -l 2>/dev/null; echo "0 3 1 * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/backup.sh >> /var/log/ubyhost-backup.log 2>&1") | crontab -
crontab -l | tail -10
```

Do NOT add the daily 03:00 line, the 03:30 `backup-s3.sh`, the 04:00
`backup-gdrive.sh`, or any `walg-backup.sh` / `walg-check.sh` cron — no off-site copies
on staging. Run `./scripts/backup.sh | tail -30` once by hand and confirm a snapshot
folder appears under `/data/backups` in the container. If `STAGING_AGE_RECIPIENT` is
set the snapshot and the `ubyhost-pg.dump.age` are age-encrypted; otherwise the tar is
plaintext on this throwaway box (fine, it never leaves the server). Restore path
(documented, rarely needed): `AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh <stamp>`.

## Step 8 — wire up GitHub deploys to this instance

Owner-side, you verify: create GitHub **environment `staging`** with secrets
`LIGHTSAIL_HOST=STAGING_STATIC_IP`, `LIGHTSAIL_SSH_PRIVATE_KEY` (the ubuntu user key),
`LIGHTSAIL_KNOWN_HOSTS` (`ssh-keyscan -H STAGING_STATIC_IP`), and variable
`LIGHTSAIL_HEALTH_URL=https://STAGING_DOMAIN/healthz`. Then run **Actions → Deploy
staging → Run workflow** on `main` with `ubyport_env=mock`. The run refuses unless the
server's own `.env` says `UBYHOST_DEPLOYMENT=staging` — that identity check is the
guarantee staging secrets can never touch the production box.

## Step 9 — promotion workflow staging → production (write this into your report)

Code only, never data:

1. PR → CI green → merge to `main`.
2. A green CI run on `main` **automatically deploys that exact commit to this staging
   server** (`deploy-staging.yml`, `ubyport_env=mock`). Any branch can also be deployed
   by hand: Actions → Deploy staging → branch + `ubyport_env` (`mock`, or `test` to file
   against the police test environment — test credentials only, never in git).
3. Click the change through on `https://STAGING_DOMAIN`.
4. Production is **manual only**: Actions → **Deploy production** → type `DEPLOY`
   (`deploy-production.yml`: pins current `main` head, requires green CI, checks the
   prod server's `.env` says `production`, then SSH-deploys and checks
   `https://ubyhost.com/healthz`).
5. Rollback: redeploy the previous known-good commit (staging: rerun Deploy staging on
   it; prod: `git reset --hard <sha>` + `./scripts/deploy.sh` per `docs/DEPLOYMENT.md`).
6. Never copy staging data to production, never restore a production backup onto
   staging.

## Report format

Numbered list of what you ran (commands with secrets redacted), then paste:
`./scripts/status.sh`, `docker compose ps`, `docker stats --no-stream`, `df -h`,
`crontab -l`, `curl -sS https://STAGING_DOMAIN/healthz`, and the Deploy staging workflow
conclusion. State explicitly: bundle size, which compose services run, backup schedule,
and that no off-site backup or secret left the server.
