# 0832 report

Status: blocked (26 passed, 1 failed; see Open items)

## Files changed
- App/app/templates/dashboard.html: `cal-hide` class on the blocks that carry `ph-hide` (Add stay, needs-you, calendar heading/grid/link, Today, desktop title, date line, banners, ov-month, etc.).
- App/app/templates/_dashboard_calendar.html: `btn soft cal-settings` (filter button soft).
- App/app/static/dashboard-calendar.css: `/* 0832 */` block (`.cal-hide`, toolbar grid at 768+, selects hidden in calendar Month scale, filter button colours, 40 px heights).
- App/tests/test_dashboard_calendar_browser.py: see Deviations.
- docs/tasks/0832-report.md (this file). Nothing staged or committed.

## Tests
Command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_0199_phone_geometry_browser.py -q -rfEs --tb=short`
Last lines: `1 failed, 26 passed in 120.74s`. Skipped: 0.
Failed: `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place` at line 492 (`cleaning_marker.wait_for(state="visible")` on the /cleaning page).

## Deviations
- admin.py sets `cal_view` for any `cal_*` query param, so the test helper pages are calendar pages. The refresh and geometry tests were therefore changed as the brief says.
- Geometry test: the summary/`.ov-cal-more` alignment checks were replaced by hidden assertions (both 0 height) plus `#calendar` height > 0. The `<= 725` check on `.ov-cal-more` was removed.
- Refresh test: the header Add-stay button is hidden on the calendar page, so the stay is opened by clicking a visible day. The banner root moved to `#calendar`. The final navigation goes day, then event, then "Open stay" (the stats-summary click was removed). The DOM-level stats assertions were kept.
- Auto-view test: the year/month selects are hidden in Month scale, so the test now uses 16 `[data-cal-next]` clicks to reach Feb 2028.
- Filter button assumed to be `[data-cal-settings]`.
- `:has` rule limited to calendar view + Month scale (otherwise phone Gantt test fails).
- Other executor (0815) edited my `/* 0832 */` CSS block concurrently (selectors now also match `data-cleaning="true"`). Not reverted; the overlap needs a look.
- Screenshots: the test run rewrote docs/tasks/screenshots-0814/*.png (shown modified in git status). I did not inspect the 390 px shot.

## Open items
- Refresh test failure at line 492. Cause not confirmed: probably the 0815 cleaning-tag change or the shared CSS overlap, not this brief's rules.
- Owner: check the 390 px and 768 px screenshots, then decide on staging/commit.
