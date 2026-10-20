# 0193 report

Status: review
Done: steps 1 to 5. Chip label, centred create dialog, form restyle of the property instructions, share and edit pages, browser tests for chip text and dialog centre (both tabs, scrolled and unscrolled, 1280x800 and 390x844), catalog entries for the six new classes, screenshots.

Files: App/app/static/cleaning.css, App/app/static/dashboard-calendar.css, App/app/templates/base.html, App/app/templates/_dashboard_calendar.html, App/app/templates/cleaning_shared.html, App/app/templates/cleaning_settings.html, App/app/templates/cleaning_edit.html, App/app/templates/cleaning_shares.html, App/tests/test_cleaning_browser.py, App/tests/static_versions.json, docs/design/catalog.json.

Found in screenshots: docs/... host-design0123.css line 76 (`body.host-workspace .cleaning-panel { padding:20px 0 }`) and line 77 (`.cleaning-page h2 { font-size:24px }`) overrode the form panels, so the panels had no side padding. New rules use the `body.host-workspace` prefix to beat them.
Dialog: the phone sheet is now centred; the form has min-height min(680px, 90dvh-24px) so Stay and Cleaning tabs keep the same top edge.

Commands (last lines):
- tests/test_static_versions.py: 3 passed
- design shell, static versions, a11y guard, guardrails, test_cleaning*.py (-x -rs): 87 passed, 0 skipped
- calendar-review set (test_cleaning, test_cleaning_browser, test_dashboard_calendar, test_dashboard_calendar_browser): 109 passed, 0 skipped
- design_lint: OK. context_lint: OK. ruff E9,F63,F7,F82,F401,F841: All checks passed

Screenshots: /mnt/project-files/design-reset/checkpoint-4-shell-fixes/cleaning-{calendar,add-stay,add-cleaning,instructions,share,edit}-{390,1280}.png, plus cleaning-add-*-scrolled.png and cleaning-calendar-1280-chips.png.

Deviations: the 1280 montage was reviewed before the host-design0123 padding fix; the 390 montage was reviewed after it. The same rules apply at 1280, so a re-look at 1280 is still owed. The Add cleaning dialog has empty space at the bottom because of the shared min-height.
Questions: on 390 px the "Add stay" action is hidden by the phone action bar, so the stay dialog is reachable on phone only from elsewhere. The test opens it through its handler. Owner to decide whether it should show on phone.
Owner steps left: none.
