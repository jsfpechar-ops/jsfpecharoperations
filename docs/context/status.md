# Status

Updated: 2026-10-06 after task 0007 phase 2 executor closeout (PR #293).

## Production

- **Phase 1 done:** login e-mails on all active accounts; magic-link deploy on Lightsail.
- **Live smoke (agent):** `/healthz` OK (`version` 1.1.0, 2026-10-06); `/legal`, `/privacy` 200; `/login` skipped (Cloudflare challenge from outside).
- Confirm git SHA on VM: `cd /opt/ubyhost && git rev-parse HEAD` (and last Deploy production run id if you use Actions).

## Now

- **Owner:** finish [0007 phase 2](../tasks/0007-post-magic-link-deploy-phase2.md) **A.2–F** (browser login, `.env`, proxy verify, per-property UbyPort test, reconcile 112). Step list in [0007-report](../tasks/0007-report.md).
- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not signed off.

## Next

- After phase 2 owner steps: Doručenka smoke on a new filing; deploy #280+#281 when you want admin preview on production.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, operator `.env`, healthchecks, Better Stack, Cloudflare, retention autopurge, Render staging, Litestream/backup drill, task 0001 (#281), **production login e-mails + phase 1 deploy (Oct 2026)**.
