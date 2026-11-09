# Status

Updated: 2026-11-09.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Host 2026-11-09 16:56 Europe/Prague: `aa6bbbf0` (#840) on `master`, same as `origin/main`.
- Postgres cutover done. Billing ON. SQLite rollback only via existing pg-cutover scripts. `COMPOSE_PROFILES=walg,monitoring,go`.
- Go jobs = queue: billing_snapshot, stripe_sweep, ical, push, submit. Python: mail, door_codes, posthog, meta_capi, deadlines. Healthy: app, Go, worker (~1h), caddy (~2h), postgres, walg (~17h). 24h error filters empty.
- `UBYHOST_GO_PATHS`: `/api/command-palette /dashboard/calendar /payments/qr/*.png /webhooks/stripe /payments/connect/start /payments/connect/return /payments/requests/new /payments/requests/*/send /payments/requests/*/link /account/push/subscribe /account/push/refresh /account/push/unsubscribe /account/push/devices/*/delete /account/push/test /pay/*/*.png`. Rollback: drop paths, `caddy-validate.sh`, `docker compose up -d caddy`. Began `9a643d9d` (#785). No further Go slice until that code is on main.
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 on both when the owner has no IBAN.

## Now
- 11-09: 1051 stay fees compact month filter (no Apply, default = current month), draft PR on `claude/stayfees-month-filter`; cache `20261109-1051a`.
- 11-09: 1053 Stay fee card rows + centred property editor column (>=1024); cache `20261109-1053a`. PR draft, CI watched.
- 11-06: #790: OCR `tip_label` + inline-flex `help-tip` (layout-lint `help-stranded` @320); cache `20261106-pr790-ocr-tip2`. Full browser glob open. [handoff](../tasks/ux-remediation-handoff.md).
- 11-06: #791 merged. 11-07: 0990-0992 (settings throttle, PG indexes 00008, edge cache) in review. **Owner:** deploy, `pg_schema.py apply`, CF rule, Grafana.
- UX gate live (layout lint + AGENTS rule 10). Stripe onboarding live; extras merged. **Owner:** deploy; booking site v1 next.
- 11-09: backups live (daily pg_dump, WAL-G 7-day PITR); restore drills passed, repeat every 3 months.

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
