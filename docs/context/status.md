# Status

Updated: 2026-10-29.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now
- Billing cockpit merged (#561). 0448 merged (#565): first plan to legacy hosts (immediate start, invoice now, no trial) + trial extension 1–365 days. Decisions 2026-10-29 in decisions.md.
- Billing ON in production (`UBYHOST_BILLING_ENABLED=1`, 2026-10-29; cockpit #561, 0448 #565). Deploy manual.
- 0429 payments UX (CI browser row pending). Next: 0435-36 rails, 0430-34 pages. Plan #551, rails #553, fix #554 merged.
- Billing 0411-0419 in #528, off. 0410 cards #517. Havel 0391/0395, 0394, 0400: #513/#520, #518, #515.
- Guide + Leon 0341-0355: owner merges #465-468. 0403-0405 in review.
- 0291-0302 buttons, fees, invoice. **Owner:** PR; CF rules 3-4.
- 0290 passkey CI/phone; #435 merge; TTLock #434 CI pending. #432 subdomain live; root login/calendar review pending.
- 0280-0283 alerts, borders, signature; 0253 layout tests. **Owner:** PR/deploy/phone, iPad.
- Foolproof 0230-0278, reset 0165-0183 (#405); phone app + alerts (0219, 0225-0229, #421). **Owner:** deploy, phone.
- #418 onboarding fixes; address open. Stay-fee email 0220-0224: owner staging test. Data box send on hold (DIA).
- Langs 0196: vi host app, uk guest form. **Owner:** add `uk` to `UBYHOST_GUEST_LANGS`; deploy.
- AI crawler block 0195: Terms §11 TDM v1.7, lawyer to confirm. Cleaning 0104: #396 CI/staging review.
- Check `/healthz`; credential letter to data box ybndqw9. Lawyer: **LAWYER REVIEW** legal v1.7 (0005), if unsigned.

## Next
- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Merged 0067 (#371), 0068 (#372). Next: [0069](../tasks/0069-same-period-shared-pin.md) (K-D04). TTLock staging: issue/delete work; untested: change, calendar stays, DST.
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: Terms/DPA line, not the host's statutory archive.
- TTLock briefs 0008–0016: [plan](../plans/ttlock-door-codes.md) §11 order. Test first; live after §12 + lawyer (K-L).

## Blocked: needs owner, lawyer or council
- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.
- Decide with owner: founder-price flag on the customer page or discount-% only.

## Owner done
- SES, Turnstile, healthchecks, Better Stack, Cloudflare pre-clearance, autopurge, Render staging, backup drill, 0001 (#281) done.
