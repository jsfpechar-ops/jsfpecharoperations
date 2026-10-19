# 0136 report

Status: blocked

## Files changed
- App/app/templates/reservation_detail.html (step 1, 4f587de)
- App/app/templates/guest_form_admin.html (step 1, 4f587de)
- App/app/host_i18n.py (step 2, b12a38c)
- App/app/passport_photos.py (step 3, comments only)
- App/tests/test_status_colours.py, App/tests/test_host_guest_form.py, App/tests/test_wp28_geometry.py (step 4)
- App/tests/test_remove_id_check.py (new, step 4)

## Commands
- Step 1: grep gives 0 and 0; template compile printed `compiled`.
- Step 2: patch `ok`. Test `test_host_i18n` language endpoint fails with `sqlite3.OperationalError: no such table: apartment`. Accepted as known by the coordinator.
- Step 3: `pytest tests/test_retention.py tests/test_passport_photo*.py -q --tb=short -x` tail: `34 passed, 2 warnings in 3.49s`.
- Step 4: `pytest tests/test_remove_id_check.py tests/test_status_colours.py tests/test_host_guest_form.py tests/test_send_controls.py tests/test_endtoend.py tests/test_wp28_ui_sweep.py tests/test_design_stay_detail.py tests/test_design_lint.py -q --tb=short -x` tail (run twice, same result):
  ```
  E   AssertionError: assert 'msg=' in '/apartments?err=This%20property%20no%20longer%20exists.'
  FAILED tests/test_endtoend.py::test_04_connection_test_reaches_the_service
  1 failed, 74 passed, 1 warning in 5.44s
  ```

## Deviations
- test_endtoend.py::test_04 fails in the combined step 4 run. It passes alone (28 passed). It also fails with only `tests/test_send_controls.py tests/test_endtoend.py`, and neither file was edited, so this is a pre-existing file-order interaction, not this brief. It is not in the known list. Stopped here per the two-failure rule.
- Not done: step 5 (browser tests, screenshots; the scratch helper `shoot_pages.py` does not exist) and step 6 (lint and commit). No screenshots taken.
- reporting.py and routes/admin.py are untouched.

## Questions
- Should test_endtoend test_04 be added to the known list, or fixed in its own brief? Run order: test_send_controls before test_endtoend.
- Step 5 needs the scratch helper `shoot_pages.py`, which is not in the scratchpad. Should it be written, or should the owner supply it?

## Owner steps left
- None. Nothing pushed, no PR opened.
