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

- Briefs ready for Cursor: [0017](../tasks/0017-archive-stay-on-page.md) (archive keeps you on the page), [0018](../tasks/0018-funnel-dashboard.md) (funnel dashboard).
- Plan [file-retention](../plans/file-retention.md): owner to choose Path R (archive export + storage module, no deletion; recommended) or Option B (deletion, lawyer first).

- TTLock door codes: briefs 0008 to 0016 in [ttlock-door-codes](../plans/ttlock-door-codes.md) §11, run in order (0016 any time after 0010). Test mode first; live only after the §12 acceptance test and the lawyer (K-L row).

- Doručenka smoke on a new filing after this cutover.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, retention autopurge, Render staging, Litestream/backup drill, task 0001 (#281), **magic-link deploy + 0007 phase 2 (Oct 2026)**.
