# Status

Updated: 2026-11-06.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.
- PostgreSQL since 2026-10-31; SQLite at `/data/ubyhost.db`. Billing ON. Go off until `COMPOSE_PROFILES` + `UBYHOST_GO_JOB_KINDS`.

## Now
- 11-06: #790: OCR `tip_label` + inline-flex `help-tip` (layout-lint `help-stranded` @320); cache `20261106-pr790-ocr-tip2`. Full browser glob open. [handoff](../tasks/ux-remediation-handoff.md).
- 11-06: 0962/0963 merged (#791). **Owner:** deploy, Grafana.
- UX gate live (layout lint + AGENTS rule 10). Stripe onboarding live; extras merged. **Owner:** deploy; booking site v1 next.

## Next
- Door codes 0037–0038 on main → owner staging steps.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided, no build; lawyer Terms/DPA line.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing HIGH RISK: K-F02, K-F03, K-F07; secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; AI crawler Terms §11 confirm.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
