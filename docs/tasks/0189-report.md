# 0189 report

Status: blocked

Done: steps 1 to 6 (shared classes, heading spacing, property sections, calendar CI, tests). Left: smart-locks screenshots (390, 1280, 2000) and visual check of the smart-lock rows.

Files changed: App/app/static/host2.css (nested rule excludes .ui-section-row; row margin; h2 spacing in panels; property-section panel rule; split-column padding-top kept only on non-panel columns; phone padding; ?v=20261020-0189d), App/app/static/host-design0123.css (property-section removed from border-top rule; ?v=20261020-0189c), App/app/templates/base.html, App/tests/static_versions.json, App/app/templates/_property_editor.html (ui-section on 10 property sections), App/app/templates/smart_locks.html (.smart-lock-row = ui-section ui-section-row), App/app/templates/dashboard.html (empty ui-section wrapper around the calendar removed; the calendar is already a bordered panel), App/app/templates/guide.html, App/app/templates/reservation_detail.html, App/app/templates/cleaning_settings.html, App/tests/test_design_guardrails_browser.py (from steps 1 to 5).

Commands (last lines):
- Browser set (5 files): `26 passed, 1 warning in 99.96s`, 0 skipped.
- calendar-review (test_cleaning, test_cleaning_browser, test_dashboard_calendar, test_dashboard_calendar_browser): `104 passed in 69.44s`, 0 skipped. Earlier failure: the dashboard wrapper panel doubled the stats-to-calendar gap to 61 px (limit 44); fixed by removing the wrapper, threshold not changed.
- test_static_versions: 3 passed.
- context_lint.py: `context lint: OK` (warnings only).

Screenshots: checkpoint-4-shell-fixes bordered-{settings,reservation-detail,stay-fees,admin-users}-{1280,2000,390}.png from earlier, bordered-admin-users re-taken after the heading fix and reviewed at 1280 (no clipping, no double border). bordered-smart-locks: /smart-locks redirected to the Properties page in the test fixture, so the captured image is not the smart-locks page. Not reviewed at 2000 or 390 after changes.

Pages changed (screenshot needed): smart-locks (not verified), admin-users (done), dashboard, property setup pages.

Questions: none.
Owner steps left: none. Next session: find why /smart-locks redirects for the fixture owner, retake bordered-smart-locks at 1280, 2000, 390, and check the .smart-lock-row panels.
