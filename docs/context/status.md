# Status

Updated: 2026-11-14.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Main 11-13: `84e966f` (#962).
- Postgres live. Billing ON. `COMPOSE_PROFILES=walg,monitoring,go`. SQLite rollback via pg-cutover only.
- Go jobs = queue (billing_snapshot, stripe_sweep, ical, push, submit, posthog, meta_capi, deadlines). Python: mail, door_codes.
- Go routes live (11-12): see [ENVIRONMENT](../ENVIRONMENT.md). Rollback: trim `UBYHOST_GO_PATHS`, caddy reload.
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 without IBAN.
- 11-13: #946/#948/#953/#957 (DR; Hetzner copy pending), #958, #959, #962. Remove Python deadlines job later.
- 1095 head-count H1 (`UBYHOST_HEADCOUNT_LEAD_LIVE` off). Next: H2a–H4, guest form C.
- UX gate live. Stripe onboarding live. Backups: daily pg_dump + WAL-G 7-day PITR (drill every 3 mo).
- 11-13: security audit draft #966 (1200-1204). **Owner:** K-S11–K-S15. 0990-0992: deploy, `pg_schema.py apply`, CF, Grafana.

## Next
- CI 1413-1415, README 1416.
- Go move ([remaining](../plans/go-full-move-remaining.md), [SQLite](../plans/sqlite-retirement.md)): #1010 has 1263, 1470-1473, 1450-1452, 1440-1446, 1420-1427, 1430-1435, switched off. Left: 1448, 1436, 1437, review, green CI. Next: 1501, 152x-162x. Server 11-13: W1-W3 on Go, retention dry-run.
- 1291 host CC is on main; 1630 stops the extra `guest_details_host` mail (only completion + CC).
- Door codes 0037–0038 on main → owner staging steps.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided; lawyer Terms/DPA line.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing HIGH RISK: K-F03, K-F07; secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; crawler Terms §11.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
