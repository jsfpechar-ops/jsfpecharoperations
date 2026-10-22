# Status

Updated: 2026-10-22.

## Production


- **Magic-link:** phases 1–2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)); e-mail login, `.env` admin/SES, access log off, properties tested.
- Live app `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- 0250-0252 Open cues, iPad menu, Back fix. **Owner:** PR, iPad.
- 0253 four red layout tests fixed (stay panel phone padding, invoice Remove height, stale tests, SW blocks page.route). WebKit runs in cloud. **Owner:** review PR.
- Foolproof workflow: round 1 (0230-0237) and round 2 (0239-0248: "What needs you" card, health check, day-before nudge, one-button mails; missing setup is amber, not red). **Owner:** review PRs, merge, deploy (`?v=` keys).
- Phone app + urgent alerts (0219, 0225-0229, #421). **Owner:** deploy, test on iPhone and Android.
- #418 onboarding fixes 0203-0212; address open.
- Stay-fee email 0220-0224: built, owner staging test.
- 0203 #419: fee list pay steps. Data box send on hold (DIA).
- #416: lock tab, stay buttons, phone pass (0196-0201).
- Langs 0196: vi host app, uk guest form. **Owner:** add `uk` to `UBYHOST_GUEST_LANGS`; deploy (`?v=`).
- AI crawler block (0195): robots.txt, tdmrep.json, Terms §11 TDM (v1.7; lawyer to confirm).
- Design reset follow-up 0165-0183 (PR #405). **Deploy:** new `?v=` keys.
- Cleaning 0104: #396 CI/staging review pending ([brief](../tasks/0104-cleaning-management.md)); calendar 0103 on main.

- Check production `/healthz`. The credential letter goes to data box ybndqw9.
- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not yet signed off.

## Next


- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Merged 0067 (#371) and 0068 (#372). TTLock answered all questions ([TTLOCK](../TTLOCK.md#what-ttlock-support-confirmed-2026-10-12)). Next: [0069](../tasks/0069-same-period-shared-pin.md), same-hours rebooking must not reuse a PIN (K-D04).
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: add a Terms/DPA line that the app is not the host's statutory archive.

- TTLock door codes: briefs 0008 to 0016 in [ttlock-door-codes](../plans/ttlock-door-codes.md) §11, run in order (0016 any time after 0010). Test mode first; live only after the §12 acceptance test and the lawyer (K-L row).

- Doručenka smoke on a new filing after this cutover.
- TTLock staging (2026-10-08/10): issue and delete work, code opened the lock. Untested: change, calendar stays, DST.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner done

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, autopurge, Render staging, backup drill, 0001 (#281), magic-link/0007 phase 2 (Oct 2026).

