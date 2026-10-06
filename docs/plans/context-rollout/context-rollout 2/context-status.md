# Status

Updated: 2026-10-06 by the orchestrator. Keep each section to 5 lines or fewer.

## Production

- Live: `8809b9f` (PR #277), Deploy production run #171, 2026-10-05. Real hosts, `ubyport=prod`.
- `main` is at `d72c870` (PR #280, admin preview unmask). **Not deployed yet.**

## Now

- Task [0001](../tasks/0001-context-rollout.md): context system rollout (archive, CI lint, PR and branch cleanup). Executor: Cursor.

## Next

- The magic link + passkeys plan. The owner is still planning it; it will be the first plan in this workflow. Don't start it until he says so.
- Owner: deploy `main` (#280) and check the Doručenka download on a new filing.

## Blocked: needs owner, lawyer or council

- Lawyer review of the legal texts: deletion 30+30 days, retention anchor, acceptance-row deletion, under-15 signatures, ID copies. See the K-L rows in [known-issues](known-issues.md).
- Stale signed dates (old plan items T48–T50): keep the current safety net or restore re-signing? Owner decision (K-F18).
- HIGH RISK filing items left open on purpose: K-F02, K-F03, K-F07. Owner: confirm the secret key was rotated after the leak (K-S10).

## Owner steps already done (don't ask again)

- SES mail, Turnstile, the operator identity in `.env`, healthchecks.io (submit, iCal, mail, backup, filing), Better Stack uptime, Cloudflare + trusted proxy CIDRs, `UBYHOST_RETENTION_AUTOPURGE=1`, legal effective date, Umami, guest languages, Render staging.
- Litestream → S3 (SSE-S3), with a restore drill passed. Nightly `age`-encrypted backup. Lightsail 8 GB.
