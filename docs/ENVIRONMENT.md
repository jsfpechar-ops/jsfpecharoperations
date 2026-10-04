# Environment variable reference

Complete list of environment variables the application and its deploy scripts
read, with defaults and what goes wrong if the value is absent or wrong. This
is the reference; `deploy/lightsail/.env.example` is the working template and
[LIGHTSAIL.md](LIGHTSAIL.md#environment-variables-what-breaks-if-wrong) is the
production runbook.

Every variable here is optional in the sense that the code has a default. That
is not the same as safe: the defaults are tuned for local development, and
several of them (`UBYPORT_ENV=mock`, `MAIL_BACKEND=disabled`,
`PUBLIC_BASE_URL=127.0.0.1`) are actively wrong for a production host.

`App/app/env_guard.py` refuses to start the process on the unsafe combinations
and logs warnings for the merely suspicious ones. Read its output on boot.

## Core

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_DATA_DIR` | `App/data` | Database, secret key, passport photos. Created at import time with mode `0700`. |
| `UBYHOST_DB` | `$UBYHOST_DATA_DIR/ubyhost.db` | Full path override for the SQLite file. `App/scripts/backup_data.sh` honours it too, so if you set one you must set it for the backup script as well. |
| `UBYHOST_SECRET_KEY` | generated once into `$UBYHOST_DATA_DIR/secret_key` | Minimum 32 characters; the process refuses to start if shorter. Signs session/PIN/claim cookies and CSRF tokens, and derives the Fernet key for UbyPort passwords **and host TOTP secrets**. See [OPERATIONS.md](OPERATIONS.md#if-the-secret-key-is-lost-or-rotated). |
| `UBYHOST_DEPLOYMENT` | `local` | `local`, `staging` or `production`. Gates real behaviour, not just labels: host CSRF enforcement, Turnstile, SES, and secure cookie flags are all conditional on `production`. |
| `PORT` | `8080` (Lightsail) / Render-supplied | Read by `App/render_start.sh` and `deploy/lightsail/docker-compose.yml`, not by the app. |

## UbyPort integration

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_UBYPORT_ENV` | `mock` | `mock`, `test` or `prod`. Any other value is a fatal startup error. `prod` additionally requires `UBYHOST_DEPLOYMENT=production` and refuses to run on Render. |
| `UBYHOST_ALLOW_PROD_MOCK` | unset | `1` allows a production deployment to start while `UBYHOST_UBYPORT_ENV=mock` (which reports nothing to the police). Unset makes that combination a fatal startup error. |
| `UBYHOST_MOCK_URL` | `http://127.0.0.1:8081/ws_uby/ws_uby.svc` | Endpoint used when `UBYPORT_ENV=mock`. |
| `UBYHOST_UBYPORT_DOMAIN` | `EXRESORTMV` | NTLM domain the police authenticate web-service accounts against. Only change this if the Foreign Police say so. |
| `UBYHOST_UBYPORT_TIMEOUT` | `60` | Per-socket timeout in seconds for each SOAP call. |
| `UBYHOST_MAX_BATCH` | `32` | Guests per `ZapisUbytovane` call. This is the spec ceiling as documented; it is **not** refreshed from `MaximalniDelkaSeznamu` at runtime, despite the Test-connection button displaying the service's current answer. If the police lower the ceiling, lower this by hand. |
| `UBYHOST_SOAP_WSA_HEADER` | unset (`0`) | Set to `1` to add a WS-Addressing `Action` header to every SOAP envelope. Read once at import, so it needs a restart. This is the first thing to try if the service starts returning SOAP faults about addressing; it is otherwise untested and should stay off. |

## Scheduler

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_ENABLE_SCHEDULER` | `1` | `0` stops **all** background work: calendar polling, automatic submission, the deadline watch, the guest e-mail outbox, claim-hold expiry and the passport-photo sweep. |
| `UBYHOST_ROLE` | `web` | What the process runs (WP06). `web`: HTTP only, never starts the scheduler (the Docker image, two uvicorn workers). `worker`: only the background jobs, started with `python -m app.worker` (the Lightsail `worker` container). `all`: both in one process (`run.sh` and `render_start.sh` default to it). Only one scheduler can run per data directory: it holds `DATA_DIR/scheduler.lock`. |
| `UBYHOST_WEB_WORKERS` | `2` | uvicorn workers in the Docker image's web process (WP32). `4` on the 8 GB / 2 vCPU production server. `docker-entrypoint.sh` and `preflight.sh` refuse anything but 1 to 16. |
| `UBYHOST_WEB_MEM`, `UBYHOST_WORKER_MEM`, `UBYHOST_LITESTREAM_MEM`, `UBYHOST_CADDY_MEM` | `2g`, `1g`, `256m`, `256m` | Lightsail compose `mem_limit` per container (WP32). Read by `docker compose` from `deploy/lightsail/.env`. Staging on 2 GB: `896m`, `448m`, `128m`, `128m`. |
| `UBYHOST_ACCESS_LOG` | `1` | `0` stops the app's PII-free access line (`ubyhost.access`). The production image also passes uvicorn `--no-access-log`. See `docs/OPERATIONS.md` § Logs. |
| `UBYHOST_GUEST_LANGS` | `en,cs` | Guest form languages, comma-separated, picked from the browser language. English and Czech are always on. Add `de`, `es`, `fr` only after a native speaker has read that catalog in `App/app/i18n.py` (WP33). |
| `UBYHOST_RETENTION_AUTOPURGE` | `0` | `1` lets the daily `retention` job delete what the schedule covers. Off is a dry run: it audits the exact row set and deletes nothing (BE-2, G-D4). |
| `UBYHOST_RETENTION_NOTICE_DAYS` | `30` | How far ahead the "records reach the end of their retention period" notice looks. |
| `UBYHOST_AUDIT_RETENTION_DAYS` | `1095` | Audit rows older than this go; `legal_accepted` evidence has its own rule (BE-4, G-D7). |
| `UBYHOST_ALERT_RETENTION_DAYS` | `365` | Resolved alerts older than this go (BE-4, G-D7). |
| `UBYHOST_RATE_LIMIT_RETENTION_HOURS` | `24` | Stale `rate_limit_event` rows older than this go (BE-4, G-D7). |
| `UBYHOST_RESTRICTED_BLOCKS_FILING` | `0` | `1` withholds a restricted (Art 18) record from police filing. Off until counsel confirms the statutory duty permits it (BE-9). |
| `UBYHOST_ICAL_POLL_MINUTES` | `60` | Calendar poll interval. |
| `UBYHOST_SUBMIT_SWEEP_MINUTES` | `10` | Automatic submission sweep interval. |
| `UBYHOST_HEARTBEAT_URL` | unset | `app/scheduler.py` — pinged after each successful submission sweep. If unset, a dead scheduler is noticed only when someone logs in. |
| `UBYHOST_HEARTBEAT_ICAL_URL` | unset | Pinged after each successful calendar sync (WP07). |
| `UBYHOST_HEARTBEAT_MAIL_URL` | unset | Pinged after each mail run in which every step succeeded (WP07). |
| `UBYHOST_HEARTBEAT_FILING_URL` | unset | Filing watchdog (WP23, `app/filing_watchdog.py`). Pinged on every deadline-job run: `<url>` when no stay is at risk of missing its police deadline, `<url>/fail` when at least one stay with a known reportable guest is (healthchecks.io semantics). Stays with no guest entered never cause `/fail`. Not pinged when the watchdog itself fails. The operator digest of at-risk stays goes to `UBYHOST_OPERATOR_EMAIL`, at most every 6 hours. |

The deadline watch (30 min), guest mail drain (5 min) and passport-photo sweep
(12 h) intervals are not configurable. See
[OPERATIONS.md](OPERATIONS.md#scheduled-jobs) for the full job list.

## Guest-facing

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_PUBLIC_BASE_URL` | `http://127.0.0.1:8080` | Used to build guest permalinks, to match `Origin`/`Referer` on host POSTs, and to decide whether guest cookies get the `Secure` flag. If this is wrong, guest links point at the wrong host and the ownership/claim cookies may be issued without `Secure`. |
| `UBYHOST_DOMAIN` | unset | Expected public hostname. Only used by the startup guard. When it disagrees with `PUBLIC_BASE_URL`, production refuses to start and other deployments get a warning. Production also refuses a `PUBLIC_BASE_URL` that is not `https://`. |
| `UBYHOST_GUEST_PIN` | `1` | `0` removes the PIN gate from every guest route, leaving the permalink token as the only barrier. A production deployment refuses to start with this off. |
| `UBYHOST_GUEST_NOTICE_VERSION` | `1.0` | Version stamped on a guest's notice acknowledgement (BE-5). Bump whenever a `legal_notice_*` / `privacy_*` string in `i18n.py` changes materially. |
| `TURNSTILE_SITE_KEY` | the production widget key in `config.py` | Cloudflare Turnstile site key. |
| `TURNSTILE_SECRET` | unset | Turnstile secret. |
| `TURNSTILE_HOSTNAMES` | unset | Comma-separated hostnames accepted in the Turnstile response. |

Turnstile is **inert unless all three of the `TURNSTILE_*` values are set**.
When it is active, an unreachable Cloudflare fails open a bounded number of
times per address and raises `turnstile_unavailable`.

## Page analytics (Umami)

| Variable | Default | Notes |
|---|---|---|
| `UMAMI_WEBSITE_ID` | unset | Website ID from the Umami website settings. |
| `UMAMI_SCRIPT_URL` | unset | Exact `src` of the tracking code from the Umami website settings. Must be `https://`. |
| `UMAMI_HOST_URL` | unset | Optional `data-host-url`. Unset uses the tracker default; for the Umami Cloud script that is `https://gateway.umami.is`. |
| `UMAMI_DOMAINS` | host of `UBYHOST_PUBLIC_BASE_URL` | `data-domains`, comma-separated. |

The tag is rendered **only when both `UMAMI_WEBSITE_ID` and `UMAMI_SCRIPT_URL`
are set**, and only on the public marketing and legal pages listed in
`app/analytics.py`. Those pages get a CSP that adds the script origin to
`script-src` and the event endpoint to `connect-src`; app, guest and auth pages
keep the strict CSP. `tests/test_umami_guard.py` enforces this.
While it is on, `/privacy` shows the analytics paragraph with an opt-out and
opt-back-in link (`static/umami-optout.js`, localStorage key `umami.disabled`).

## Reverse proxy and client IP

| Variable | Default | Notes |
| --- | --- | --- |
| `CLOUDFLARE_PROXY` | `0` | `1` says Cloudflare fronts the origin (origin certs, Full (strict)). It does **not** grant trust by itself. |
| `UBYHOST_TRUSTED_PROXY_CIDRS` | unset | Comma-separated CIDRs allowed to set `CF-Connecting-IP`. The only source of that trust. |

`CF-Connecting-IP` is believed only when the immediate peer is in
`UBYHOST_TRUSTED_PROXY_CIDRS`. `CLOUDFLARE_PROXY=1` used to imply the whole
private space (loopback, `10/8`, `172.16/12`, `192.168/16`), which let anything
that could reach the origin from a private address — a co-tenant container, a
machine on the office LAN — name its own visitor address and walk past every
per-address rate limit. The app cannot tell a real Caddy peer from any other
private one, so it no longer guesses: set the proxy's network explicitly, for
example `UBYHOST_TRUSTED_PROXY_CIDRS=172.16.0.0/12` for the Docker bridge pool
that `deploy/lightsail` uses. An unset value logs a warning at the first request
that needs it.

If neither is set behind a proxy, every visitor appears to come from the proxy's
address, so all PIN and claim rate limits share a single bucket — one guest
retrying can lock out every other guest, and a brute-force attempt is not
isolated to its source.

## Mail

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_MAIL_BACKEND` | `disabled` | `disabled`, `console` or `ses`. `disabled` also **switches off the claim gate on the guest form**, because there is no way to send the claim link. `ses` is refused unless deployment is production and credentials are complete. |
| `UBYHOST_MAIL_FROM` | unset | Envelope sender; required for `ses`. |
| `UBYHOST_SES_REGION` | `eu-central-1` | |
| `UBYHOST_AWS_ACCESS_KEY_ID` | unset | |
| `UBYHOST_AWS_SECRET_ACCESS_KEY` | unset | |

## Accounts

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_BOOTSTRAP_ADMIN` | `1` | `0` skips creating the first administrator on startup. Use it only on an instance that already has one; with no admin and no bootstrap there is no way in. |
| `UBYHOST_ADMIN_USERNAME` | `admin` | Lower-cased. |
| `UBYHOST_ADMIN_PASSWORD` | unset | When omitted, a random password is written once to `$UBYHOST_DATA_DIR/initial_admin_credentials` with owner-only permissions. |

## Operator identity (shown in the UI and legal pages)

| Variable | Default |
| --- | --- |
| `UBYHOST_OPERATOR_NAME` | unset |
| `UBYHOST_OPERATOR_ICO` | unset |
| `UBYHOST_OPERATOR_DIC` | unset |
| `UBYHOST_OPERATOR_ADDRESS` | unset |
| `UBYHOST_OPERATOR_EMAIL` | `support@ubyhost.com` |
| `UBYHOST_OPERATOR_REGISTRY_URL` | unset |

All six must be set for your own deployment. Production refuses to start while the name, IČO or address is empty. Set them only in the server `.env`, never in the repository. Without them the legal pages
will show empty operator details; set `UBYHOST_OPERATOR_REGISTRY_URL` to your
own public-register entry, or the legal pages will name the wrong company.

## Legal document versions

| Variable | Default |
| --- | --- |
| `UBYHOST_TERMS_VERSION` | `1.6` |
| `UBYHOST_PRIVACY_VERSION` | `1.6` |
| `UBYHOST_DPA_VERSION` | `1.6` |
| `UBYHOST_LEGAL_EFFECTIVE_DATE` | `2026-11-16` |

These override the version number displayed and logged against user acceptance.
The document *text* lives in `App/app/terms_i18n.py`,
`privacy_policy_i18n.py` and `dpa_i18n.py`. Overriding a version without
changing the text — or the reverse — silently desynchronises what a host
accepted from what they were shown. Prefer editing the text and the default in
the same commit and leaving these unset.

`UBYHOST_LEGAL_EFFECTIVE_DATE` (ISO `YYYY-MM-DD`) is the one effective date
printed on `/terms`, `/privacy` and `/dpa`; the version beside it is the
configured version above. Terms 1.6, Privacy 1.6 and DPA 1.6 take effect
together, so a host accepts all three on a single `/account/accept` page. Set
the date at release, at least 30 days after hosts are told (Terms § 22), either
here or by changing `LEGAL_EFFECTIVE_DATE` in `App/app/config.py`. A malformed
value stops start-up.

## Development and test only

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_ICAL_ALLOW_PRIVATE` | `0` | Allows calendar fetches to private/loopback addresses. Never enable outside tests; the Lightsail preflight script refuses to deploy with it on. |
| `MOCK_UBYPORT_STATE` | `App/mock_ubyport/mock_state.json` | State file for the mock police service. Delete it to reset the mock's duplicate register. |
| `MOCK_UBYPORT_HOST` | `127.0.0.1` | |
| `MOCK_UBYPORT_PORT` | `8081` | |

## Read by the platform, not by us

`RENDER`, `RENDER_SERVICE_ID`, `RENDER_INSTANCE_ID`, `RENDER_EXTERNAL_URL` and
`RENDER_EXTERNAL_HOSTNAME` are inspected by the startup guard to detect a
Render-like environment and refuse live police reporting there. You do not set
them; Render does.

## Read by deploy and backup scripts

| Variable | Default | Used by |
| --- | --- | --- |
| `ACME_EMAIL` | unset | `docker-compose.yml` (Caddy/ACME registration) |
| `UBYHOST_CONTAINER` | unset; the scripts fall back to `docker compose ps` (`lib-docker.sh`) | `deploy/lightsail/scripts/backup*.sh` |
| `UBYHOST_INSTALL_DIR` | `/opt/ubyhost` | `setup-server.sh` |
| `UBYHOST_DEPLOY_USER` | `ubuntu` | `setup-server.sh` |
| `UBYHOST_BACKUP_DIR` | `$UBYHOST_DATA_DIR/backups` | `App/scripts/backup_data.sh` |
| `UBYHOST_SECRET_KEY` | unset | `App/scripts/backup_data.sh` — written into the snapshot when there is no `data/secret_key` file, so an off-site restore can be decrypted |
| `UBYHOST_BACKUP_AGE_RECIPIENT` | unset | `App/scripts/backup_data.sh` — public `age1...` recipient the snapshot is encrypted to. **Required when `UBYHOST_DEPLOYMENT=production`**; the run fails closed without it |
| `UBYHOST_BACKUP_RETENTION_DAYS` | `30` | `App/scripts/backup_data.sh` — snapshots older than this many days are removed; the newest is always kept. Set `7` once Litestream replicates (WP32) |
| `UBYHOST_BACKUP_PING_URL` | unset | `deploy/lightsail/scripts/backup.sh` — pinged after each successful daily backup. Required in production: `preflight.sh` refuses to deploy while it is empty. |
| `AGE_IDENTITY_FILE` | unset | `restore.sh` — host path to the age private identity used to decrypt an encrypted snapshot; never inside the volume |
| `RESTORE_CONFIRM` | unset | `restore.sh` — `yes` skips the interactive confirmation prompt |
| `UBYHOST_S3_BUCKET` | unset | `backup-s3.sh` |
| `UBYHOST_S3_PREFIX` | `UbyHost-backups` | `backup-s3.sh` |
| `RENDER_STAGING_DEPLOY_HOOK` | unset (GitHub secret) | `deploy-production.yml` — triggers the Render staging deploy |
| `RCLONE_REMOTE` | `gdrive` | `backup-gdrive.sh` |
| `RCLONE_BACKUP_FOLDER` | `UbyHost-backups` | `backup-gdrive.sh` |
| `SKIP_PUBLIC_SMOKE` | unset | `deploy.sh` — skips the post-deploy public smoke check |
