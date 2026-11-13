# Status

Updated: 2026-11-13.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Main 11-13: `748098d9` (#957).
- Postgres cutover done. Billing ON. SQLite rollback only via pg-cutover scripts. `COMPOSE_PROFILES=walg,monitoring,go`.
- Go jobs = queue: billing_snapshot, stripe_sweep, ical, push, submit, posthog, meta_capi, deadlines (live since 11-13, healthy). Python: mail, door_codes.
- Go live, all routes on main (11-12): palette, calendar, payments QR/connect/requests, stripe webhook, push, pay PNGs — paths in [ENVIRONMENT](../ENVIRONMENT.md). Rollback: trim `UBYHOST_GO_PATHS`, `caddy-validate.sh`, `docker compose up -d caddy`. Go migration done (#934-936, #941/#942, #944/#945, #949).
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 on both when the owner has no IBAN.

## Now
- 11-13: DR steps 3/5/6/7 merged (#946, #948, #953, #957; Hetzner copy awaits owner and lawyer). Open drafts: #958 (DR decision 4 wording), #959 (no-report stays leave filing watch), stuck-queued-job alert (building). Later: remove Python deadlines code.
- 11-10 live: 1085/1086 police letter paste (#882, #892); 1089/1090 under-15 signature (#885, #888); 1091/1093 short guest titles (#883, #887); 1092 head-count single writer (#884); 1094 H0 check (#893); 1096 Save row, leave warning (#894).
- Building: 1095 head-count H1 (flag `UBYHOST_HEADCOUNT_LEAD_LIVE` off). Next: H2a, H2b, H3, H4, guest form C.
- 11-10: [Speed](../plans/speed-and-ease.md)/[group](../plans/guest-group-registration.md) overnight build: merged and auto-deployed #854-#867, #871; late-filing count was 0. Held drafts for copy review: #868 (F1 bill mail), #869 (F3 fee update mail).
- 11-07: 0990-0992 (throttle, PG indexes 00008, edge cache) in review. **Owner:** deploy, `pg_schema.py apply`, CF rule, Grafana.
- UX gate live (layout lint + AGENTS rule 10). Stripe onboarding live; extras merged. **Owner:** deploy; booking site v1 next.
- 11-09: backups live (daily pg_dump, WAL-G 7-day PITR); restore drills passed, repeat every 3 months.
- 11-08: 1032 stay-fee pay box (all ways visible) + receipt mail, draft PR; method never claimed. **Owner:** review, deploy.

## Next
- Door codes 0037–0038 on main → owner staging steps.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided, no build; lawyer Terms/DPA line.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing HIGH RISK: K-F03, K-F07; secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; AI crawler Terms §11 confirm.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
