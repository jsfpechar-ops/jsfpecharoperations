# Status

Updated: 2026-11-09.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.
- Postgres cutover done (since 2026-10-31). Billing ON. SQLite file remains; rollback only through the existing pg-cutover scripts.
- Go is up (`COMPOSE_PROFILES` includes go). Go jobs: billing_snapshot, stripe_sweep, ical, push, submit. Python worker: mail, door_codes, posthog, meta_capi, deadlines.
- HTTP on Go via `UBYHOST_GO_PATHS` (6a–8). Rollback: remove those paths, `./scripts/caddy-validate.sh`, `docker compose up -d caddy`. Cutover began at `9a643d9d` (#785). No further Go route or job cutover until that code is on main. Server HEAD after later deploys was not read from this chat.
- AI on: havel, leon, guide_translate. Stripe mode test. Guest QR: Python and Go both 404 when the owner has no IBAN; no live bank-account QR checked yet.

## Now
- 11-09: 1051 stay fees compact month filter (no Apply, default = current month), draft PR on `claude/stayfees-month-filter`; cache `20261109-1051a`.
- 11-09: 1053 Stay fee card rows + centred property editor column (>=1024); cache `20261109-1053a`. PR draft, CI watched.
- 11-06: #790: OCR `tip_label` + inline-flex `help-tip` (layout-lint `help-stranded` @320); cache `20261106-pr790-ocr-tip2`. Full browser glob open. [handoff](../tasks/ux-remediation-handoff.md).
- 11-06: #791 merged. 11-07: 0990-0992 (settings throttle, PG indexes 00008, edge cache) in review. **Owner:** deploy, `pg_schema.py apply`, CF rule, Grafana.
- UX gate live (layout lint + AGENTS rule 10). Stripe onboarding live; extras merged. **Owner:** deploy; booking site v1 next.
- 11-08: backups PR #805 (1020-1023) in review: daily S3, Litestream removed, WAL-G sidecar + PITR runbook. **Owner:** WAL-G needs .env.walg + IAM + quiet-hour deploy; restore drill before trusting it.

- 11-08: 1032 stay-fee pay box (no radios, all ways visible) + receipt mail with total and calculation, draft PR. Method used is never claimed (app cannot know). **Owner:** review, deploy.

## Next
- Door codes 0037–0038 on main → owner staging steps.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided, no build; lawyer Terms/DPA line.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing HIGH RISK: K-F02, K-F03, K-F07; secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; AI crawler Terms §11 confirm.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
