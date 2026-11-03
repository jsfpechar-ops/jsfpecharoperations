# 0816 report

Status: done (two executor runs hit their cap; orchestrator finished it). Review fixes follow in 0818.

Files: dashboard-calendar.js (`tiles()`, chips, panel from click/drag/Enter; a plain click keeps the earlier single-day selection so click-click makes a range), dashboard-calendar.css (0816 block, Add 48 px at ≥768), _dashboard_calendar.html (?v=20261102-0816d), static_versions.json, test_dashboard_calendar_browser.py, test_dashboard_phone_browser.py, screenshots-0814/ (768-1440 shots, written only with UBYHOST_TASK_SHOTS=1).

Old assertions changed: month bars (`.cal-event`) replaced by `.cal-tile-chip` or the panel list; day click now opens the panel and Add opens create; month row height cap 102 -> 140 (tiles are 96/112 px by design); the week-boundary clipping test runs in week scale where bars remain.

Tests: six section 6 files, 53 passed, 0 skipped (calendar file rerun after the last CSS change: 22 passed). Lint OK.
