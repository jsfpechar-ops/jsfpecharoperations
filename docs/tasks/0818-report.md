# 0818 report

Status: blocked (items 1-4 done, item 5 not done; see Open item)

## Files changed

- `App/app/static/dashboard-calendar.css`: new 0818 block appended at the end (items 1-4).
- `App/app/templates/_dashboard_calendar.html`: css `?v=20261102-0818`, js `?v=20261102-0818`; prev, Today and next buttons get the `soft` class.
- `App/tests/static_versions.json`: regenerated.
- `App/tests/test_dashboard_calendar_browser.py`: assertions added to `test_month_tiles_and_side_panel` (controls clear of the panel, grid reaches the panel, arrow and Today not coral, 768 chips have 0 px text, `.havel-fab` hidden with the panel open).
- `docs/tasks/screenshots-0814/*.png`: retaken by the test run with `UBYHOST_TASK_SHOTS=1`.
- `docs/tasks/0818-report.md`: this file.

## Tests

Command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_cleaning_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short -rfEs`

Last line: `53 passed in 166.93s (0:02:46)`. 0 failed, 0 skipped.
Lint: `context lint: OK`.

## Deviations

- Item 2 (grid width): the calendar root gets `margin-right` when the panel is open: `calc(360px + 16px - 36px)` at 1024 px and up, `calc(320px + 16px - 20px)` at 768-1023 px. The 36 px and 20 px are the page wrap's measured right gutter. They are hard-coded, so they break if the wrap padding changes. The earlier `padding-right` approach left the grid about 100 px short because the dashboard has a left sidebar.
- Item 1: at 1280 with the panel open, the month title truncates ("Octo...") because the controls fill the row. Not fixed.
- Item 3: the JS renders 2 chips plus `+n` (`dashboard-calendar.js` line 312, `slice(0, 2)`). CSS cannot show 3 bars. At 768-1023 the view shows 2 bars plus `+n`. Showing 3 needs a JS change that would also change the text chips at 1024 px and up, so I did not make it.
- Item 4: done in CSS for every width: `body:has(.dashboard-calendar.has-panel) .havel-fab { display:none }`.
- Section 4 said to edit the 0816 block. I appended a 0818 block instead and left the 0816 rules as they were.

## Open item (blocked): item 5, full-page calendar on desktop

Not implemented. No route change was needed; the blocks are in `dashboard.html`. I tried hiding them with `cal-only-hide` classes and reverted the attempt. `cal_view` is set for any query parameter starting with `cal_` (`App/app/routes/admin.py:554`), so `?cal_date=` pages count as calendar pages too. Hiding the blocks on desktop breaks existing tests that use them:

- `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place` clicks `[data-dashboard-refresh="stats"] .needs-you-more > summary` (line 584) and appends a banner to `[data-dashboard-refresh="work"]` (line 569).
- `test_calendar_geometry_locales_and_screenshots` expects the stats block and `.ov-cal-more` to have height at 1024 px and up.

Owner decision needed: (a) hide the blocks on the calendar page and rewrite those two test flows to use another page, or (b) keep the dashboard blocks on desktop. The tests for item 5 were not added.

## Owner steps left

None for this brief. Deploy is not involved. The orchestrator commits.
