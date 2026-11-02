# 0821 report

Status: blocked (steps 1-5 done, next = step 6)

## Done

- Step 1: `App/app/booking_cancel.py` created. Commit `4b0ae40`.
- Step 2: `App/app/booking_manage.py` created. Commit `4a958c6`.
- Step 3: CSS moved to `App/app/templates/_pp_booking_css.html` (with the appended rules); `property_page.html` now has `{% include "_pp_booking_css.html" %}`. Four tokens checked present. Tests 0818 (`test_booking_site_page`, `test_property_page`) pass. Commit `35ec44f`.
- Step 4: English and Czech keys added to `App/app/host_i18n.py` after the `site_booking.invoice.note` lines. Commit `1b9d461`.
- Step 5: `App/app/routes/property_page.py`: imports and the three guest routes (`booking_manage_page`, `booking_manage_cancel`, `booking_manage_calendar`) plus helpers added before `/thanks`. Ruff passed. Brief test set (62 tests) passed. Commit `935598e`.

## Next

Step 6 (create `App/app/templates/booking_manage.html`). Not started.

## Deviations

- Step 4: when `tests/test_host_i18n.py` ran alone, 3 tests failed ("no such table: apartment"), and `tests/test_notification_copy.py` had 1 failure ("no such table: guest"). Both also fail with the step 4 edit stashed, so they are not caused by it. In the brief's combined test set (step 5 run) all 62 tests pass, so the failures look like test-order or DB-setup dependence. Not investigated further.
- Step 2: the unused `from . import ... property_page` import was left out, as the brief's note allows.
- Commits used named files only, not `git add -A`.
- Budget: this report was written but NOT committed (tool-call budget reached). Commit `docs/tasks/0821-report.md` first when resuming.

## Left

Steps 6 to 10.
