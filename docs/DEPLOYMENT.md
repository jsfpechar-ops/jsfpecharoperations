# Deployment and environments

UbyHost runs in **three logical tiers**. The checked-in configuration points only
**production** at the real police register. The application does not enforce
this separation, so verify `UBYHOST_DEPLOYMENT` and `UBYHOST_UBYPORT_ENV`
together before every deployment.

**Operator setup (UbyHost / jsf):**

| Role | Where | Example URL |
|------|--------|-------------|
| **Staging** | Render **`ubyhost-staging`** | `https://ubyhost-staging.onrender.com` |
| **Production** | **AWS Lightsail** (`deploy/lightsail`) | `https://ubyhost.com` |

Use Render for mock demos and UX checks. Run live reporting only on Lightsail.

| Tier | Host | `UBYHOST_DEPLOYMENT` | `UBYHOST_UBYPORT_ENV` | Disk | Purpose |
|------|------|----------------------|------------------------|------|---------|
| **Local** | — | `local` (default) | `mock` | `./App/data` | Development on your laptop |
| **Staging** | Render **`ubyhost-staging`** | `staging` | `mock` | Ephemeral (free tier OK) | Demos, UX testing, new features |
| **Production** | **Lightsail** Docker stack | `production` | `test` → `prod` | Volume `ubyhost-data` | Real guest reporting |

Staging is configured for `mock`; while that configuration is active, nothing
leaves the server for the police. Do not set staging to `test` or `prod`.
Production starts on the **test** UbyPort endpoint so you can validate credentials
and field mappings before flipping to **prod**.

The blueprint still defines Render **`ubyhost`** (Starter + disk) for all-in-on-Render
deployments. **This project’s production is Lightsail** — suspend or remove Render
`ubyhost` if you do not want a second production host.

## Architecture

```
GitHub (main)
    │
    ├── CI (pytest + smoke) on every PR
    │
    ├── Render (render.yaml)
    │       └── ubyhost-staging   mock, manual deploy — staging only
    │
    └── AWS Lightsail (/opt/ubyhost/deploy/lightsail)
            └── ubyhost + Caddy   production, persistent SQLite
```

## First-time setup on Render (staging)

1. Push this repository to GitHub.
2. In [Render](https://render.com/): **New → Blueprint** → connect the repo.
3. Click **Apply**. You get **`ubyhost-staging`** (mock) and optionally **`ubyhost`**.
4. Use **`ubyhost-staging`** only for staging: manual deploy when you want to test UI.
   Admin password is in Render → **ubyhost-staging** → Environment.
5. **Production** is not on Render for this operator — see **[LIGHTSAIL.md](LIGHTSAIL.md)** and
   `deploy/lightsail/README.md`. Skip Render `ubyhost` or suspend it after Lightsail is live.
6. Optional: GitHub secret **`RENDER_DEPLOY_HOOK`** only if you still auto-deploy Render
   **`ubyhost`**; Lightsail updates via `git pull` + `./scripts/deploy.sh` on the VM.

Verify both services: `curl https://<host>/healthz` should return JSON with
`deployment` and `ubyport_env`.

## Promotion workflow (staging → production)

Use this whenever you ship a change that affects hosts or guests.

1. **Merge to `main`** — GitHub Actions must pass (tests + smoke).
2. **Staging** (optional) — Render → **`ubyhost-staging`** → Manual Deploy.
3. **Production (Lightsail)** — SSH to the instance, then:
   ```bash
   cd /opt/ubyhost && git pull origin main
   cd deploy/lightsail && ./scripts/deploy.sh
   ```
4. **Smoke production** — sign in at **ubyhost.com**, open Settings, confirm:
   - Deployment = `production`
   - UbyPort target = `test` (until go-live) or `prod`
   - Public base URL = `https://ubyhost.com`
5. **Rollback** — redeploy a previous git commit on Lightsail (`git checkout` / `git pull`
   an older SHA, then `./scripts/deploy.sh`). SQLite on the Docker volume is **not**
   rolled back with the code.

## Secrets and credentials

| Secret | Where | Notes |
|--------|-------|-------|
| `UBYHOST_SECRET_KEY` | Render env (generated) | Encrypts UbyPort passwords at rest. **Never rotate** without a migration plan. |
| `UBYHOST_ADMIN_PASSWORD` | Render env (you set) | Bootstrap admin only; change in the UI after first login. |
| UbyPort **web-service** login (`UBY-WS…`) | Entered per apartment in the UI | **Not** your normal UbyPort web login. Request from `reguby@pcr.cz` / data box `ybndqw9`. |
| Police PDF / portal passwords | **Never** in git or Render env | Those are for the human UbyPort portal, not this app. |
| Annotated **sample** WS credential PDF | Committed under `App/app/static/docs/` | Fictional training aid only. Regenerate with `python App/tools/generate_ubyport_sample_pdf.py` (ReportLab). |

## Persistent data and backups

**Production (Lightsail)** stores SQLite on the Docker volume `ubyhost-data`. On the VM:

```bash
cd /opt/ubyhost/deploy/lightsail
./scripts/backup.sh
```

Backups land in the container under `/data/backups/` (last 10 kept). Off-site copy:
**Google Drive** via `scripts/backup-gdrive.sh` (recommended). **S3** via
`scripts/backup-s3.sh` is optional and can be deferred.

**Staging (Render)** uses ephemeral disk on the free tier — no production data there.

To restore production: stop the stack, replace `ubyhost.db` from a backup on the volume,
restart.

## Production host (Lightsail)

Full guide: **[LIGHTSAIL.md](LIGHTSAIL.md)**  
Domain + DNS (Cloudflare): **[CLOUDFLARE.md](CLOUDFLARE.md)**  
Production zone extras (HSTS, Bot Fight Mode, leaked credentials, client-side security): same file, section **Production zone (`ubyhost.com`)**.

```bash
cd deploy/lightsail
cp .env.example .env   # edit domain, passwords, UbyPort env
./scripts/deploy.sh
```

Includes Caddy (automatic HTTPS), persistent SQLite volume, backup scripts, and
sizing notes for ~10 properties.

### Manual Docker (any VPS)

```bash
docker build -t ubyhost .
docker run -p 8080:8080 \
  -e UBYHOST_DATA_DIR=/data \
  -e UBYHOST_DEPLOYMENT=production \
  -e UBYHOST_UBYPORT_ENV=test \
  -e UBYHOST_PUBLIC_BASE_URL=https://your.domain \
  -e UBYHOST_ADMIN_USERNAME=admin \
  -e UBYHOST_ADMIN_PASSWORD='…' \
  -v ubyhost-data:/data \
  ubyhost
```

Set `UBYHOST_UBYPORT_ENV=mock` only for non-production stacks.

## Monitoring

- **Health**: `GET /healthz` — `status`, `deployment`, `ubyport_env`, `data_dir_writable`.
- **Render**: enable email alerts for deploy failures and health-check failures.
- **Application**: Settings → audit log; apartment submission history and Doručenka PDFs.

## Environment variables (production)

| Variable | Production value |
|----------|-------------------|
| `UBYHOST_DEPLOYMENT` | `production` |
| `UBYHOST_UBYPORT_ENV` | `test`, then `prod` |
| `UBYHOST_PUBLIC_BASE_URL` | `https://ubyhost.com` (Lightsail) |
| `UBYHOST_GUEST_PIN` | `1` (recommended) |
| `UBYHOST_ENABLE_SCHEDULER` | `1` |
| `UBYHOST_DATA_DIR` | `/data` in the container (Lightsail volume) |

## What not to do

- Do not point production at `mock`.
- Do not enable **Load demo data** in production (blocked by the app when not on mock).
- Do not commit `App/data/*`, PDFs, or police credentials to git.
- Do not skip the **test** endpoint before `prod` — rejections on prod count against you.
