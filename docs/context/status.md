# Status

<<<<<<< HEAD
Updated: 2026-10-06 by Cursor (task 0002 report). Keep each section to 5 lines or fewer.
=======
Updated: 2026-10-06 (police answers on UbyPort, branch `fix/ubyport-police-answers`). Keep each section to 5 lines or fewer.
>>>>>>> bd0feb3 (Stop treating late filings as failures and stop resending refused records)

## Production

- Live: `8809b9f` (PR #277), Deploy production run #171, 2026-10-05. Real hosts, `ubyport=prod`.
- `main` includes context rollout (#281); admin preview (#280) is in `main` but **not deployed yet.**

## Now

<<<<<<< HEAD
- Owner: review and merge **task 0002** PR (`task/0002-account-emails`) — login e-mail on every account (magic-link plan step 1).
- Other agent: police / stay-fee brief on `task/0002c-ubyport-severity` (separate from magic link).
- Task 0005 legal texts (e-mail login + passkeys, v1.7) implemented on `cursor/legal-texts-1.7-d5e1`; awaiting lawyer review of LAWYER REVIEW paragraphs.
=======
- Owner: review and merge the police-answers PR (HIGH RISK filing: 112 is now an accept, refused records are sent once). Then deploy and press **Refresh code lists** on every production property.
- Owner: Phase 4 test filing on Lightsail staging with the UBY-WS test account (`deploy/lightsail/README.md`, "Filing against the police test environment"). Then K-F13 data check.
- Owner: run task [0001](../tasks/0001-context-rollout.md) step 12 with `APPLY=1` to close the 40 listed stale PRs (keep #278 and #279 open).
>>>>>>> bd0feb3 (Stop treating late filings as failures and stop resending refused records)

## Next

- After 0002 deploy: fill every account e-mail in `/admin/users`, then run 0003+0004+0005 (one release) per `docs/docs/plans/magic-link-passkeys/HANDOFF.md`.
- Owner: deploy `main` (#280 + #281) and check Doručenka download on a new filing when ready.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and existing K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, operator `.env`, healthchecks, Better Stack, Cloudflare, retention autopurge, legal effective date, Umami, guest languages, Render staging, Litestream/backup drill, task 0001 context rollout (#281).
