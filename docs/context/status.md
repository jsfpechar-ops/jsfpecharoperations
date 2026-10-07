# Status

Updated: 2026-10-07 after task 0007 phase 2 complete (owner sign-off).

## Production

- **Magic-link cutover:** phase 1 + phase 2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)). E-mail login only; `.env` admin + SES; Caddy access log off; all properties connection-tested.
- **112 reconcile:** dry run `guests answered with accepted codes only: 0` — no `--apply` needed (Oct 2026).
- Live app: `/healthz` `version` 1.1.0. Record deploy SHA when convenient: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not yet signed off.
- Optional: deploy #280+#281 (admin preview) when you want it on production.

## Next

- TTLock door codes: plan [ttlock-door-codes](../plans/ttlock-door-codes.md), facts [TTLOCK](../TTLOCK.md). Run [0008](../tasks/0008-door-codes-schema.md) then [0009](../tasks/0009-ttlock-client.md). Pilot ships without a claim check (owner, accepted risk).

- Doručenka smoke on a new filing after this cutover.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, retention autopurge, Render staging, Litestream/backup drill, task 0001 (#281), **magic-link deploy + 0007 phase 2 (Oct 2026)**.
