# Status

Updated: 2026-11-01.

## Production
- Magic-link 1–2 done; checked; access log off.
- `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now
- Signup review: 0620 Ceník copy, 0621 first screen; monthly + yearly stay.
- 2026-11-01: **Production on PostgreSQL** since 2026-10-31 23:56Z (39 s downtime; SQLite kept at `/data/ubyhost.db`, rollback `./scripts/pg-cutover.sh rollback`). Go merged, off in prod until `go` is in `COMPOSE_PROFILES` and a kind in `UBYHOST_GO_JOB_KINDS`: G1a, container, G3a billing_snapshot, G3b stripe_sweep, G5a request bytes (#621-#634). G5b responses (0480, #635). Next: G5c transport + claim (0481), G5d outcome write, G3 jobs, G2, G4 after the redesign, G6 ([plan v4](../plans/postgresql/migration-plan-v4.md)).
- #583 merged: guest save-and-continue, visible acknowledgement, contextual help. #587 open: 0452 read-only billing extract + 0454 host UX + handoff documentation.
- Billing cockpit merged (#561). 0448 merged (#565): first plan to legacy hosts (immediate start, invoice now, no trial) + trial extension 1–365 days. Decisions 2026-10-29 in decisions.md.
- Billing ON in production (`UBYHOST_BILLING_ENABLED=1`, 2026-10-29; cockpit #561, 0448 #565). Deploy manual.
- 0429 payments UX: next 0435-36 rails, 0430-34 pages (#551, #553, #554 merged).
- 0290 passkey CI/phone; #435 merge; TTLock #434 CI pending. #432 subdomain live; root login/calendar review pending.
- Foolproof 0230-0278, reset 0165-0183 (#405); phone app + alerts (0219, 0225-0229, #421). **Owner:** deploy, phone.
- Langs 0196: **Owner:** add `uk` to `UBYHOST_GUEST_LANGS`.
- AI crawler block 0195: Terms §11 TDM v1.7, lawyer to confirm. Cleaning 0104: #396 CI/staging review.
- Credential letter to data box ybndqw9. **LAWYER REVIEW** legal v1.7 (0005), if unsigned.

## Next
- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Merged 0067 (#371), 0068 (#372). Next: [0069](../tasks/0069-same-period-shared-pin.md) (K-D04). TTLock staging: issue/delete work; untested: change, calendar stays, DST.
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: Terms/DPA line, not the host's statutory archive.
- TTLock briefs 0008–0016: [plan](../plans/ttlock-door-codes.md) §11 order. Test first; live after §12 + lawyer (K-L).

## Blocked: needs owner, lawyer or council
- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.
- Decide with owner: founder-price flag on the customer page or discount-% only.

## Owner done
- SES, Turnstile, healthchecks, Better Stack, Cloudflare pre-clearance, autopurge, Render staging, backup drill, 0001 (#281) done.
