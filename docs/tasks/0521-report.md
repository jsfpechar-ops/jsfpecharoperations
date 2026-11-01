# 0521 report: Overview 14-day calendar

Status: blocked

## Done
- Step 1 (template `data-days`, `?v=20261101-0521`): committed.
- Step 2 (script `fixedDays`): committed, plus two fix commits. `renderGantt()` and the day-number label also needed the fixed range (not in the brief). Template `?v=` bumped to `20261101-0521b` because the manifest refused the change.
- Step 3 (`static_versions.json --write`): committed.
- Step 4 (`App/tests/test_0521_overview_14_days_browser.py`, 3 tests): all pass, 0 skipped.
- Step 5 (screenshots): `docs/tasks/screenshots-0521/calendar-overview-14-days-cs-1280.png`, `calendar-overview-14-days-cs-390.png`. Both looked right.

## Test results
- New test file: `3 passed in 9.19s`.
- Battery (`test_dashboard_calendar_browser.py`, `test_dashboard_calendar.py`, `test_dashboard_phone_browser.py`, `test_static_versions.py`, `test_cleaning_browser.py`): `10 failed, 68 passed in 323.09s`.
- Failing, all on `/` at computer width (they expect the month view, `.cal-week`, or the view switch):
  - test_dashboard_calendar_browser.py: test_auto_view_threshold_filter_and_manual_override, test_drag_nights_create_persist_and_open_details, test_keyboard_selection_cancel_and_overlap_confirmation, test_reverse_gantt_drag_prefills_the_property_without_saving, test_calendar_geometry_locales_and_screenshots, test_calendar_week_boundary_clips_fractional_checkout_with_continuation_edges, test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place, test_default_calendar_url_is_clean_and_specific_views_survive_reload, test_explicit_auto_view_survives_reload_over_a_saved_manual_preference
  - test_dashboard_phone_browser.py: test_phone_dashboard_compact (expects `.cal-view-segment`)
- `open_page()` in the browser test waits for `.cal-week` on `/?cal_date=2026-10-01`, so most of these fail in the helper.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none from this change).

## git diff --stat origin/main
Includes the branch's brief commits (`docs/tasks/0520-*`, `docs/tasks/0521-*`), which are not mine. My files: `App/app/static/dashboard-calendar.js`, `App/app/templates/_dashboard_calendar.html`, `App/tests/static_versions.json`, `App/tests/test_0521_overview_14_days_browser.py`, `docs/tasks/screenshots-0521/`.

## Deviations
- Step 2 fix: `renderGantt()` and the day-number label used the month range, so the 14-day range had no effect on the grid.
- Test helpers are imported from `test_dashboard_calendar_browser.py` rather than copied.
- No assertions were updated. Section 8 covers one assertion; the failures span about ten tests, so I stopped.

## Questions for the owner
1. Should the 10 existing tests move to a month-calendar page (`/cleaning`), or be rewritten for the 14-day Overview?
2. Should `open_page()` change its default URL?
3. Should `test_phone_dashboard_compact` (`.cal-view-segment`) be expected to pass on `/`?

## Owner steps left
- Decide on the questions above, then rerun the battery.
- No push or PR made (executor rules).
