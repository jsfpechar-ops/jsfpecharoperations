# Status

Updated: 2026-11-06.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now
- 11-06: #790: 0991 CI fixes on handoff branch (page-help modal, alerts, lock off, a11y, locators). Awaiting green then merge. [report](../tasks/0988-report.md).
- 11-06: 0962 prune, 0963 log `kind=` merged (#791). **Owner:** deploy, 0962 Grafana steps.
- 2026-11-04: 0949 paste card removed (part B open): [report](../tasks/0949-report.md).
- 11-05: #786 filters implemented; validation blocked (workspace): [report](../tasks/0950-fix-1-report.md).
- 2026-11-04: brief 0930 in review (PR #768): stay bars end mid departure day.
- 2026-11-03: UX gate live: layout lint (`App/tests/layout_lint.js`) + AGENTS.md rule 10; threads self-check screenshots, owner does not.
- 2026-11-02: Airbnb pass on login and admin pages (0892-0894) in draft PR #739; 0869 renumbers colliding briefs.
- 2026-11-01: **PostgreSQL** in prod since 2026-10-31 (SQLite kept at `/data/ubyhost.db`; rollback `./scripts/pg-cutover.sh rollback`). Go jobs off until enabled via `COMPOSE_PROFILES` / `UBYHOST_GO_JOB_KINDS` (batch #621-#640, 0482). Next: G5d-2+ ([plan v4](../plans/postgresql/migration-plan-v4.md)).
- Billing ON in production (`UBYHOST_BILLING_ENABLED=1`, 2026-10-29; #561, #565).
- Stripe: onboarding live; extras merged (#701, #705, #706). **Owner:** deploy. Next: booking site v1.
- 0290 passkey CI/phone; #435 merge; TTLock #434 CI pending. #432 subdomain live; root login/calendar review pending.
- Foolproof 0230-0278, reset 0165-0183 (#405); phone app + alerts (0219, 0225-0229, #421). **Owner:** deploy, phone.
- Langs 0196: vi host app, uk guest form. **Owner:** add `uk` to `UBYHOST_GUEST_LANGS`; deploy.
- AI crawler block 0195: Terms §11 TDM v1.7, lawyer to confirm. Cleaning 0104: #396 CI/staging review.
- Credential letter to data box ybndqw9. **LAWYER REVIEW** legal v1.7 (0005), if unsigned.

## Next
- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: Terms/DPA line, not the host's statutory archive.
- TTLock briefs 0008–0016: [plan](../plans/ttlock-door-codes.md) §11 order. Test first; live after §12 + lawyer (K-L).

## Blocked: needs owner, lawyer or council
- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
