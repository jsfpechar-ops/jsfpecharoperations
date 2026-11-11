# Status

Updated: 2026-11-11.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Host 2026-11-09 16:56 Europe/Prague: `aa6bbbf0` (#840) on `master`, same as `origin/main`.
- Postgres cutover done. Billing ON. SQLite rollback only via existing pg-cutover scripts. `COMPOSE_PROFILES=walg,monitoring,go`.
- Go jobs = queue: billing_snapshot, stripe_sweep, ical, push, submit. Python: mail, door_codes, posthog, meta_capi, deadlines. Healthy: app, Go, worker (~1h), caddy (~2h), postgres, walg (~17h). 24h error filters empty.
- Go slice live (#785 `9a643d9d`): palette, calendar, payments QR/connect/requests, stripe webhook, push, pay PNGs — paths in [ENVIRONMENT](../ENVIRONMENT.md). Rollback: trim `UBYHOST_GO_PATHS`, `caddy-validate.sh`, `docker compose up -d caddy`. Hold further slices until main catches up.
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 on both when the owner has no IBAN.

## Now
- 11-10 live: 1085/1086 police letter paste (#882, #892); 1089/1090 under-15 signature (#885, #888); 1091/1093 short guest titles (#883, #887); 1092 head-count single writer (#884); 1094 H0 check (#893); 1096 Save row, leave warning (#894).
- 11-11: guest-details mail: briefs 1120-1123b, see docs/plans.
- Building: 1095 head-count H1 (flag `UBYHOST_HEADCOUNT_LEAD_LIVE` off). Next: H2a, H2b, H3, H4, guest form C.
- 11-10: 1092 demo full coverage, PR #886.
- 11-10: [Speed](../plans/speed-and-ease.md)/[group](../plans/guest-group-registration.md) overnight build: merged and auto-deployed #854-#867, #871; late-filing count was 0. Held drafts for copy review: #868 (F1 bill mail), #869 (F3 fee update mail).
- 11-09: 1051 stay-fee month filter (cache `20261109-1051a`), 1053 stay-fee rows + centred editor (`20261109-1053a`): draft PRs.
- 11-07: 0990-0992 (throttle, PG indexes 00008, edge cache) in review. **Owner:** deploy, `pg_schema.py apply`, CF rule, Grafana.
- UX gate live (layout lint + AGENTS rule 10). Stripe onboarding live; extras merged. **Owner:** deploy; booking site v1 next.
- 11-09: backups live (daily pg_dump, WAL-G 7-day PITR); restore drills passed, repeat every 3 months.
- 11-08: 1032 stay-fee pay box (all ways visible) + receipt mail, draft PR; method never claimed. **Owner:** review, deploy.

## Next
- Door codes 0037–0038 on main → owner staging steps.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided, no build; lawyer Terms/DPA line.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing HIGH RISK: K-F02, K-F03, K-F07; secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; AI crawler Terms §11 confirm.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
