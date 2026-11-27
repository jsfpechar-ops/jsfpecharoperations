# Status

Updated: 2026-11-27.

## Go cutover (11-25)
- PR #1319: 2040–2085 done, `parity_gate.sh` PASS. Owner: merge #1319, deploy (autopurge off week 1).

## Production
- Magic-link 1–2 done; `/healthz` 1.1.0; Postgres + Billing ON (`COMPOSE_PROFILES=walg,monitoring,go`); SQLite rollback: pg-cutover.
- Payments retired (`UBYHOST_PAYMENTS_RETIRED`); Stripe off; code/data kept.
- Go jobs: billing_snapshot, ical, push, submit, posthog, meta_capi, deadlines. Python: mail, door_codes.
- AI: `havel,leon,guide_import` (`guide_translate` off). Backups: daily pg_dump + WAL-G 7-day PITR.

## Next
- Stay journey 5-step status (Go): [2097](../tasks/2097-go-stay-journey-5step-ses-and-manual-paths.md) done (SES email, link opened, form+housebook, TTLock-only, calm-blue auto-police + manual paths).
- Check-in auto-filing (Go): [plan](../plans/checkin-anchored-auto-filing.md), 2091–2096 done.
- 2001: invoice Wolt-simple + stay header ([brief](../tasks/2001-invoice-wolt-simple.md)); 2000: no police nags on Overview without UbyPort login.
- Comfy UX (Go): [plan](../plans/host-ux-comfy-refresh.md); 2087–2090 green (#1335).
- Go parity: **GATE: PASS** (#1319, 2040–2085); 2011–2018 (#1252).
- Go executor queue ([plan](../plans/go-cutover-executor-queue.md)): **1793**, **0852**; **1730**/**1770** wait on sidecars.
- [Autopilot](../plans/autopilot-agentic.md): A2 done (2029); A6 waits on Python retirement.
- Guest isolation ([plan](../plans/guest-form-isolation.md)): 1834-1839 (#1070); drafts #1072-1073; 1835 (#1071) after 1834; owner 1837 Q4-5.
- Entry code + guide (Go): [plan](../plans/entry-code-external-guide.md) (3 typed codes, Notion import); runnable 2032, 2035, 1668, 1664.
- CI 1413-1415, README 1416.
- Go move ([remaining](../plans/go-full-move-remaining.md), [SQLite](../plans/sqlite-retirement.md)): #1010 merged; #1021 open; W1, W1b, W6-W8 Go.
- [go-sqlite-final]: SQLite 1474-1480, Go 1700-1790 (#1081); done through 1702e1-3, next 1703, 1705.
- Go photo volume (11-14): `/data` + x/image; 1640, 1641, 1447, 1603, 1650-1652; 1597 waits on claim + `normalise_guest`.
- 1630: drop extra `guest_details_host` mail (1291 on main). Door codes 0037–0038: owner staging. TTLock 0008–0016: after §12 + lawyer (K-L).
- File-retention: decided (lawyer Terms/DPA). Login wording: 1762-1764 (blocked on 1704).

## Blocked: needs owner, lawyer or council
- Lawyer: legal texts (0005, K-L). Stale signed dates (K-F18). Filing K-F03, K-F07: AI-reviewed 11-15, not lawyer items (see go-sqlite-final §7); secrets K-S10.
- Owner: `uk` in `UBYHOST_GUEST_LANGS`; phone/passkey deploy; crawler Terms §11.

## Owner done
- SES, Turnstile, monitoring, staging, backup drill, 0001 done.
