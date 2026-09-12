# Deployment and environments

UbyHost runs in **three logical tiers**. Only one of them talks to the real police
register.

| Tier | Render service | `UBYHOST_DEPLOYMENT` | `UBYHOST_UBYPORT_ENV` | Disk | Purpose |
|------|----------------|----------------------|------------------------|------|---------|
| **Local** | — | `local` (default) | `mock` | `./App/data` | Development on your laptop |
| **Staging** | `ubyhost-staging` | `staging` | `mock` | Ephemeral (free tier OK) | Demos, UX testing, new features |
| **Production** | `ubyhost` | `production` | `test` → `prod` | **Required** (persistent volume) | Real guest reporting |

Nothing in staging ever leaves your server for the police. Production starts on the
**test** UbyPort endpoint so you can validate credentials and field mappings before
flipping to **prod**.

## Architecture

```
GitHub (main)
    │
    ├── CI (pytest + smoke) on every PR
    │
    └── Render Blueprint (render.yaml)
            ├── ubyhost-staging   mock + manual deploy (optional)
            └── ubyhost           test/prod + auto-deploy from main + disk
```

## First-time setup on Render

1. Push this repository to GitHub.
2. In [Render](https://render.com/): **New → Blueprint** → connect the repo.
3. Click **Apply**. Two web services are created:
   - `ubyhost-staging` — safe playground (manual deploy; staging auto-deploy is off in the blueprint).
   - `ubyhost` — production (auto-deploys from `main` when CI passes).
4. On **`ubyhost` (production)** only, open **Environment** and set:
   - `UBYHOST_ADMIN_USERNAME` — your admin login (e.g. `admin`).
   - `UBYHOST_ADMIN_PASSWORD` — a long unique password (not shared with staging).
5. Leave `UBYHOST_UBYPORT_ENV=test` until the [production checklist](PRODUCTION_CHECKLIST.md)
   is complete.
6. Add GitHub secret **`RENDER_DEPLOY_HOOK`**: Render → **ubyhost** → Settings → **Deploy Hook** → copy URL.
   CI triggers production on every green `main` build. First deploy: **Manual Deploy → Deploy latest commit** if needed.

Verify both services: `curl https://<host>/healthz` should return JSON with
`deployment` and `ubyport_env`.

## Promotion workflow (staging → production)

Use this whenever you ship a change that affects hosts or guests.

1. **Merge to `main`** — GitHub Actions must pass (tests + smoke).
2. **Production** — `ubyhost` auto-deploys from `main` (or CI hits `RENDER_DEPLOY_HOOK`).
3. **Staging** (optional) — deploy `ubyhost-staging` manually when you want a mock playground.
4. **Smoke production** — sign in, open Settings, confirm:
   - Deployment = `production`
   - UbyPort target = `test` (until go-live) or `prod`
   - Public base URL matches the production hostname
5. **Rollback** — Render **Events → Rollback** to the previous deploy, or redeploy an
   earlier commit. The SQLite database lives on the disk and is **not** rolled back
   with the code — only application code reverts.

## Secrets and credentials

| Secret | Where | Notes |
|--------|-------|-------|
| `UBYHOST_SECRET_KEY` | Render env (generated) | Encrypts UbyPort passwords at rest. **Never rotate** without a migration plan. |
| `UBYHOST_ADMIN_PASSWORD` | Render env (you set) | Bootstrap admin only; change in the UI after first login. |
| UbyPort **web-service** login (`UBY-WS…`) | Entered per apartment in the UI | **Not** your normal UbyPort web login. Request from `reguby@pcr.cz` / data box `ybndqw9`. |
| Police PDF / portal passwords | **Never** in git or Render env | Those are for the human UbyPort portal, not this app. |

## Persistent data and backups

Production **must** use a persistent volume. The blueprint mounts Render disk at
`App/data` on the `ubyhost` service.

On the server (or via Render shell):

```bash
cd App
./scripts/backup_data.sh
```

Backups land in `data/backups/` (last 10 kept). Copy them off Render periodically
(S3, Google Drive, etc.).

To restore: stop the service, replace `ubyhost.db` from a backup, restart.

## Alternative hosts

### AWS Lightsail (Docker — recommended VPS path)

Full guide: **[LIGHTSAIL.md](LIGHTSAIL.md)**  
Domain + DNS (Cloudflare): **[CLOUDFLARE.md](CLOUDFLARE.md)**

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
| `UBYHOST_PUBLIC_BASE_URL` | `https://ubyhost.onrender.com` (or your custom domain) |
| `UBYHOST_GUEST_PIN` | `1` (recommended) |
| `UBYHOST_ENABLE_SCHEDULER` | `1` |
| `UBYHOST_DATA_DIR` | `/opt/render/project/src/App/data` (default on Render with disk) |

## What not to do

- Do not point production at `mock`.
- Do not enable **Load demo data** in production (blocked by the app when not on mock).
- Do not commit `App/data/*`, PDFs, or police credentials to git.
- Do not skip the **test** endpoint before `prod` — rejections on prod count against you.
