# 1026 report: stay-fee >60 rule and locked guest stay dates

Status: review (partial: remaining guest save-route tests not re-run, see Left)

## Task 1: over 60 nights owes nothing

- Code already matched the owner rule, so no behaviour change. `stay_fee.guest_period` marks any stay over 60 nights `not_subject` (0 liable nights) before it reads the host decision, so a host "charge" cannot bill it. Exactly 60 nights is liable by default.
- Estimate (`routes/guest.py::_fee_estimate`, `_fee_box`), pay step (`_fee_pay_panel` via `charge_for_reservation`) and register all derive from `guest_period` and `_apply_scope_boundary`, so they agree.
- Ambiguity kept: a host-recorded scope ruling `calendar_days` (explicit, with reference) still moves exactly 60 nights out of scope. Not changed, flagged for owner.
- Money impact: none. 61+ nights were already 0 Kč; 59 and 60 nights were already charged.
- New tests: `App/tests/test_stay_fee_rules_1026.py` (59/60/61 engine, host charge at 61, estimate and fee box at 59/60/61, ruling check, locked-date helper).

## Task 2: guest stay dates are locked

- Guest save (`/l/{token}/{reservation_id}/save`) and language switch (`/relang`) read posted `stay_from`/`stay_to` through `admin_helpers.stay_dates_from_form`. Replaced with `guest.py::_locked_stay_dates(reservation, existing)`: stored stay if set, else the booking dates. Posted values are ignored. Template hidden inputs unchanged.
- Money impact: a guest can no longer pay less by editing hidden dates to a shorter stay.
- Old tests pinned the refusal and were updated (renamed where needed): `App/tests/test_host_guest_form.py::test_guest_save_refuses_a_stay_outside_the_booking` became `test_guest_save_ignores_posted_stay_dates`; `test_the_stay_refusal_is_translated` now asserts no refusal text.

## Tests

- `pytest tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_0911* tests/test_0913* tests/test_fee_*.py tests/test_stay_fee_audit_1025.py tests/test_guest_pay_form_values.py tests/test_stay_fee_guest_pay_0897.py tests/test_static_versions.py`: 435 passed, 2 skipped (screenshot-only).
- `tests/test_host_guest_form.py tests/test_stay_fee_rules_1026.py`: 34 passed.
- Guest save-route files (`-x` run): 185 passed, then the one refusal test failed and was updated.

## Left

- Re-run the remaining guest save-route test files (the batch stopped at the first failure; not re-run after the fix).
- No static file or template changed, so no cache bump and no screenshots.
