# STEP0: Staging deploy target in GitHub Actions

## Summary
The Lightsail deploy steps move into a reusable workflow, `deploy-lightsail.yml` (`workflow_call`). `deploy-production.yml` calls it with environment `production`, ref `main`, CI required and `https://ubyhost.com/healthz`. Production behaviour is unchanged: manual, `force_confirm=DEPLOY`, pinned to main's head, green CI required, same concurrency group, and the Render hook job is kept.

The new `deploy-staging.yml` (manual only) deploys any branch to environment `staging`, using that environment's own secrets. The CI check stays on, with an opt-out checkbox.

Both runs first read the target server's `.env` and refuse to touch the server unless `UBYHOST_DEPLOYMENT` matches the target (staging also needs `UBYHOST_UBYPORT_ENV=mock`). The stack gets a `mock-ubyport` compose service under profile `staging`, so mock filing works on Lightsail.

Stacked on WP05, WP06 and WP07.

## Files changed
- `.github/workflows/deploy-lightsail.yml`: new reusable workflow (the old production steps, parameterised, plus the server identity check).
- `.github/workflows/deploy-production.yml`: the job now calls the reusable workflow; comments updated.
- `.github/workflows/deploy-staging.yml`: new manual staging deploy (branch input, skip-CI checkbox, concurrency `deploy-staging`).
- `.github/workflows/deploy-preflight.yml`: environment choice (production or staging); prints `COMPOSE_PROFILES`.
- `deploy/lightsail/docker-compose.yml`: `mock-ubyport` service, profile `staging`. It uses the app image and mounts `App/mock_ubyport` read-only, because the image excludes that directory.
- `deploy/lightsail/scripts/preflight.sh`: rules for staging (mock, profile, mock URL, own Litestream prefix), and refuses the staging profile on production.
- `deploy/lightsail/.env.example`, `deploy/lightsail/README.md`, `docs/DEPLOYMENT.md`: staging docs.

## Tests added
No app tests (workflow and deploy files only). Checks run:
- `actionlint` on all workflows: clean. `yaml.safe_load`: all five parse.
- The remote identity check was extracted from the rendered heredoc and run against fake `.env` files (quoted values and CRLF included): staging run on a production server refused; staging server with `test` refused; staging and mock passed; production on production passed; production on a staging server refused.
- `preflight.sh` with fake `.env` files: a valid staging `.env` gives "Preflight OK". Staging without mock, profile, mock URL or own prefix gives 4 errors. Production with `COMPOSE_PROFILES=staging` is refused.
- `shellcheck -S error` on deploy scripts: clean.

## Test commands and results
As above. `pytest tests/test_backup_offsite.py tests/test_env_guard.py tests/test_worker.py tests/test_startup_concurrency.py tests/test_wp07_cache_heartbeats.py tests/test_scheduler.py`: 58 passed.

## Deviations from the spec and why
- The spec only asks for a second target. The added server-side identity check (before `git reset`) is the guard against a staging run whose secrets fall back to repo-level production secrets. Without it, such a run would check out a feature branch on the production server.
- Staging uses `UBYHOST_DEPLOYMENT=staging`, not production+mock. This keeps Turnstile, operator-identity and backup-encryption rules production-only, as on Render staging.
- Mock UbyPort is a compose profile service. On Lightsail there was no mock server, so `UBYPORT_ENV=mock` would have failed every submission.
- The spec says the staging instance is a 1 GB bundle. WP06's memory check refuses less than about 1.7 GB, so the staging `.env` sets `UBYHOST_ALLOW_SMALL_HOST=1`. Memory limits are caps, and staging traffic is tiny.
- `deploy-preflight.yml` got an environment input. This is small and needed to check the staging server the same way.

## What Cursor must verify or adapt when applying on the real main
- The reusable workflow uses `${{ github.repository }}` instead of the hard-coded repo slug. Confirm it resolves to the same repository.
- First production run after merge: watch that the job is now named `lightsail / lightsail` and still pins to main and checks CI.
- Before the first run, run Deploy preflight (production) and confirm the server prints `UBYHOST_DEPLOYMENT=production`. The new identity check refuses otherwise.
- Required check names (`test, smoke, guest-browser, shellcheck, docker, secrets`) are unchanged.

## Manual steps for the owner
1. Lightsail: new instance, Frankfurt, 1 GB bundle (2 GB if you want staging to mirror production memory for HIGH RISK checks). Attach a static IP. Follow docs/LIGHTSAIL.md setup. DNS: `staging.<your-domain>` A record to that IP (Cloudflare proxied, origin certificate for that hostname, or grey cloud with Let's Encrypt).
2. Staging `.env` (placeholders, see README "Staging server"): `UBYHOST_DEPLOYMENT=staging`, `UBYHOST_UBYPORT_ENV=mock`, `COMPOSE_PROFILES=staging`, `UBYHOST_MOCK_URL=http://mock-ubyport:8081/ws_uby/ws_uby.svc`, own domain and public URL, `UBYHOST_MAIL_BACKEND=console`, `UBYHOST_ALLOW_SMALL_HOST=1`, a new `UBYHOST_SECRET_KEY` (never the production one), and operator fields with placeholders.
3. Litestream for staging: same bucket, `LITESTREAM_S3_PATH=staging/ubyhost`, and a separate IAM user `ubyhost-litestream-staging` with the WP05 policy but prefixes `staging/*` / `staging`, so staging can never write the production prefix.
4. GitHub → Settings → Environments → New environment `staging`. Deployment branches: All branches. Secrets: `LIGHTSAIL_HOST` (staging static IP), `LIGHTSAIL_SSH_PRIVATE_KEY` (a key pair made only for staging), and `LIGHTSAIL_KNOWN_HOSTS` (`ssh-keyscan <staging-ip>`). Variable: `LIGHTSAIL_HEALTH_URL=https://staging.<your-domain>/healthz`.
5. GitHub → Environments → `production`. Set Deployment branches and tags to "Selected: main", so a production deploy cannot run a workflow file from a feature branch. If the three `LIGHTSAIL_*` secrets are repository-level today, move them into the `production` environment and delete the repository-level copies.
6. Run Actions → Deploy preflight (staging), then Actions → Deploy staging on a branch. Sign in on the staging domain, file a demo stay, and check the mock receipt.
7. Never put real guest data on staging.
