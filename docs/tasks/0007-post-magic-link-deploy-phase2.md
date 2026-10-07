# 0007: Post magic-link deploy — phase 2 (production cutover)

Status: done
Depends on: phase 1 done (login e-mails on every active account; `./scripts/deploy.sh` or Deploy production green)
Executor: Cursor | Owner: Josef for server, proxy, UbyPort checks

## 1. Objective

Finish production cutover after e-mail login: verify live app, legal re-accept, UbyPort property checks, 112 reconcile, proxy hygiene, and doc/status closeout.

## 2. Context

Phase 1 done (do not repeat): active accounts have login e-mails; production deploy completed; `main` includes #288–#292 (magic link, hardening, test fixes, auto-deploy after green CI).

| Area | Read |
|------|------|
| Mail / login | [SES](../SES.md), [SECURITY](../SECURITY.md) |
| Deploy / smoke | [DEPLOYMENT](../DEPLOYMENT.md), [LIGHTSAIL](../LIGHTSAIL.md), `deploy/lightsail/scripts/smoke-remote.sh` |
| UbyPort / 112 | [UBYPORT_CORE](../UBYPORT_CORE.md), K-F13 in [known-issues](../context/known-issues.md) |
| Legal v1.7 | [0005 report](0005-report.md) if present, [RETENTION](../privacy/RETENTION.md) |

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/context/status.md` | edit | Production revision, phase 2 progress |
| `docs/tasks/0002-report.md` | edit | Mark phase 1 owner steps done where accurate |
| `docs/tasks/0006-report.md` | edit | Mark login e-mails done; proxy step open until verified |
| `docs/tasks/0007-report.md` | edit | Executor report |

No `App/` changes.

## 4. Steps

### A. Verify production (owner or SSH)

1. `curl -sS https://ubyhost.com/healthz` — JSON `status":"ok"`. *(Agent done 2026-10-06.)*
2. Sign in at `/login` with your **login e-mail** (magic link). Confirm old password login is gone.
3. **Settings** — deployment `production`, UbyPort target as intended (`test` until go-live, then `prod`).
4. **Admin → Users** — no missing-e-mail banner; spot-check rows show login e-mails.

### B. Server `.env` (SSH, `deploy/lightsail/.env`)

1. Set **`UBYHOST_ADMIN_EMAIL`** to the address the admin uses at `/login` (see [ENVIRONMENT](../ENVIRONMENT.md) admin section).
2. Remove or disable bootstrap admin password vars if any remain (`UBYHOST_BOOTSTRAP_ADMIN=0` typical).
3. Confirm **`UBYHOST_MAIL_BACKEND=ses`** (or documented choice); mail sends for login links.

### C. Reverse proxy (owner — Caddy/nginx/Cloudflare)

1. **Do not log query strings** on `/login/link` (token in `?t=`). See task 0006 report owner step 2. Repo default: `deploy/lightsail/caddy/Caddyfile.cloudflare` has access logging off.
2. Reload proxy after change.

### D. Every property (host UI)

1. For each apartment: **Save and test connection** to UbyPort (loads error severities on success).
2. Note any failures before filing season.

### E. Legal v1.7 (hosts)

1. After deploy, hosts with pending documents see **/account/accept** until they accept v1.7.
2. Owner: confirm operator copy on `/legal` / terms / privacy matches what lawyer approved (0005 LAWYER REVIEW strings still open if not signed off).

### F. Reconcile code 112 (production data — careful)

From `deploy/lightsail` on the server:

1. Dry run: `docker compose exec -T ubyhost python scripts/reconcile_accepted_codes.py`
2. In UbyPort web app, verify **2–3** listed guest ids match reality (112 = reported late = accepted per police letter).
3. If correct: `docker compose exec -T ubyhost python scripts/reconcile_accepted_codes.py --apply`
4. Never run `--apply` without spot-check (see [0002-police brief](0002-police-downloads-stayfee.md) § Owner steps).

### G. Repo hygiene (executor)

1. Update [status.md](../context/status.md) — production commit, deploy run id, phase 2 done items.
2. Mark phase 1 owner steps done in [0002-report](0002-report.md) / [0006-report](0006-report.md) if accurate.
3. `python3 scripts/context_lint.py` from repo root.

## 5. Do not touch

- Lawyer sign-off on 0005 (separate track).
- Task 0001 step 12 `APPLY=1` unless owner asks.
- Changing `require_green_ci` or deploy gates.
- Re-do phase 1 (login e-mails, deploy).

## 6. Commands

```bash
curl -sS https://ubyhost.com/healthz
cd deploy/lightsail && ./scripts/smoke-remote.sh https://ubyhost.com
python3 scripts/context_lint.py
```

On server (§F): `docker compose exec -T ubyhost python scripts/reconcile_accepted_codes.py` (then `--apply` if spot-check OK).

## 7. Acceptance

- [x] A.1 healthz OK (agent).
- [x] A.2–A.4 magic-link login, Settings, Admin → Users (owner, 2026-10-07).
- [x] B `.env` admin e-mail and SES (owner).
- [x] C proxy does not log `/login/link?` tokens (owner verify).
- [x] D every property connection-tested (owner).
- [x] E legal accept flow spot-checked (owner).
- [x] F reconcile dry run: 0 guests; `--apply` skipped (nothing to change).
- [x] G status, reports, context lint (executor).

## 8. Stop and ask

Stop if reconcile output is unexpected, any property connection fails, or `.env` values are unclear.

## 9. Report

Write [0007-report.md](0007-report.md). Set brief `Status: done` when owner A.2–F are complete.

## Risk list (for the reviewer)

`docs/context/status.md`, `docs/tasks/0002-report.md`, `docs/tasks/0006-report.md`, `docs/tasks/0007-report.md`.

## Owner steps

Numbered list: brief §4 steps **A.2 through F** (browser, SSH, UbyPort). Full copy in [0007-report.md](0007-report.md).
