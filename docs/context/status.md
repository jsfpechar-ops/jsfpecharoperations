# Status

Updated: 2026-10-06 by Cursor (combined magic-link + bug-fix PR). Keep each section to 5 lines or fewer.

## Production

- Live: `8809b9f` (PR #277), Deploy production run #171, 2026-10-05. Real hosts, `ubyport=prod`.
- `main` includes context rollout (#281); admin preview (#280) is in `main` but **not deployed yet.**

## Now

- Owner: review the **combined PR** (magic link 0002–0005 + today's Cursor bug fixes: #283 filing-in-flight, #289 admin preview/Litestream tests, stay-fee/UbyPort from `task/0002c`).
- Full-suite pytest still has session-order failures to fix before merge; browser e2e (25 tests) passes with 0 skipped.
- Lawyer: review LAWYER REVIEW paragraphs in task 0005 legal bump (v1.7).

## Next

- After merge and deploy: set every account login e-mail in `/admin/users` before enabling link-only login in production (0003 guard).
- Close superseded open PRs #283 and #289 once combined PR merges. Deploy #280+#281 when ready.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, operator `.env`, healthchecks, Better Stack, Cloudflare, retention autopurge, legal effective date, Umami, guest languages, Render staging, Litestream/backup drill, task 0001 context rollout (#281).
