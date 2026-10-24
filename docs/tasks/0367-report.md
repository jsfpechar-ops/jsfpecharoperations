# 0367 report

Status: review

Files changed: App/tests/test_0199_phone_geometry_browser.py, App/tests/test_wp28_geometry.py, docs/tasks/0367-report.md. No app file touched.

- test_0199 `test_lock` (F gap 218): stale. Commit 97ac958 (2026-10-23) put the door-code window card between the Door lock intro and the panel. F now measures the larger of intro-to-window and window-to-panel gap (still <= 24 px), so a blank hole is still caught.
- test_wp28 `test_operator_signature_block_is_styled`: stale. Brief 0209 moved the signature from /entities to Reporting & fees (`/apartments/<id>?view=settings&section=reporting`); 0282 moved Clear and Upload into a dialog, in separate rows. Test now loads the new page, checks block border and radius, opens the dialog and checks buttons within each action-group are level.

Commands: test_wp28 7 passed (twice); test_0199 3 passed (twice); guardrails + a11y guard 14 passed; 0 skipped.
Owner steps: merge when CI is green.
