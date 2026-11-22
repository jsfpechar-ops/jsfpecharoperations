# Status

Updated: 2026-11-22.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Main 11-13: `84e966f` (#962).
- Postgres live. Billing ON. `COMPOSE_PROFILES=walg,monitoring,go`. SQLite rollback via pg-cutover only.
- Go jobs = queue (billing_snapshot, stripe_sweep, ical, push, submit, posthog, meta_capi, deadlines). Python: mail, door_codes.
- Go routes: [ENVIRONMENT](../ENVIRONMENT.md). Rollback: trim `UBYHOST_GO_PATHS`, reload caddy. Stay detail on Python (K-O07: `/reservations/*[0-9]` off; list = exact `/reservations` only).
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 without IBAN. Review: [plan](../plans/ai-payments-hardening.md).
- Later: remove Python deadlines job. UX gate + Stripe onboarding live. Backups: daily pg_dump + WAL-G 7-day PITR (drill every 3 mo).

## Next
- 2001: invoice Wolt-simple + Generate invoice on stay header ([brief](../tasks/2001-invoice-wolt-simple.md)).
- 2000: no police nags on Overview without UbyPort login.
- Briefs 1865 (staging auto-deploy; prod manual) + 1866 (CI/GitHub hardening).
- Go executor queue ([plan](../plans/go-cutover-executor-queue.md)): runnable **1793**, **0852**; **1730**/**1770** blocked on sidecars.
- [Autopilot](../plans/autopilot-agentic.md): hide Payments first.
- Guest isolation ([plan](../plans/guest-form-isolation.md)): 1834-1839 (#1070); drafts #1072-1073; 1835 (#1071) after 1834; owner 1837 Q4-5.
- Entry code + guide (Go): [plan](../plans/entry-code-external-guide.md); runnable 1660, 1663, 1668, 1661→1662, 1664; 1665-1667 wait on ports.
- CI 1413-1415, README 1416. Go move ([remaining](../plans/go-full-move-remaining.md), [SQLite](../plans/sqlite-retirement.md)): #1010 merged; #1021 open; W1, W1b, W6-W8 on Go, W3 rolled back.
- [go-sqlite-final]: through 1702e1-3, next 1703, 1705. Photo volume: 1640, 1641, 1447, 1603, 1650-1652; 1597 waits.
- Door codes 0037–0038 on main: owner staging. TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided; lawyer Terms/DPA. Login wording: 1762-1764 (blocked on 1704).
- Stays: exact `/reservations` only; do not add `/reservations/*[0-9]` until K-O07 cleared on staging.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing K-F03, K-F07: AI-reviewed 11-15 (go-sqlite-final §7); secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; crawler Terms §11.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
