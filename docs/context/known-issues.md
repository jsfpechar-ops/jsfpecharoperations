# Known issues

**Rules**

- This is the single list of known bugs and open findings. It replaces FOLLOWUPS.md and every automation's MEMORIES.md.
- **Don't read it whole.** `grep -n '<file or area>' docs/context/known-issues.md`.
- Bug hunts: skip anything listed here and append only new IDs.
- When an item is fixed: delete its row in the fixing PR and add a decisions line if it mattered.

**Status values:** `open`, `unverified` (check before you act), `decision` (owner, lawyer or council must decide), `accepted`. **HR** = HIGH RISK: needs an owner decision before any change.

**Sources** (open only the cited section):

| Key | File |
|---|---|
| P | `docs/archive/plans/UbyHost_prelaunch_review/UbyHost_prelaunch_review.md` |
| F | `docs/archive/FOLLOWUPS.md` |
| AR | `docs/archive/plans/UbyHost_Audit_and_Cursor_Plan_2026-09-28.md` |
| G | `docs/archive/plans/GDPR_REMEDIATION_PLAN.md` |
| C | `docs/archive/TECHNICAL_COMPLIANCE_AUDIT.md` |
| S | `docs/archive/SECURITY_REVIEW_2026-09-15.md` |
| R | `docs/archive/PHASE_1-6_REVIEW_2026-09-24.md` |
| UX | `docs/archive/plans/UX_IMPLEMENTATION_REVIEW.md` |
| X | Cursor chats (not in repo) |

Seeded 2026-10-06 from the audits against `d72c870`. About 100 findings were judged fixed and left out.

| ID | Sev/status | Where | Issue | Src |
|---|---|---|---|---|
| K-F01 | High open | reporting.py:1356-1413, ubyport/client.py:166 | Non-401 4xx retried every sweep, no attempt cap | P A28-29 |
| K-F02 | High open HR | icalsync.py date-move UPDATE ~498 | Date move ignores submission_claim; can move a guest mid-send | P A24 |
| K-F03 | Med open HR | icalsync.py ~805-830 | Lone vanished future booking stays "suspect" forever | P A19 |
| K-F04 | Med open | icalsync.py | Same booking in two feeds makes two stays, one overdue forever | P A22 |
| K-F05 | Med open | icalsync.py, routes/admin.py | Manual and scheduled sync clash on UNIQUE; loser marked error | P A23 |
| K-F06 | Med open | validation.py country_codes() | Some police country codes missing; Kosovo XKX unconfirmed | P A27 |
| K-F07 | Low open HR | routes/guest.py immediate mode | Guest save blocks on the UbyPort call (60 s+) | P A75 |
| K-F08 | Low open | icalsync.py:304 | DTEND ≤ DTSTART stored; those guests never validate | P A31 |
| K-F09 | Low open | routes/admin.py:1927 | Manual send inspects only the first batch | P A36 |
| K-F10 | Low open | routes/admin.py calendar delete | Deleted calendar's future stays stay active and alert | P A34 |
| K-F11 | Med open | reporting.py:829-845 | Surplus blank guest form blocks automatic filing | F |
| K-F12 | Med accepted | reporting.py:270,1002 | ID check dropped from the UI (owner, 2026-10-09, PR #331); host checks documents themselves | F W4.3 |
| K-F13 | Med open | production data | 112 is "reported late", an accept (police, 24 Sep 2026). Production guests in `error`/`blocked` whose only code is 112 are in the register. Owner: `App/scripts/reconcile_accepted_codes.py` (dry run), check 2-3 in UbyPort, then `--apply`; never resend | F W4.2 |
| K-F14 | Med unverified | reporting.py due_for_automatic_send | 48 h send cap not compared with the legal deadline | AR-06 |
| K-F15 | Med unverified | icalsync.py ~750 | Vanished bookings may keep a live guest link | AR-27 |
| K-F16 | Med unverified | icalsync.py ~549-642 | Date-move reconcile not atomic; re-sign alert can be lost | AR-38 |
| K-F17 | Low unverified | reporting.py claim TTL; :1683 recover_stale_submissions | Lease may expire across slow batches; stale-running recovery unconfirmed | P A16, A30 |
| K-F19 | Low open | codelists.py error_severities | Severities load on a passed connection test or "Refresh code lists"; until then only 1, 112, 150 are known and other codes count as refused | police A1-A2 |
| K-F18 | High decision HR | reporting.py:859 signature_dates_stale | Stale signed dates: keep the safety net or restore re-signing (T48–T50)? | P Q6 |
| K-L01 | High decision | retention.py:218,237 | Deletion 30+30 days and Terms s19 export wording need a lawyer | P Q9, G G-D11 |
| K-L02 | High decision | retention.py ~306 | Termination deletes legal_acceptance rows; G-D7 says keep 3 years | F BE-10 |
| K-L03 | High decision | retention.py, housebook.py expired_guest_ids | Retention anchor per guest vs 6 years from the last entry | G G-D4 |
| K-L04 | High decision | reporting.py guest_signature_issue | Foreigners under 15 may be exempt; a signature is forced | C |
| K-L05 | High decision | passport_photos.py | Legal basis for ID image copies and drawn signatures | C P0 2-3 |
| K-L06 | High decision | deadlines.py add_working_days | Inclusive working-day reading of §100(c) needs counsel | F D3 |
| K-L07 | Med decision | privacy_policy_i18n.py §8 | Logging section describes old logging | G OPS-3 |
| K-L08 | Med decision | cookie and banner copy | Cloudflare cookie names unverified; no-banner wording unapproved | G MK-2/3 |
| K-L09 | Med decision | docs/UbyHost_workplan/compliance/00_README.md | DSR/incident retention; Terms §17.2 liability floor | compliance |
| K-L10 | Med decision | stay_fee.py | 60-night boundary; GDPR Art. 9 for disability exemptions | X |
| K-L11 | High decision | subprocessors_i18n.py ttlock row, DPA §11 | Door codes: SCCs with TTLock (Sciener, China) must be signed before any host other than the owner uses door codes; add TTLock to DPA §11 at the next revision. Assessment done in DOOR_CODES_LEGAL | [DOOR_CODES_LEGAL](../privacy/DOOR_CODES_LEGAL.md) |
| K-P01 | High decision | access.py, auth.py (#280) | Admin preview unmasked, reason optional: align the DPIA/DPA text | AR |
| K-P02 | High open | docs/vendors/README.md, ROPA | Support-mailbox provider has no subprocessor row and no DPA | G LD-4 |
| K-P03 | High open | backup-gdrive.sh | Drive backups need a Workspace DPA or removal; DPA §11 lists Render | G OPS-2 |
| K-P04 | Med open | db.py guests | Names, birth date and address in plaintext at rest | F W2.2 |
| K-P05 | Med open | db.py | Dead plaintext doc_number/visa_number columns not dropped | G BE-11 |
| K-P06 | Low open | routes/stay_fees.py:576 | fee_host_reason_reference unencrypted | P A46 |
| K-P07 | Med open | docs/vendors/README.md | Vendor DPA evidence is only a README | G LD-9 |
| K-S01 | Med open | .cursor/mcp.json | Agents hold a production Cloudflare MCP (removed by task 0001) | AR-41 |
| K-S02 | Med open | server egress | SSRF DNS-rebinding residual; needs egress deny rules | S UH-11 |
| K-S03 | Med accepted | routes/guest.py | One link + PIN reveals dates of overlapping stays | S UH-21 |
| K-S04 | Med unverified | routes/guest.py claim routes | Claim routes skip the reach-back bound (id oracle) | R #106 |
| K-S05 | Med unverified | admin console | Admin console shows working guest claim links | F W2.4 |
| K-S06 | Low open | main.py:167 | CSP script-src allows 'unsafe-inline' | P A42 |
| K-S07 | Low decision | auth.py:498,618 | BOOTSTRAP_ADMIN=0 with no accounts may leave the host UI open | P A47 |
| K-S08 | Low unverified | rate_limit.py:79 | No per-account login lockout across addresses | P A44 |
| K-S09 | Low open | deploy-production.yml | GITHUB_TOKEN stays in the server's git remote | P A58 |
| K-S10 | High decision | server .env | Owner: confirm UBYHOST_SECRET_KEY was rotated after the history leak | AR-01 |
| K-I01 | Med fixed | routes/invoices.py issue | Double submit issues two invoice numbers (0019 lock per stay; 0020 wiring) | P A07 |
| K-I02 | Low open | invoices.py:51-63 _parse_decimal | "1.000" parses as 1 | X |
| K-I03 | Low open | invoices.py cancel | Concurrent cancel returns 500 | P A10 |
| K-I04 | Low open | invoices.py | Unvalidated duzp/due/correction dates return 500 | P A11 |
| K-I05 | Low open | invoices.py:299 | Invoice year from the server date, not Prague | P A12 |
| K-I06 | Low unverified | invoice_pdf.py | PDF floors the unit price; the web page rounds | P A13 |
| K-I07 | Low unverified | routes/stay_fees.py | Cadence switch may orphan adjustments | P A15 |
| K-I08 | Low open | stay_fee.py _day_liability | "Charge" files a minor with a blank reason | P A08 |
| K-U01 | High decision | product.html:49,113, landing.html:72,189 | CTAs dead-end at /login while sign-up is off | UX UX-9 |
| K-U02 | Med unverified | routes/guest.py PIN gate | A wrong PIN loses the #c= claim secret | UX M-3 |
| K-U03 | Med open | signature.js:515, settings.html:250 | Back skips validation; recovery-code field numeric-only on iOS | UX M-5, M-1 |
| K-U04 | Med unverified | mail_notify.py, signature.js, reservations | UX majors M-4 to M-9 | UX |
| K-U05 | Med unverified | test_guest_browser_e2e.py | [320] reported failing on main; confirm in CI | X |
| K-O01 | High open | server crontab | Backup and off-site crons aren't in the repo; verify on the server | AR-04 |
| K-O02 | Med open | docker-compose.yml:14 | Floating image tag; check rollback on a real deploy | AR-03 |
| K-O03 | Med open | reporting.py:702 dashboard_rows | N+1 queries and double decrypts | P A50-51 |
| K-O04 | Low open | requirements.txt, Caddyfile | Pillow undeclared; dev deps use >=; HSTS includeSubDomains missing | P A59, A61 |
| K-O05 | Med open | db.py periodic scans | Scans cover all stays ever, so cost grows with retention | AR-43 |
| K-W01 | Med decision | GitHub jsfpechar-ops/jsfpecharoperations | ~30 stale open PRs (wp-stack etc.); owner runs task 0001 step 12 with APPLY=1; do not close #278 or #279 | task 0001 |
| K-ML01 | Low open | App/app/static/app.js | Dead reset-password JS after task 0003 password removal | magic-link HANDOFF |
| K-ML02 | Low open | App/app/host_i18n.py | Dead `login.password*` i18n keys after e-mail link login | magic-link HANDOFF |
| K-ML03 | Low open | docs/UbyHost_workplan/compliance/01, 03 | Compliance docs partially updated in 0005; lawyer review on LAWYER REVIEW paragraphs | task 0005 |
| K-ML04 | Low open | login link limit | Anyone can use up a victim's 3 requests per 15 min. Kept: counting only real accounts would reveal who uses UbyHost | 0006 |
