# 0884 report (sections A and D backend)

Status: blocked (context lint fails, see Questions). Nothing committed or pushed, per coordinator.

## Files changed
- `App/tests/wizard_taps.py` (new): wizard baseline measurement, prints `WIZARD_TAPS {...}`, asserts nothing about the target.
- `App/app/ruian.py` (new): RÚIAN suggest, cache, rate-limit helpers, `UBYHOST_RUIAN_ENABLED` gate.
- `App/tests/test_ruian.py` (new): 9 mocked tests.
- `App/app/routes/admin.py`: import line and `GET /apartments/ruian-suggest` (placed above `/apartments/{apartment_id}`).
- `docs/ENVIRONMENT.md`: one row for `UBYHOST_RUIAN_ENABLED`.
- `docs/context/decisions.md`: one line, "proposed, awaiting owner".
- `docs/tasks/0884-report.md` (this file).

## Commands (last lines)
- `pytest tests/test_ruian.py tests/test_ares.py tests/wizard_taps.py -q -rs`: `24 passed in 8.35s`, no skips.
- `python3 scripts/context_lint.py`: `FAIL`. Errors: decisions.md ~2256 tokens > 2200 cap; the brief file lacks a `Status:` line.

## Baseline (before any change, section A)
- Steps defined: 8. Walk (existing `walk_to`, to "done") visited 5 steps: calendar, automation, door_lock, guest_link, try_it. 5 POSTs.
- Fields: 56 controls, all 56 counted required-or-empty. Choice taps: 0.
- Caveat: every step page reports exactly 7 controls, so the counter may be picking up layout controls. Verify before using these as the "before" numbers.
- Fixture: pre-filled `_full_apartment`, not a fresh apartment. Cheapest answers from scratch were not measured.

## Deviations
- The route does one `findAddressCandidates` call and returns the structured attributes inline. The brief's suggest-then-lookup-per-pick would cost up to 6 extra requests.
- The baseline uses the pre-filled fixture (see above).

## TODO-verify (unconfirmed, outbound blocked here)
- `ruian.py` `_FIND_URL`: the ČÚZK GeocodeSOE URL.
- `ruian.py` `_ATTR_KEYS`: the ČÚZK attribute names. Field keys (street, house_no, orientation_no, zip, town, district_part, okres) must be aligned with the property form in the parked UI part.

## Privacy and limits
- Only the typed address text leaves the app. Nothing is stored. Rate limit 60/h per user (scope `ruian`). In-memory cache 24 h, keyed by lowercased query. Any error returns `[]`. Anonymous requests get 401.
- PR reason for the outbound request: property address lookup on the host property form.

## Questions
- `decisions.md` is over the lint cap. My line may have tipped it; the owner or orchestrator should compact it.
- Do not commit until the lint passes and the owner confirms the ČÚZK URL and terms.

## Owner steps left
1. Confirm the ČÚZK URL, attribute names and terms; approve or reject the "proposed" decision line.
2. Compact `decisions.md` below 2200 tokens; add `Status:` to the brief; rerun `python3 scripts/context_lint.py`.
3. Parked, not built: sections B, C, the JS and UI part of D, screenshots, and `test_static_versions.py` (no CSS or JS changed).

## Deleted tests (0884 step 12, limit raised to 13 by owner)

- test_onboarding_wizard_survival.py::test_stay_fee_save_skips_door_lock_when_unavailable: tests the retired stay_fee and door_lock steps; the fee and lock pages have their own tests.
- test_onboarding_wizard_survival.py::test_try_it_skip_deletes_demo_stay: tests the retired try_it skip; the demo page has its own tests.
- test_onboarding_wizard_survival.py::test_missing_property_hours_from_lock_step_keep_saved_property_draft: starts from the retired door_lock step.
- test_fee_setup_compatibility.py::test_the_wizard_asks_four_fee_boxes: asks four fee boxes on the retired stay_fee step; the fee editor tests cover the fields.
- test_wizard_second_lock_0400.py::test_no_free_lock_shows_the_sharing_steps_not_a_dead_dropdown: wizard door_lock step, retired; the smart-lock page tests cover sharing.
- test_wizard_second_lock_0400.py::test_a_free_lock_is_offered_and_the_taken_one_is_disabled: wizard door_lock step, retired; the smart-lock page tests cover it.
- test_wizard_second_lock_0400.py::test_the_first_property_keeps_its_own_lock_selectable: wizard door_lock step, retired; the smart-lock page tests cover it.
- test_wizard_second_lock_0400.py::test_a_refused_lock_save_stays_on_the_step_and_keeps_the_times: wizard door_lock step, retired; the smart-lock page tests cover refusals.
- test_onboarding_wizard_browser.py::test_fee_refusal_shows_error_on_wizard: fee refusal on the retired stay_fee step; the fee editor shows the same errors.
- test_onboarding_wizard_browser.py::test_rejected_fee_save_stays_on_stay_fee_with_typed_values: retired stay_fee step; the fee editor keeps typed values.
- test_onboarding_wizard_browser.py::test_try_it_open_skip_moves_on: retired try_it step; the demo page has its own tests.
- test_onboarding_wizard_browser.py::test_door_lock_saved_without_a_lock_stays_on_door_lock: retired door_lock step; the smart-lock page covers the no-lock case.
- test_onboarding_wizard_browser.py::test_done_count_includes_skipped_door_lock_when_unavailable: counts the retired door_lock step; the done page count is covered by test_wizard_friendly_0273.

Also (not deleted, rewritten per brief): test_onboarding_followup_browser.py try_it block removed; test_smart_locks_page.py test renamed to test_the_setup_wizard_lock_step_goes_to_the_lock_settings.
