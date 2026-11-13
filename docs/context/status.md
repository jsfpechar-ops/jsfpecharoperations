# Status

Updated: 2026-11-13.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Main 11-13: `84e966f` (#962).
- Postgres cutover done. Billing ON. SQLite rollback only via pg-cutover scripts. `COMPOSE_PROFILES=walg,monitoring,go`.
- Go jobs = queue: billing_snapshot, stripe_sweep, ical, push, submit, posthog, meta_capi, deadlines (live since 11-13, healthy). Python: mail, door_codes.
- Go live, all routes on main (11-12): palette, calendar, payments QR/connect/requests, stripe webhook, push, pay PNGs — paths in [ENVIRONMENT](../ENVIRONMENT.md). Rollback: trim `UBYHOST_GO_PATHS`, `caddy-validate.sh`, `docker compose up -d caddy`. Go migration done (#934-936, #941/#942, #944/#945, #949).
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 on both when the owner has no IBAN.
- 11-12: 1172 double-booking alarm, Go-only | [1172](../tasks/1172-double-booking-alarm.md)
- 11-13: merged #946/#948/#953/#957 (DR; Hetzner copy pending), #958, #959, #962. Later: remove Python deadlines job.
- Building: 1095 head-count H1 (flag `UBYHOST_HEADCOUNT_LEAD_LIVE` off). Next: H2a, H2b, H3, H4, guest form C.
- 11-10: [Speed](../plans/speed-and-ease.md)/[group](../plans/guest-group-registration.md) overnight build: merged and auto-deployed #854-#867, #871; late-filing count was 0. Held drafts for copy review: #868 (F1 bill mail), #869 (F3 fee update mail).
- 11-07: 0990-0992 (throttle, PG indexes 00008, edge cache) in review. **Owner:** deploy, `pg_schema.py apply`, CF rule, Grafana.
- UX gate live (layout lint + AGENTS rule 10). Stripe onboarding live; extras merged. **Owner:** deploy; booking site v1 next.
- 11-09: backups live (daily pg_dump, WAL-G 7-day PITR); restore drills passed, repeat every 3 months.
- 11-08: 1032 stay-fee pay box (all ways visible) + receipt mail, draft PR; method never claimed. **Owner:** review, deploy.
- 11-13: security audit draft #966 (1200-1204). **Owner:** K-S11–K-S15.

## Next
- Go move: 97/341 routes in Go ([remaining](../plans/go-full-move-remaining.md)); briefs 1420-1459 in #1010. #982 (D1): merge with switch off; 1263 before `UBYHOST_SCHEMA_APPLY=go`.
- 1291: host CC on guest completion (#988).
- Door codes 0037–0038 on main → owner staging steps.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided, no build; lawyer Terms/DPA line.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing HIGH RISK: K-F03, K-F07; secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; AI crawler Terms §11 confirm.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
