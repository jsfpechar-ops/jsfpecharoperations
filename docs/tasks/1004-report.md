# 1004 report

Status: blocked

Deviations: Done: steps 1 to 5 (CSS, template cache key, test assertions), committed as `1004 step 1` to `1004 step 5`. Left: §6 command 2 (layout lint), command 3, screenshots, design catalog, extra request (cleaning panel overlay), this report's screenshot section. Stopped by §8: a test failed twice.

Files changed: `App/app/static/dashboard-calendar.css` (rule deleted, `top:28px` to `top:40px`, 3 px left border removed), `App/app/templates/_dashboard_calendar.html` (`?v=20261107-1004`), `App/tests/test_dashboard_calendar_browser.py` (2 assertions now `== 2`). No base.html reference to dashboard-calendar.css was found, so no base.html bump.

Command 1 result (`test_dashboard_calendar_browser.py`, `test_0955_calendar_toolbar_stable_browser.py`, `test_dashboard_calendar.py`, browser required): 125 passed, 1 failed: `test_0891_airbnb_month_tiles_and_pills[768]`, `pill["left"]` 45.7 vs expected 52.9. The same test passes alone with and without the 1004 changes. In the full set it fails on the pre-1004 baseline too (5 failures there, including the same 0891 pill assertion), so it looks pre-existing and order-dependent, not caused by the CSS change. Not fixed; owner or orchestrator to decide.

Command 4 (`python3 scripts/context_lint.py`): OK.

Questions: Should the 0891 pill test be fixed in its own brief?

Owner steps left: none yet; merge waits on the test decision and the unfinished UX gate.
