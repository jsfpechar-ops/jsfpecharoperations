# 1004 report

Status: blocked

Deviations: Done: steps 1 to 5 (CSS, template cache key, test assertions), committed as `1004 step 1` to `1004 step 5`. Left: §6 command 2 (layout lint), command 3, screenshots, design catalog, extra request (cleaning panel overlay), this report's screenshot section. Stopped by §8: a test failed twice.

Files changed: `App/app/static/dashboard-calendar.css` (rule deleted, `top:28px` to `top:40px`, 3 px left border removed), `App/app/templates/_dashboard_calendar.html` (`?v=20261107-1004`), `App/tests/test_dashboard_calendar_browser.py` (2 assertions now `== 2`). No base.html reference to dashboard-calendar.css was found, so no base.html bump.

Command 1 result (`test_dashboard_calendar_browser.py`, `test_0955_calendar_toolbar_stable_browser.py`, `test_dashboard_calendar.py`, browser required): 125 passed, 1 failed: `test_0891_airbnb_month_tiles_and_pills[768]`, `pill["left"]` 45.7 vs expected 52.9. The same test passes alone with and without the 1004 changes. In the full set it fails on the pre-1004 baseline too (5 failures there, including the same 0891 pill assertion), so it looks pre-existing and order-dependent, not caused by the CSS change. Not fixed; owner or orchestrator to decide.

Command 4 (`python3 scripts/context_lint.py`): OK.

Questions: Should the 0891 pill test be fixed in its own brief?

Owner steps left: none yet; merge waits on the test decision and the unfinished UX gate.

## Session 2 (extra request, lint, cache keys)

Done: Extra request: `App/app/static/dashboard-calendar.css` at 1024 px and up, `.has-panel` no longer sets the 360 px margin-right, so the day panel (`dialog[data-cal-day-dialog]`, already fixed right, 360 px) overlays the grid; added z-index 20 and a soft left shadow. Tablet 768 to 1023 px gutter unchanged; bottom sheet below 768 unchanged. Cache keys: `_dashboard_calendar.html` `dashboard-calendar.css?v=20261107-1205`, `base.html` `app2.css?v=20261107-1205`, `App/tests/static_versions.json` rewritten by `test_static_versions.py --write`. Design lint: OK (no new classes).

Command 2 (`test_layout_lint_browser.py`, browser required): 4 passed, 0 skipped. Command 3 (`test_cleaning_browser.py`, `test_0956_calendar_rule_colours_browser.py`, `test_static_versions.py`): 78 passed, 0 skipped. `python3 scripts/context_lint.py`: OK.

Not done: (1) Screenshots `calendar-month-1280.png`, `calendar-week-1280.png`, `cleaning-panel-1280.png` were NOT produced. Session login for a standalone script failed (session cookie not set on the test client; with the staging no-login patch the pages timed out in `loaded()`). Not in /mnt/project-files/ux-shots. (2) Grid width before/after the panel opens is unmeasured. (3) `test_dashboard_calendar_browser.py` not re-run after the CSS change. (4) Sections of the test file (command 1) for the 0818 gutter not re-run.

Owner steps left: none. Next: a follow-up brief for the screenshots and the grid-width check; run `test_dashboard_calendar_browser.py` with browser required.
