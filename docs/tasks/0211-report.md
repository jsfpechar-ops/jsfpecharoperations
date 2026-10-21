# 0211 report: lock time zone and guest window default

Status: review

## Files changed

- App/app/routes/admin.py: new `_lock_tz_wrong` helper used by the property `tz_warning` and by each lock in `_smart_lock_panel_context` (`lock["tz_wrong"]`); create default `permalink_window_days` 2 to 1.
- App/app/templates/_smart_locks_panel.html: `{% if lock.tz_wrong %}`.
- App/app/routes/guest.py: fallback window 2 to 1.
- App/tests/test_smart_locks_page.py: `test_lock_card_accepts_prague_summer_time`.
- App/tests/test_operator_naming.py: optional-field check now asserts no red star (0204 pin).
- App/tests/test_guest_window_default_0211.py (new): create default is 1.

## Commands (last lines)

1. `pytest tests/test_smart_locks_page.py tests/test_door_code_one_lock_one_property.py tests/test_design_admin.py`: `26 passed, 1 warning in 2.32s`
2. `python3 scripts/design_lint.py`: `design lint: OK`

Also run: `test_operator_naming.py`, `test_property_address_required.py`, `test_status_colours.py`: `54 passed in 2.73s`. `test_guest_window_default_0211.py`, `test_calmer_forms.py`, `test_claim_mail.py`: `58 passed in 3.04s`.

## Acceptance (section 7)

- [x] Lock at 7200000 shows no warning; 0 still warns (test passes). Section 6 passes.

## Pins changed

- App/tests/test_operator_naming.py: the "optional" assertion, as the brief gives.
- No other pinned test needed changing.

## Deviations

- Step 1b says "three" `tz_warning` lines. The file has only one, so only that one was replaced.
- Commits follow the executor `NNNN step k` rule (steps 1 to 5), then this report commit `0211 lock time zone`.
- Not pushed and no PR opened (the owner's instruction for this run is not to push).

## Questions

None.

## Owner steps left

- Push the branch and open the PR, or ask for it. Merge with `scripts/merge-pr-on-green.sh` only. Deploy is manual.
- Screenshots: none, per brief.
