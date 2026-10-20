# 0193 report

Status: blocked
Done: steps 1 to 5. Left: step 6 (screenshots, new browser tests for chip text and dialog centre, cleaning_settings/cleaning_edit/share form restyle beyond the fieldset, catalog.json entries not needed since no new class names).

Files: App/app/static/dashboard-calendar.js, App/app/static/dashboard-calendar.css, App/app/static/cleaning.css, App/app/templates/_dashboard_calendar.html, App/app/templates/_cleaning_screen.html (reverted to original, no change), App/app/templates/base.html, App/app/templates/cleaning_shared.html, App/tests/static_versions.json, docs/tasks/0193-cleaning-polish.md, docs/tasks/0193-report.md.

Commands:
- static versions: 3 passed
- cleaning tests (test_cleaning*.py): 38 passed, 21 skipped (browser tests, env not set)
- cleaning browser with UBYHOST_BROWSER_EXECUTABLE: 21 passed, 0 skipped
- design_lint: FAIL, pre-existing (smart_locks.html enforced template missing), not this brief
- context_lint: FAIL, pre-existing (0192 report missing)

Deviations: the cleaning.js version was not bumped (file unchanged). Mobile month view still hides the chip label (compact dots).
Questions: none.
Owner steps left: none. Screenshots and browser tests for the new behaviour are not done.
