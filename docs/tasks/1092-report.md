# 1092 report

Status: review (implemented by the orchestrator under the owner's exact-phrase override, 2026-11-10).

## Files changed

- `App/app/sample_calendar.py` — sample feed redesigned: 9 Reserved stays never overlap (each DTSTART >= previous DTEND); block moved to a free gap (+20). Still 9 reservations per property.
- `App/mock_ubyport/server.py` — `/sample-airbnb.ics` now serves `app.sample_calendar.sample_airbnb_ics()`; the divergent 4-event copy is gone.
- `App/app/demo.py` — demo marks aligned with `mark_from_ws_user` (12CDEF/34ABCD); `_enrich_*` re-anchored (+5 assigned, +7 locked, +12 czech); new `_enrich_extras()` seeds stay-fee config + rate + filing + adjustment on Vinohrady, guest `fee_host_decision='charge'`, two QR payment_requests (paid + awaiting_payment), a door-code window, cleaning_property/cleaning_event rows, a published property page (slug + page, nightly 1500 CZK, house rules) and one paid `site_booking` (direct, in the +14..+16 gap); `clear()` now deletes all demo-linked rows (adjustments before filings, FK order).
- Tests: `test_demo_seed.py` (owner-bound seed, new anchors, no-overlap + per-feature assertions + clear-empties), `test_sample_calendar.py` (new anchors + no-overlap pin), `test_demo_stay_exclusion.py` (new pin: demo fee/payment/cleaning rows never enter a filing batch).
- Docs: `docs/context/test-map.md` (Demo seed row; four row labels compacted to fit the cap), `README.md` (verified counts + demo.py line ref), `App/app/host_i18n.py` + `host_vi_i18n.py` (`demo.load_detail` copy, en/cs/vi), `.gitignore` + `git rm --cached App/mock_ubyport/mock_state.json` (A60).

## Commands (last lines)

- `pytest tests/test_demo_seed.py tests/test_demo_stay_exclusion.py tests/test_sample_calendar.py -q` → 23 passed
- `pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py` → 59 passed
- `pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_payment_rails.py tests/test_payment_services.py -q` → 1063 passed, 12 skipped
- `pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_cleaning*.py -q` → 274 passed, 3 skipped
- `pytest tests/test_property_slug.py tests/test_property_page*.py tests/test_booking_site.py tests/test_booking_widget.py tests/test_booking_direct_*.py -q` → 116 passed, 2 skipped
- copy/i18n/calendar rows → 107 passed, 1 skipped; onboarding/property/first/endtoend rows per-file → all passed
- `pytest tests/test_soap.py tests/test_ubyport_*.py tests/test_submission_*.py` → 117 passed; `test_ubyport_sample_pdf.py` (3 tests) fails identically on the base commit (sandbox reportlab issue), as does `test_feed_dns_pinning.py` (cannot bind the pinned address in this sandbox) — both pre-existing, not from this change.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` → All checks passed!
- `python3 scripts/context_lint.py` → OK

## Acceptance

- [x] Sample calendar stays never overlap (pinned); mock and app serve one feed.
- [x] seed() under mock creates both properties + fee config + filing/adjustment + 2 payment requests + fee decision + door code + cleaning + published property page + 1 paid booking; `POST /demo` unchanged.
- [x] clear() removes everything (asserted table by table).
- [x] No demo row reachable from filing paths (exclusion test green).
- [x] Rows above green; ruff + context_lint clean; README counts updated.

## Deviations

- No `invoice` row is seeded for the stay fee: `invoice_item.kind='stay_fee'` was reverted upstream and nothing creates one, so there is nothing to link. `payment_request.invoice_id` stays NULL for the same reason.
- Card rail is not seeded (needs a real Stripe link); two QR requests instead.
- test-map row labels trimmed to fit the file's token cap.

## Owner steps

1. Review PR #886 (branch `vibe/demo-coverage-9320c3`), merge via `scripts/merge-pr-on-green.sh` when CI is green.
2. On staging: sign in, "Load demo data"; click through Stay fee (filing + adjustment), Payments (paid + awaiting), Door codes, Cleaning, the Stays list (no double-booked property) and the public property page; then "Clear demo data" and confirm an empty dashboard.

## Review round 2 (owner review of PR #886, 2026-11-10) — all fixed

1. Paid `site_booking` now creates the linked `reservation` (source='site', like `booking_direct`), so +14..+16 are blocked and the booking appears in Stays; no guest rows, and demo apartments are never filed.
2. Demo property page seeds with `hide_from_search=1`, and `booking_checkout.start`/`start_direct` refuse demo apartments (`demo.is_demo_apartment`) before holding dates — pinned by `test_booking_checkout_refuses_demo_apartments`.
3. Sealed `stay_fee_filing`/`stay_fee_adjustment` removed: invented rows cannot produce an honest sealed PDF/CSV; the live fee pages compute from the demo stays. `stay_fee_rate` + config remain.
4. Door-code window now ends at the one-night stay's check-out (today+1 11:00) and `next_attempt_at` is set, so `door_codes.reconcile` does not churn on it.
5. `uby_mark` is derived via `validation.mark_from_ws_user(uby_ws_user)` in `_seed_apartment` (param removed).
6. The no-overlap feed assertion was already in `test_sample_calendar.py::test_sample_airbnb_ics_never_double_books` (line 39) since the first push; kept, plus the seed-level check.
7. Moot after (3): no adjustment row anymore.
8. Blank line restored before `@app.post("/reset")` in the mock server.

Re-run: demo rows 24 passed; booking/property-page rows 116 passed; stay-fee/door-code/payments rows 1088 passed; ruff clean; context_lint OK. Reservation count is now 19 (site booking's own reservation); README updated.
