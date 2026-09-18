# Deployment and environments

UbyHost runs in **three logical tiers**. The checked-in configuration points only
**production** at the real police register. The application does not enforce
this separation, so verify `UBYHOST_DEPLOYMENT` and `UBYHOST_UBYPORT_ENV`
together before every deployment.

**Operator setup (***REMOVED***):**

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

## Guest e-mail (staging first)

Claim links, the guest's single day-before incomplete-registration reminder, host incomplete-registration warnings, and completion receipts are **not** delivered on production until SES is deliberately enabled.

| Host | `UBYHOST_MAIL_BACKEND` | Where messages go |
|------|------------------------|-------------------|
| **ubyhost-staging** (Render) | `console` | Settings → Guest e-mails (copy the `#c=` confirmation link) |
| **Lightsail production** | `disabled` (default) | Nothing is queued or sent |
| **Lightsail + SES** | `ses` only when `UBYHOST_DEPLOYMENT=production` and credentials are complete | Amazon SES (`eu-central-1`) |

After a manual deploy of a claim build to **ubyhost-staging**, open Settings and confirm the backend is `console`. Production `.env` must keep `UBYHOST_MAIL_BACKEND=disabled` until the [SES enablement runbook](SES.md) is complete (domain DKIM/MAIL FROM verified, IAM keys, `_send_ses` deployed, then `.env` flip).

**Contact split:** the host admin portal (sidebar and Settings) shows **`support@ubyhost.com`** for software questions. The guest form shows the **host** legal-entity name, e-mail, and phone for anything about the stay. Do not send guests to UbyHost support for bookings.

### Required owner acceptance before production

Do **not** promote this guest-claim build to production until the product owner has personally tested it on **ubyhost-staging** and explicitly approved the exact revision. Keep production guest mail disabled during review.

The staging acceptance check covers:

- host sidebar and Settings show `support@ubyhost.com`;
- property legal-entity name, e-mail, and phone appear on the guest form;
- the optional per-property custom guest message can be saved, edited, cleared, and renders with line breaks;
- PIN, date selection, guest count, e-mail claim, explicit magic-link confirmation, masked assignment, and lock/reopen/release work;
- incomplete claimed forms remain open during the 24-hour post-check-in grace period, the host receives the check-in-day warning, and access locks afterward unless explicitly reopened;
- immediate reporting sends only after the whole declared party is complete; delayed reporting uses the saved completion time plus the configured hours (24 by default), then sends without host verification;
- check-in visibility, one day-before guest reminder, host incomplete-registration warning, completion receipt/CC, passport policy, and all three reporting gates behave as configured; verify reminder deduplication;
- English and Czech guest flows are clear;
- console mail contains the expected messages without contacting real guests.

After approval, deploy the code and database migration first with `UBYHOST_MAIL_BACKEND=disabled` and UbyPort still on `test`. Back up production and run smoke checks before separately enabling SES or real UbyPort reporting. A failed check returns the revision to staging.

## Promotion workflow (staging → production)

Use this whenever you ship a change that affects hosts or guests.

1. **Staging** (required for this build) — Render → **`ubyhost-staging`** → Manual Deploy of the PR branch. Record the tested commit and obtain explicit product-owner approval using the checklist above.
2. **Merge the approved revision to `main`** — GitHub Actions must pass (tests + smoke). Keep `LIGHTSAIL_AUTO_DEPLOY=0` until the owner approves production deployment.
3. **Production (Lightsail)** — after approval and green CI, SSH to the instance, then:
   ```bash
   cd /opt/ubyhost && git pull origin main
   cd deploy/lightsail && ./scripts/deploy.sh
   ```
   Or GitHub → **Actions → Deploy production → Run workflow** (`workflow_dispatch`).
   CI-triggered deploys after green `main` run when SSH secrets are set (default on). For this build, keep `LIGHTSAIL_AUTO_DEPLOY=0` until the owner’s staging acceptance and production approval are recorded.
   `deploy.sh` refuses to replace a running release unless it can create and
   integrity-check a SQLite backup first. It then dry-runs the new schema
   migration against a copy of that backup and compares critical live table
   row counts after startup.
4. **Smoke production** — `./scripts/status.sh` and `./scripts/smoke-remote.sh`. Sign in at **ubyhost.com**, open Settings, confirm:
   - Deployment = `production`
   - UbyPort target = `test` (until go-live) or `prod`
   - Public base URL = `https://ubyhost.com`
   Public `GET /healthz` in production does **not** include those labels (monitoring still gets `status` + `data_dir_writable`).
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

To restore production: see **[LIGHTSAIL.md](LIGHTSAIL.md#restore-runbook-same-instance)** (`./scripts/restore.sh`). Off-site: Google Drive via `backup-gdrive.sh`.

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

- **Health**: `GET /healthz` — `status`, `version`, `data_dir_writable`. Outside production it also includes `deployment` and `ubyport_env`. On Lightsail use `./scripts/status.sh` for the env labels.
- **No external pager** is configured; failed submissions surface as in-app alerts and `./scripts/logs.sh`.
- **Render**: enable email alerts for deploy failures and health-check failures (staging only).
- **Application**: Settings → audit log; apartment submission history and Doručenka PDFs.

## Environment variables (production)

| Variable | Production value | If wrong |
|----------|------------------|----------|
| `UBYHOST_DEPLOYMENT` | `production` | `prod` UbyPort will not start |
| `UBYHOST_UBYPORT_ENV` | `test`, then `prod` | `mock` sends nowhere; `prod` on Render is refused |
| `UBYHOST_PUBLIC_BASE_URL` | `https://ubyhost.com` | Guest links / cookies |
| `UBYHOST_GUEST_PIN` | `1` | Unprotected permalinks |
| `UBYHOST_ENABLE_SCHEDULER` | `1` | No iCal / auto-submit / photo sweep |
| `UBYHOST_DATA_DIR` | `/data` in the container | Empty DB on a new volume |
| `UBYHOST_SECRET_KEY` | ≥32 chars, stable | Lost Fernet + sessions |

Full table: [LIGHTSAIL.md](LIGHTSAIL.md#environment-variables-what-breaks-if-wrong).

## What not to do

- Do not point production at `mock`.
- Do not enable **Load demo data** in production (blocked by the app when not on mock).
- Do not commit `App/data/*`, PDFs, or police credentials to git.
- Do not skip the **test** endpoint before `prod` — rejections on prod count against you.
