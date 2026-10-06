# Status

Updated: 2026-10-06 after magic-link deploy phase 1 (e-mails + production deploy).

## Production

- **Phase 1 done:** login e-mails on all active accounts; deploy via Lightsail (`deploy.sh` or Actions).
- **`main`:** #288–#292 merged (magic link, 0006 hardening, CI/deploy automation). Confirm live git SHA on server with `git rev-parse HEAD` in `/opt/ubyhost`.
- **Phase 2:** follow [0007 post-deploy brief](../tasks/0007-post-magic-link-deploy-phase2.md) in a **new agent session**.

## Now

- Owner: phase 2 checklist (proxy `/login/link` logs, `.env` admin e-mail, per-property UbyPort test, `reconcile_accepted_codes.py`).
- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not yet signed off.

## Next

- After phase 2: Doručenka smoke on a new filing; optional #280+#281 features if not already live.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, operator `.env`, healthchecks, Better Stack, Cloudflare, retention autopurge, Render staging, Litestream/backup drill, task 0001 context rollout (#281), **login e-mails on production accounts (Oct 2026)**.
