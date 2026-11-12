# Known issues

**HR**: owner decides.

**Sources:** [map](known-issue-sources.md).

| ID | Sev/status | Where | Issue | Src |
|---|---|---|---|---|
| K-DOM01 | Pending | App URLs | CI + phone check | owner |
| K-F01 | High open | reporting.py:1356-1413, ubyport/client.py:166 | Non-401 4xx retried each sweep, uncapped | P A28-29 |
| K-F02 | Closed (#933, 11-12) | icalsync.py, go/internal/ical | Date move/cancel ignored submission_claim. Fixed in PR #933 (1143 guard, 1136 locks, 1138 claim re-check, 1139 cancel) | P A24 |
| K-F03 | Med open HR | icalsync.py ~805-830 | Lone vanished future booking stays "suspect" forever | P A19 |
| K-F04 | Med open | icalsync.py | Duplicate feeds: two stays, one overdue forever | P A22 |
| K-F05 | Med open | icalsync.py, routes/admin.py | Manual and scheduled sync clash on UNIQUE; loser marked error | P A23 |
| K-F06 | Med open | validation.py country_codes() | Some police country codes missing; Kosovo XKX unconfirmed | P A27 |
| K-F11 | Med open | reporting.py:829-845 | Surplus blank guest form blocks automatic filing | F |
| K-F12 | Med accepted | reporting.py | ID check dropped (PR #331); host verifies documents | F |
| K-F13 | Med open | production | 112 = accepted late; never resend. `reconcile_accepted_codes.py` dry run, then `--apply`. | F |
| K-F14 | Med unverified | reporting.py due_for_automatic_send | 48 h send cap not compared with legal deadline | AR-06 |
| K-F15 | Med unverified | icalsync.py ~750 | Vanished bookings may keep a live guest link | AR-27 |
| K-F16 | Med unverified | icalsync.py ~549-642 | Date-move reconcile not atomic; re-sign alert can be lost | AR-38 |
| K-F18 | High decision HR | reporting.py:859 signature_dates_stale | Stale signed dates: safety net or re-signing (T48–T50)? | P Q6 |
| K-L01 | High decision | retention.py:218,237 | Deletion 30+30 days; Terms s19 export wording: lawyer needed | P Q9, G G-D11 |
| K-L02 | High decision | retention.py ~306 | Termination deletes legal_acceptance rows; G-D7 says keep 3 yrs | F BE-10 |
| K-L03 | High decision | retention.py, housebook.py expired_guest_ids | Retention anchor: per guest vs 6 y from last entry | G G-D4 |
| K-L04 | High decision | reporting.py guest_signature_issue | Foreigners under 15 may be exempt; signature forced | C |
| K-L05 | High decision | passport_photos.py | Legal basis: ID image copies, drawn signatures | C P0 2-3 |
| K-L06 | High decision | deadlines.py add_working_days | §100(c) inclusive working-day reading needs counsel | F D3 |
| K-L07 | Med decision | privacy_policy_i18n.py §8 | Logging section describes old logging | G OPS-3 |
| K-L08 | Med decision | cookie and banner copy | Cloudflare cookie names unverified; no-banner wording unapproved | G MK-2/3 |
| K-L09 | Med decision | UbyHost_workplan/compliance/00_README.md | DSR/incident retention; Terms §17.2 liability floor | compliance |
| K-L10 | Med decision | stay_fee.py | 60-night boundary; GDPR Art. 9 for disability exemptions | X |
| K-P01 | High decision | access.py, auth.py (#280) | Admin preview unmasked, reason optional; align DPIA/DPA text | AR |
| K-P02 | High open | docs/vendors/README.md, ROPA | Support-mailbox provider: no subprocessor row, no DPA | G LD-4 |
| K-P03 | High open | backup-gdrive.sh | Drive backups need Workspace DPA or removal; DPA §11 lists Render | G OPS-2 |
| K-P04 | Med open | db.py guests | Names, birth date, address in plaintext at rest | F W2.2 |
| K-P05 | Med open | db.py | Dead plaintext doc_number/visa_number columns remain | G BE-11 |
| K-P07 | Med open | docs/vendors/README.md | Vendor DPA evidence is only a README | G LD-9 |
| K-P08 | Med decision | posthog_sync.py | Account deletion leaves the PostHog person; manual for now | 0039 |
| K-S01 | Med open | .cursor/mcp.json | Agents held a production Cloudflare MCP (removed by 0001) | AR-41 |
| K-S02 | Med open | server egress | SSRF DNS-rebinding residual; needs egress deny rules | S UH-11 |
| K-S03 | Med accepted | routes/guest.py | One link + PIN reveals dates of overlapping stays | S UH-21 |
| K-S04 | Med unverified | routes/guest.py claim routes | Claim routes skip the reach-back bound (id oracle) | R #106 |
| K-S05 | Med unverified | admin console | Admin console shows working guest claim links | F W2.4 |
| K-S10 | High decision | server .env | Owner: confirm UBYHOST_SECRET_KEY rotated after history leak | AR-01 |
| K-I03 | Low open | invoices.py cancel | Concurrent cancel returns 500 | P A10 |
| K-I04 | Low open | invoices.py | Unvalidated duzp/due/correction dates give 500 | P A11 |
| K-I05 | Low open | invoices.py:299 | Invoice year from server date, not Prague | P A12 |
| K-I06 | Low unverified | invoice_pdf.py | PDF floors the unit price; the web page rounds | P A13 |
| K-I07 | Low unverified | routes/stay_fees.py | Cadence switch may orphan adjustments | P A15 |
| K-I08 | Low open | stay_fee.py _day_liability | "Charge" files a minor with a blank reason | P A08 |
| K-I09 | Med unverified | invoices.py:validate_for_issue | Buyer address unchecked; verify VAT invoice requirements | UI §3 |
| K-U01 | High decision | product.html:49,113, landing.html:72,189 | CTAs dead-end at /login while sign-up is off | UX UX-9 |
| K-U02 | Med unverified | routes/guest.py PIN gate | A wrong PIN loses the #c= claim secret | UX M-3 |
| K-U03 | Med open | signature.js:515, settings.html:250 | Back skips validation; recovery-code field numeric-only on iOS | UX M-5, M-1 |
| K-U04 | Med unverified | mail_notify.py, signature.js, reservations | UX majors M-4 to M-9 | UX |
| K-U05 | Med unverified | test_guest_browser_e2e.py | Local browser pass; CI pending | X |
| K-U06 | Low open | apartment_form.html | Pills aligned; CI/staging pending | UI §3 |
| K-U07 | Low decision | entities.html | Visible Delete/explanation; guard kept; CI | UI §4 |
| K-U11 | Med open | host.css | Geometry checked locally; CI/staging pending | 0040 |
| K-U12 | Med open | reservations.html, dashboard.html | 1280px overflow; mobile menu closes | 0041 |
| K-U13 | Med review | browser tests | CI import 0042; UI fails | 0042 |
| K-O01 | High open | server crontab | Backup and off-site crons are not in the repo; verify on server | AR-04 |
| K-O02 | Med open | docker-compose.yml:14 | Floating image tag; check rollback on real deploy | AR-03 |
| K-O03 | Med open | reporting.py:702 dashboard_rows | N+1 queries and double decrypts | P A50-51 |
| K-O04 | Low open | requirements.txt, Caddyfile | Pillow undeclared; dev deps use >=; no HSTS includeSubDomains | P A59, A61 |
| K-O05 | Med open | db.py periodic scans | Scans cover all stays ever; cost grows with retention | AR-43 |
| K-W01 | Med decision | GitHub repo | ~30 stale PRs; owner task 0001 step 12 APPLY=1; keep #278 #279 | 0001 |
| K-ML01 | Low open | App/app/static/app.js | Unused reset-password JS (0003) | magic-link HANDOFF |
| K-ML02 | Low open | App/app/host_i18n.py | Unused `login.password*` i18n keys | magic-link HANDOFF |
| K-ML03 | Low open | UbyHost_workplan/compliance/01, 03 | Compliance docs partly updated; lawyer review due | task 0005 |
| K-ML04 | Low open | login limit | Address 3/15 min budget exhaustible; account-only limits leak accounts | 0006 |
| K-D02 | Low open | door_codes `_handle_moves` | Move replace: gateway retried every 15 min, uncapped; guest keeps old PIN | 0037 |
| K-D03 | Med decision | door_codes `_handle_moves` | Move permission/reauth/config/disabled: no retry once access fixed (0037) | 0037 |
| K-D04 | High open | door_codes `issue`, `_handle_moves` | Same-hours rebooking can get cancelled PIN via `get` | 0069 |
| K-U15 | Med review | Host forms/navigation | Owner review (0084) | [plan](../plans/host-ux-combined-staging.md) |
| K-T01 | Low open | Tests | Order-dependent tests (also 3 in test_host_i18n.py) | 0080 |
| K-U16 | Review | Host UI | #389 polish; CI pending | 0102 |
| K-PG04 | Low open | scripts/reencrypt_data_key.py | Refuses on PG (no verified backup source); fix before first PG key rotation | 0462 |
| K-U17 | Low open | Property page | #sec-messages deep link lands on calendars after late layout shifts; re-scroll. | 0995 |

- K-UI-CACHE: bump `?v=` on edits; 1y cache (0172).
- K-NAV-418: 3 host_i18n tests fail. K-CHECKIN #435, K-MORE #436 undeployed.
- K-PK0290: passkey fix open.
- K-CF01: mid-session challenge: see CLOUDFLARE Rule 3.
- K-PG-ORDER: goose tests fail after icalsync locally; CI OK.
- 0897 guest pay gaps: Slovak QR, PG migration 00007 unrun, no mark-as-paid, no e-mail link, copy, legal sign-off.
- K-PICK: guest-enhancements.js:207 blur timer not cleared on refocus (1079).

- K-HOUSEBOOK: house book Details popover unreachable at 390/768 (zero-size trigger).
- K-FLAKY-DC: flaky `test_door_codes_safeguards::test_an_undeleted_old_code_after_a_move_tells_the_host` (test-postgres-full); passed on rerun.
- K-GUEST-DATES: es/fr guest dates row wraps at 375, 360 px.
- K-1091D: `test_1091_d` name no longer matches its test.
- K-TAP43: local only (CI green): `test_design_guardrails_browser.py` guest-new 390 "Cancel" tap target 43 < 44.
- K-H0: from tasks/1094-report.md: `checkin_hour` NULL can raise TypeError in door_codes.py (~179, 436); `/save` with a non-owned guest_id becomes a new person; `guest_form_saved` audit has no field names.
- K-SM2 (brief 1105): OPERATIONS.md submit_state section disagrees with the code in 9 places.
- K-SM3 (brief 1111): rules.md lines 37, 44 still say production is SQLite, migrations frozen at 0033.
- K-DC-AMBIG (1149 S8/S9): delete timeout or crash, then revival: issued, PIN gone, no audit. Owner.
- K-F22 closed (1150, 1150b): an iCal date move now waits for a crash-stuck running filing (found through submission.guest_ids, any age), same as for outcome_unknown.
- K-DC-RECANCEL (937 review): re-cancel after a lost race re-deletes a gone code; check TTLock not-found = success.
