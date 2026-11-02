# 0834 Part A report

Status: review

## Files changed
- `App/tests/test_cleaning_browser.py` only. Not staged, not committed.

## Tests rewritten (all 4 names, 10 cases) now pass
- `test_calendar_and_large_list_geometry_and_filtering` (6 cases): host calendar asserted as tiles (`.cal-day.has-cleaning`, `.cal-tile-chip.cal-clean-chip`, no `.cal-week-events`). Cleaning label and property checked in the Oct 19 day sheet. The old summary/overflow and `#calendar` above `#cleaning-list` checks were dropped because the list is hidden on the tile UI.
- `test_fractional_checkout_and_same_day_cleaning_geometry` (2 cases): same-day tags checked as two chips on Oct 17. Day sheet marker, focus restore and details dialog checked. Gantt cleaning-marker geometry and short-job checks kept. Shared page keeps the original week-view marker checks, since shared pages are not tile mode.
- `test_missing_code_is_omitted_from_host_list_and_calendar_dialog`: host marker click moved into the day sheet. Shared page keeps the week-view click.
- `test_cleaning_chip_label_starts_with_cleaning`: "Cleaning" label check moved to the day sheet, because tile chips show the localized word, not a `.cal-cleaning-label`.

## Coverage lost (owner should decide)
- Host week-view booking-bar fractional geometry (15:00 check-in, 11:00 checkout) is no longer rendered on /cleaning and is not asserted anywhere now. The host gantt draws no booking bars either.
- Tile chips do not show the cleaning start time, so the 11:00 time is asserted only through the data (`displayStart`) and the gantt marker.

## Command results
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py -k "<4 names>" -q --tb=short -rfs`: `10 passed, 16 deselected in 18.04s`
- Whole file (`-rfs`): `4 failed, 22 passed in 133.33s`. Failures are all Part B: `test_host_crud_and_drag_change_cleanings_without_moving_bookings`, `test_calendar_popup_types_create_in_place_and_localize_validation`, `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`, `test_cleaning_calendar_can_create_stay_and_refresh_turnover_in_place`. Skipped: 0.

## Deviations
- Did not read 0815/0833 reports (time budget); selectors taken from `App/app/static/dashboard-calendar.js` and the two new tests at file end.
- No product change needed for Part A.

## Questions
- Do we want a product hook for booking-bar geometry on the host, or accept the coverage loss?

## Owner steps left
- Review the diff, then stage/commit/PR as usual. Part B not started.
# 0834 Part B report

Status: review

## Files changed
- `App/tests/test_cleaning_browser.py` (4 tests rewritten)
- `App/tests/test_dashboard_calendar_browser.py` (1 test: /cleaning step)
- Not staged, not committed. No product change needed. `docs/tasks/screenshots-0814/` not rewritten (UBYHOST_TASK_SHOTS unset).

## Tests rewritten (now pass)
- `test_host_crud_and_drag_change_cleanings_without_moving_bookings`: no drag. Create from the header, check the tile tag and day sheet, open details. Move is a date change on the edit page (`/cleaning/events/{id}/edit`). Remove on the edit page. Bookings unchanged check kept.
- `test_calendar_popup_types_create_in_place_and_localize_validation`: starts on `cal_date=2026-10-27`. Created cleaning checked on the tile tag and day sheet. Localized validation (422, error text, no row) unchanged.
- `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`: tile tag and day sheet marker (label, property, warning in details). Data checks unchanged.
- `test_cleaning_calendar_can_create_stay_and_refresh_turnover_in_place`: stay checked in the DB (201, same path). Turnover is read from the DB only after its tag shows, because the refresh reconciles it (`cleaning.reconcile` runs on the cleaning routes, not inside the reservation save).
- `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place`: /cleaning step uses the month tag (`cal_date=2026-10-27`) and the day sheet, title checked for "27". Stay step opens the form through the day sheet's Add button, since a plain day click after the booking sheet did not open the form.

## Coverage lost (owner should decide)
- Drag-to-move on the host calendar is no longer tested (feature gone). Move is now covered only by the edit form.
- Host table rows and their 5-column layout and notes-not-shown check are gone (table hidden on tiles).
- Week-view marker geometry for the unset-hours cleaning (full-day box width) is not asserted anywhere on /cleaning.
- Stays are not drawn on /cleaning tiles, so "the created stay appears on the cleaning calendar" is no longer asserted. The stay is checked in the DB only.
- Dashboard: the "Tue 27 Oct" table text check is now a loose "27" check on the sheet title.

## Command results
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py -q --tb=short -rfs` (whole file): `26 passed in 47.87s`, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q --tb=short -rfs` (whole file): `19 passed in 46.10s`, 0 skipped.

## Deviations
- Did not read `docs/tasks/0815-report.md` or `0833-report.md`; selectors came from `dashboard-calendar.js` and the two new tests (same as part A).
- Test-only fixes applied after first runs: `cal_view=calendar` on the dashboard's /cleaning URL (the page opened in gantt by stored preference), and the turnover read moved after its tag wait.

## Questions
- Accept the lost coverage above, or add a product hook for booking-bar geometry and stays on /cleaning?
- The dashboard day click after closing a booking sheet opens the day sheet instead of the Stay form. Is that intended? The test works around it.

## Owner steps left
- Review the diff, then stage, commit and PR as usual. Part A and B can go together.
