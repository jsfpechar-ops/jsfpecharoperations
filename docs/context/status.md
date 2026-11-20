# Status

Updated: 2026-11-17.

## Production
- Magic-link 1–2 done; access log off. `/healthz` 1.1.0. Main 11-13: `84e966f` (#962).
- Postgres live. Billing ON. `COMPOSE_PROFILES=walg,monitoring,go`. SQLite rollback via pg-cutover only.
- Go jobs = queue (billing_snapshot, stripe_sweep, ical, push, submit, posthog, meta_capi, deadlines). Python: mail, door_codes.
- Go routes live: [ENVIRONMENT](../ENVIRONMENT.md). Rollback: trim `UBYHOST_GO_PATHS`, reload caddy.
- AI: `havel,leon,guide_import` (`guide_translate` off). Stripe test. Guest QR 404 without IBAN. Review: [plan](../plans/ai-payments-hardening.md).
- Later: remove Python deadlines job.
- UX gate and Stripe onboarding live. Backups: daily pg_dump + WAL-G 7-day PITR (drill every 3 mo).
- 11-13 merges, head-count H1, security audit #966: [archive](../plans/status-archive-2026-11.md).

## Next
- Go executor queue ([plan](../plans/go-cutover-executor-queue.md)): runnable **1793**, **0852**; **1730** / **1770** blocked until exact-diff sidecars.
- [Autopilot](../plans/autopilot-agentic.md): hide Payments first.
- Guest isolation ([plan](../plans/guest-form-isolation.md)): 1834-1839 (#1070); drafts #1072-1073 (1830, 1834); 1835 (#1071) after 1834. Owner: 1837 Q4-5.
- Entry code + guide (Go): [plan](../plans/entry-code-external-guide.md). Runnable 1660, 1663, 1668; 1661→1662, 1664; 1665-1667 wait on property-settings and guest-pages ports.
- CI 1413-1415, README 1416.
- Go move ([remaining](../plans/go-full-move-remaining.md), [SQLite](../plans/sqlite-retirement.md)): #1010 merged 11-14. PR #1021 open. Server 11-15: W1, W1b, W6-W8 on Go; W3 rolled back; retention dry-run.
- [go-sqlite-final]: SQLite 1474-1480, Go 1700-1790 (#1081). Done through 1702e1-3; Next: 1703, 1705.
- Go photo volume (11-14): writable `/data` + x/image. Order: 1640, 1641, 1447, 1603; 1650-1652 (ports for 1597). 1597 waits on guest claim and `normalise_guest` ports.
- 1630: drop the extra `guest_details_host` mail (1291 on main).
- Door codes 0037–0038 on main: owner staging.
- TTLock 0008–0016: [plan](../plans/ttlock-door-codes.md) §11; live after §12 + lawyer (K-L).
- File-retention: decided; lawyer Terms/DPA line.
- Login wording: 1762 (Face ID / device labels), 1763 (auto-open), 1764 (Settings wording, blocked on 1704); after 1760, exact-diff pass first.
- Stays Go-only: 1855-1858; `/reservations` in `UBYHOST_GO_PATHS` after 1856.

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing K-F03, K-F07: AI-reviewed 11-15, not lawyer items (see go-sqlite-final §7); secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; crawler Terms §11.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
