# 1026 report: stay-fee >60 rule and locked guest stay dates

Status: review (Task C not done, owner decision needed: see Left)

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

## Task 3: unsigned guests are counted in the fee

- A guest the host added without a signature is now counted in the pay-step total, the per-person amounts, the register and the live charge. The fee follows the stay, not the signature.
- Changed: `stay_fee.property_period` and `stay_fee.charge_for_reservation` no longer skip unsigned guests. `unsigned_stays()` and the `unsigned` issue flag are unchanged (the flag still blocks finalization). Archived and demo guests stay excluded.
- Money impact: totals go UP by the nights of every unsigned guest on an active stay (before: 0 Kč for them). No one has been asked to pay these amounts yet, so this is a change to what guests see from now on.
- Tests updated to the new rule (old pinned behaviour in brackets):
  - `App/tests/test_stay_fee.py::test_property_period_counts` (9 nights, 450 Kč -> 11 nights, 550 Kč)
  - `App/tests/test_stay_fee_audit_1025.py::test_group_pay_panel_qr_and_register_agree` (unsigned row 0 nights -> 5; persons [2,4,5] -> [2,4,5,5]; July nights 3 -> 5)
  - `App/tests/test_stay_fee_obec_0898.py::test_charge_counts_unsigned_excludes_demo_and_respects_the_kill_switch` (renamed; unsigned line [] -> 1 line)
- Left as is: `App/tests/test_demo_stay_exclusion.py` (demo guests stay excluded, still 0).

## Task C: pay-step line (not done)

- The owner's line already exists. `App/app/i18n.py` `fee_now_body` (en, cs, de, es, fr) and `App/app/guest_uk_i18n.py` (uk) say "You only pay once for the whole group." (en) and the Czech, German, Spanish, French and Ukrainian equivalents. Adding a second line would duplicate it, which the owner rule forbids.
- No Vietnamese guest copy exists for the fee keys at all.
- Question for the owner: keep the existing line (no change), or replace `fee_now_body` with the new wording and add VI? Nothing changed for Task C.

## Tests

- Stay-fee set (`test_stay_fee_rules_1026.py`, `test_stay_fee_audit_1025.py`, `test_stay_fee.py`, `test_stay_fee_obec_0898.py`, `test_demo_stay_exclusion.py`, `test_query_budget.py`, `test_stay_fee_guest_pay_0897.py`, `test_guest_pay_form_values.py`): 170 passed, `-x`.
- Guest save-route set (all 57 `tests/test_*guest*.py` files, plus `test_stay_missing_guest_rows.py`, `test_stay_fee_rules_1026.py`, `test_stay_fee_audit_1025.py`): 742 passed, 0 skipped, `-x`.
- Browser (`UBYHOST_REQUIRE_BROWSER=1`, `-rs`): `test_stay_fee_guest_pay_browser.py` and `test_0896_fee_pay_geometry_browser.py`: 18 passed, 0 skipped.
- No template, CSS or static file changed: no cache bump, `test_guest_languages.py` and `test_static_versions.py` not needed.
- Git side effect: the browser run rewrote two tracked PNGs under `docs/tasks/screenshots-0402/`; restored with path-limited `git checkout --`. No PNG committed.

## Left

- Task C: owner decision (see above).
- Screenshot: `/mnt/project-files/ux-shots/stayfee-rules/pay-390.png` NOT written. The only 390 px pay image the test makes is the host stay-fee page, not the guest pay step, so I did not copy it. Needs a guest pay-step 390 px shot.
- Owner: review the Task D money change before merge.

- CI fix (PR #815): changed `tests/test_p3_review_repro.py::test_unparseable_stay_date_is_refused` (3 params: garbage, 2026-02-30, 31.12.2099) and renamed it `test_unreadable_posted_stay_date_is_ignored_and_booking_dates_kept`.
- Why: it pinned the old 422 refusal of a bad posted stay_from; task 2 locks stay dates (guest.py::_locked_stay_dates), so the save now returns 303 and keeps the booking dates. Owner approved the lock; the lock itself is unchanged.
- No other listed test failed (the 3 CI failures were all these parametrized cases). Listed set + test_stay_fee_rules_1026.py: 283 passed.
