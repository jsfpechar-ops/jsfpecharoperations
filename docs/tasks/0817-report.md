# 0817 report

Status: done (executor stopped at its cap; orchestrator finished it).

Files: App/app/static/dashboard-calendar.css, App/app/templates/_dashboard_calendar.html (css ?v=20261102-0817c, close and Cancel buttons use `btn soft`), App/tests/static_versions.json, App/tests/test_dashboard_phone_browser.py, docs/tasks/screenshots-0814/.

Deviations:
- Item 9 applies to the create dialog select `#cal-property`, not the filter select `[data-cal-property]` (the filter must match the other toolbar controls).
- The × and Cancel were white/coral because `body.v2 .btn:not(.soft)` forces white text; fixed with the `soft` class instead of more CSS.
- Grid, week rows and weekday header sit on the page background instead of a white box.

Tests: the six section 6 files, 48 passed, 0 skipped. Lint OK.
