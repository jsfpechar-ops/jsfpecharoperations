# Status

Updated: 2026-10-31.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now
- 2026-10-31: owner decided PostgreSQL now and the Go port now. Plan [migration-plan-v4](../plans/postgresql/migration-plan-v4.md); briefs 0457–0459 ready; #592 open, 0 reviews, needs steps 4–6 of the plan before merge. **Owner:** decisions D1–D4 in the plan.
- #583 merged: guest save-and-continue, visible acknowledgement, contextual help. #587 open: 0452 read-only billing extract + 0454 host UX + handoff documentation.
- Billing cockpit merged (#561). 0448 merged (#565): first plan to legacy hosts (immediate start, invoice now, no trial) + trial extension 1–365 days. Decisions 2026-10-29 in decisions.md.
- Billing ON in production (`UBYHOST_BILLING_ENABLED=1`, 2026-10-29; cockpit #561, 0448 #565). Deploy manual.
- 0429 payments UX (CI browser row pending). Next: 0435-36 rails, 0430-34 pages. Plan #551, rails #553, fix #554 merged.
- 0290 passkey CI/phone; #435 merge; TTLock #434 CI pending. #432 subdomain live; root login/calendar review pending.
- Foolproof 0230-0278, reset 0165-0183 (#405); phone app + alerts (0219, 0225-0229, #421). **Owner:** deploy, phone.
- Langs 0196: vi host app, uk guest form. **Owner:** add `uk` to `UBYHOST_GUEST_LANGS`; deploy.
- AI crawler block 0195: Terms §11 TDM v1.7, lawyer to confirm. Cleaning 0104: #396 CI/staging review.
- Check `/healthz`; credential letter to data box ybndqw9. Lawyer: **LAWYER REVIEW** legal v1.7 (0005), if unsigned.

## Next
- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Merged 0067 (#371), 0068 (#372). Next: [0069](../tasks/0069-same-period-shared-pin.md) (K-D04). TTLock staging: issue/delete work; untested: change, calendar stays, DST.
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: Terms/DPA line, not the host's statutory archive.
- TTLock briefs 0008–0016: [plan](../plans/ttlock-door-codes.md) §11 order. Test first; live after §12 + lawyer (K-L).

## Blocked: needs owner, lawyer or council
- PostgreSQL #592: unreviewed; D1 managed vs self-hosted blocks step 6.
- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.
- Decide with owner: founder-price flag on the customer page or discount-% only.

## Owner done
- SES, Turnstile, healthchecks, Better Stack, Cloudflare pre-clearance, autopurge, Render staging, backup drill, 0001 (#281) done.
