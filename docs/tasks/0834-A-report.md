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
