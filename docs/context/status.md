# Status

Updated: 2026-10-25.

## Production

- Magic-link phases 1–2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)); login, admin/SES, access log off, properties tested.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- 0391 Open buttons are real links (stays row Open did nothing). **Owner:** merge PR, deploy (`?v=`).

- 0377 sidebar slide: owner PR.
- Guide + Leon 0341-0355: owner merges #465-#468, evals.
- 0291-0302 buttons/fee steps/invoice/copy. **Owner:** PR; CF rules 3-4.
- 0290: passkey CI/phone pending.
- Check-in alerts #435: tests pass; owner merge/deploy.
- TTLock disclosure #434: timing/geometry CI pending.
- #432 subdomain deployed; root login/calendar review pending.

- 0280-0283 short alerts, card borders, signature dialog. **Owner:** PR/deploy/phone test.
- 0253 four red layout tests. **Owner:** review 0253 PR, iPad.
- Foolproof 0230-0278, design reset 0165-0183 (#405). **Owner:** deploy (`?v=` keys).
- Phone app + urgent alerts (0219, 0225-0229, #421). **Owner:** deploy, test on iPhone and Android.
- #418 onboarding fixes 0203-0212; address open.
- Stay-fee email 0220-0224: built, owner staging test.
- 0203 #419: fee list pay steps. Data box send on hold (DIA).
- #416: lock tab, stay buttons, phone pass (0196-0201).
- Langs 0196: vi host app, uk guest form. **Owner:** add `uk` to `UBYHOST_GUEST_LANGS`; deploy (`?v=`).
- AI crawler block 0195: Terms §11 TDM v1.7, lawyer to confirm.
- Cleaning 0104: #396 CI/staging review pending ([brief](../tasks/0104-cleaning-management.md)); calendar 0103 on main.

- Check `/healthz`; credential letter to data box ybndqw9.
- Lawyer: **LAWYER REVIEW** legal v1.7 (0005), if unsigned.

## Next

- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Merged 0067 (#371) and 0068 (#372). TTLock answered all questions ([TTLOCK](../TTLOCK.md#what-ttlock-support-confirmed-2026-10-12)). Next: [0069](../tasks/0069-same-period-shared-pin.md), same-hours rebooking must not reuse a PIN (K-D04).
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: add a Terms/DPA line that the app is not the host's statutory archive.

- TTLock briefs 0008–0016: [plan](../plans/ttlock-door-codes.md) §11 order (0016 after 0010). Test first; live after §12 acceptance + lawyer (K-L).

- Doručenka smoke on a new filing after this cutover.
- TTLock staging (2026-10-08/10): issue and delete work, code opened the lock. Untested: change, calendar stays, DST.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner done

- SES, Turnstile, healthchecks, Better Stack, Cloudflare pre-clearance (23 Oct), autopurge, Render staging, backup drill, 0001 (#281) done.
