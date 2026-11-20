# Low-severity known issues archive

Moved from [known-issues](../context/known-issues.md) on 2026-11-11 (compaction). Same table columns.

| ID | Sev/status | Where | Issue | Src |
|---|---|---|---|---|
| K-F07 | Low open HR | routes/guest.py immediate mode | Guest save waits for UbyPort (60 s+) | P A75 |
| K-F08 | Low open | icalsync.py:304 | DTEND ≤ DTSTART stored; those guests never validate | P A31 |
| K-F09 | Low open | routes/admin.py:1927 | Manual send inspects only the first batch | P A36 |
| K-F10 | Low open | routes/admin.py calendar delete | Deleted calendar's future stays stay active and alert | P A34 |
| K-F17 | Low unverified | reporting.py claim TTL; :1683 recover_stale_submissions | Lease may expire in slow batches | P A16, A30 |
| K-F19 | Low open | codelists.py error_severities | Before a successful Refresh only 1/112/150 known | police A1-A2 |
| K-P06 | Low open | routes/stay_fees.py:576 | fee_host_reason_reference unencrypted | P A46 |
| K-S06 | Low open | main.py:167 | CSP script-src allows 'unsafe-inline' | P A42 |
| K-S07 | Low decision | auth.py:498,618 | BOOTSTRAP_ADMIN=0, no accounts: host UI may stay open | P A47 |
| K-S08 | Low unverified | rate_limit.py:79 | No per-account login lockout across addresses | P A44 |
| K-S09 | Low open | deploy-production.yml | GITHUB_TOKEN stays in server's git remote | P A58 |
| K-I02 | Low open | invoices.py:51-63 _parse_decimal | "1.000" parses as 1 | X |
| K-I05 | Low open | invoices.py:299 | Invoice year from server date, not Prague | P A12 |
| K-I06 | Low unverified | invoice_pdf.py | PDF floors the unit price; the web page rounds | P A13 |
| K-I07 | Low unverified | routes/stay_fees.py | Cadence switch may orphan adjustments | P A15 |
| K-ML01 | Low open | App/app/static/app.js | Unused reset-password JS (0003) | magic-link HANDOFF |
| K-I03 | Low open | invoices.py cancel | Concurrent cancel returns 500 | P A10 |
| K-I04 | Low open | invoices.py | Unvalidated duzp/due/correction dates give 500 | P A11 |
| K-U06 | Low open | apartment_form.html | Pills aligned; CI/staging pending | UI §3 |
- K-SM2 (brief 1105): OPERATIONS.md submit_state section disagrees with the code in 9 places.
- K-SM3 (brief 1111): rules.md lines 37, 44 still say production is SQLite, migrations frozen at 0033.
- K-DC-RENAME (943): lookup by name `UH-<id>`; a code renamed in TTLock reads as gone.
- K-FLAKY-VT: test_host_filter_panels_browser.py:695 ViewTransition abort once (#943).
- K-FLAKY-DC (#1081): CI door-code tests leave pending once; local OK; suspect two nows in issue/_issue_due.
- K-F24 (947 review): recovered batch in manual mode keeps retried_at NULL; going automatic resends it once.
- K-DC-REMOVE (950): A-B-A-B move sends no 2nd moved_failed mail.
- K-DC-REVIVE-CARD (1173c): card closed in revoke_pending, delete refused, stay revived: stays closed.
- K-DC-EXTEND (1173c review): stay extended after its issued code expired gets no new code.
- K-PG-FK: goose 00004/11/13 FKs not DEFERRABLE (1263).
- K-HB-HAND: housebook says "Not yet sent" for a hand-filed guest (Python quirk; 1704a test).
- K-BLOCKED-PAGE (1859b): BlockedPage inline main styles; app.css later.
