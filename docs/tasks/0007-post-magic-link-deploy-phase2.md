# 0007: Post magic-link deploy — phase 2 (production cutover)

Status: ready  
Depends on: phase 1 done (login e-mails on every active account; `./scripts/deploy.sh` or Deploy production green)  
Executor: new Cursor session (Composer) | Owner: Josef for server, proxy, UbyPort checks

## Phase 1 done (do not repeat)

- Active accounts have login e-mails (SQL or `/admin/users` after deploy).
- Production deploy completed (`deploy/lightsail/scripts/deploy.sh` or Actions).
- `main` includes #288–#292 (magic link, hardening, test fixes, auto-deploy after green CI).

## Objective

Finish production cutover after e-mail login: verify live app, legal re-accept, UbyPort property checks, 112 reconcile, proxy hygiene, and doc/status closeout.

## Routing

| Area | Read |
|------|------|
| Mail / login | [SES](SES.md), [SECURITY](SECURITY.md) |
| Deploy / smoke | [DEPLOYMENT](DEPLOYMENT.md), [LIGHTSAIL](LIGHTSAIL.md), `deploy/lightsail/scripts/smoke-remote.sh` |
| UbyPort / 112 | [UBYPORT_CORE](UBYPORT_CORE.md), K-F13 in [known-issues](context/known-issues.md) |
| Legal v1.7 | [0005 report](0005-report.md) if present, [RETENTION](privacy/RETENTION.md) |

## Checklist (in order)

### A. Verify production (owner or SSH)

1. `curl -sS https://ubyhost.com/healthz` — JSON `status":"ok"`.
2. Sign in at `/login` with your **login e-mail** (magic link). Confirm old password login is gone.
3. **Settings** — deployment `production`, UbyPort target as intended (`test` until go-live, then `prod`).
4. **Admin → Users** — no missing-e-mail banner; spot-check rows show login e-mails.

### B. Server `.env` (SSH, `deploy/lightsail/.env`)

1. Set **`UBYHOST_ADMIN_EMAIL`** to the address the admin uses at `/login` (see [ENVIRONMENT](ENVIRONMENT.md) admin section).
2. Remove or disable bootstrap admin password vars if any remain (`UBYHOST_BOOTSTRAP_ADMIN=0` typical).
3. Confirm **`UBYHOST_MAIL_BACKEND=ses`** (or documented choice); mail sends for login links.

### C. Reverse proxy (owner — Caddy/nginx/Cloudflare)

1. **Do not log query strings** on `/login/link` (token in `?t=`). See task 0006 report owner step 2.
2. Reload proxy after change.

### D. Every property (host UI)

1. For each apartment: **Save and test connection** to UbyPort (loads error severities on success).
2. Note any failures before filing season.

### E. Legal v1.7 (hosts)

1. After deploy, hosts with pending documents see **/account/accept** until they accept v1.7.
2. Owner: confirm operator copy on `/legal` / terms / privacy matches what lawyer approved (0005 LAWYER REVIEW strings still open if not signed off).

### F. Reconcile code 112 (production data — careful)

From server `App/` (or `docker compose exec ubyhost`):

1. Dry run: `.venv/bin/python scripts/reconcile_accepted_codes.py`
2. In UbyPort web app, verify **2–3** listed guest ids match reality (112 = reported late = accepted per police letter).
3. If correct: `.venv/bin/python scripts/reconcile_accepted_codes.py --apply`
4. Never run `--apply` without spot-check (see [0002-police brief](0002-police-downloads-stayfee.md) § Owner steps).

### G. Repo hygiene (executor)

1. Update [status.md](context/status.md) — production commit, deploy run id, phase 2 done items.
2. Mark phase 1 owner steps done in [0002-report](0002-report.md) / [0006-report](0006-report.md) if accurate.
3. `python3 scripts/context_lint.py` from repo root.

## Out of scope

- Lawyer sign-off on 0005 (separate track).
- Task 0001 step 12 `APPLY=1` unless owner asks.
- Changing `require_green_ci` or deploy gates.

## Success

Production hosts use e-mail login only; properties connection-tested; 112 reconcile applied or explicitly deferred with owner note; proxy does not log login tokens; status.md reflects live revision.
