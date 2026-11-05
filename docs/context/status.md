# Status

Updated: 2026-11-05.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.
- Billing ON (`UBYHOST_BILLING_ENABLED=1`, 10-29; cockpit #561, 0448 #565).
- **PostgreSQL** since 10-31 23:56Z; SQLite kept at `/data/ubyhost.db` (rollback `./scripts/pg-cutover.sh rollback`).

## Now
- 11-05: PR #786 owner decisions recorded; mobile Stays filters implemented, validation blocked by workspace startup: [report](../tasks/0950-fix-1-report.md).
- 11-04: 0949 paste card removed (part B open): [report](../tasks/0949-report.md). PR #763 stay fee: 0897, 0898, 0932-0934 done; merging on green.
- 11-04: brief 0930 in review (PR #768): stay bars end mid departure day.
- 11-03: UX gate live: layout lint (`App/tests/layout_lint.js`) + AGENTS.md rule 10; owner does not review UX.
- 11-02: Airbnb pass on login/admin (0892-0894) in draft PR #739; 0869 renumbers colliding briefs.
- 11-01: Go merged, off in prod until `go` is in `COMPOSE_PROFILES` and kinds in `UBYHOST_GO_JOB_KINDS`. Done: G1a, container, G3a, G3b, G5a-G5d-1 (#621-#640, 0482). Next: G5d-2 onward ([plan v4](../plans/postgresql/migration-plan-v4.md)).

## Next
- Door codes 0037 and 0038 on main; next: owner steps on staging.
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: Terms/DPA line, not the host's statutory archive.
- TTLock briefs 0008–0016: [plan](../plans/ttlock-door-codes.md) §11 order. Test first; live after §12 + lawyer (K-L).

## Owner
- Stripe onboarding + extras (#701, #705, #706): deploy; booking site v1 next. 0290 passkey CI/phone; #435 merge; TTLock #434 CI pending. #432 subdomain live; root login/calendar review pending.
- Foolproof 0230-0278, reset 0165-0183 (#405); phone app + alerts (0219, 0225-0229, #421): deploy, phone.
- Langs 0196: add `uk` to `UBYHOST_GUEST_LANGS`; deploy. AI crawler block 0195: Terms §11 TDM v1.7, lawyer to confirm. Cleaning 0104: #396 CI/staging review. Credential letter to data box ybndqw9.
- **LAWYER REVIEW** legal v1.7 (0005), if unsigned.

## Blocked: needs owner, lawyer or council
- Lawyer review of legal texts (0005, K-L rows in [known-issues](known-issues.md)). Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner done
- SES, Turnstile, healthchecks, Better Stack, Cloudflare pre-clearance, autopurge, Render staging, backup drill, 0001 (#281).
