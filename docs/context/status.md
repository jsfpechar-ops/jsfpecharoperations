# Status

Updated: 2026-10-06 after merging `main` into PR #288. Keep each section to 5 lines or fewer.

## Production

- Live: `8809b9f` (PR #277), Deploy production run #171, 2026-10-05. Real hosts, `ubyport=prod`.
- `main` includes context rollout (#281); admin preview (#280) is in `main` but **not deployed yet.**

## Now

- Owner: review **[#288](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/288)** (magic link 0002–0005, police/stay-fee 0002 brief, filing-in-flight fix). Full-suite pytest still needs green before merge.
- Lawyer: **LAWYER REVIEW** paragraphs in task 0005 (legal v1.7).
- Owner: task [0001](../tasks/0001-context-rollout.md) step 12 with `APPLY=1` when ready (keep #278 and #279 open).

## Next

- After #288 deploy: set every login e-mail in `/admin/users`; run `reconcile_accepted_codes.py` per [0002-police brief](../tasks/0002-police-downloads-stayfee.md).
- Deploy #280+#281 when ready; test Doručenka on a new filing.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, operator `.env`, healthchecks, Better Stack, Cloudflare, retention autopurge, legal effective date, Umami, guest languages, Render staging, Litestream/backup drill, task 0001 context rollout (#281).
