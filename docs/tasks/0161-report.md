# 0161 report

Status: review

Files: App/app/templates/users.html, App/app/host_i18n.py, App/tests/test_design_guardrails_browser.py.
Row menu now holds a "Manage account" link plus button-only forms; the e-mail, open-workspace and schedule-deletion forms live in `#user-manage` (`?manage=<id>`), no JS needed.
Guard: both tests in test_design_guardrails_browser.py pass (2 passed, 0 skipped). design_lint OK, context_lint OK.
Related unit/browser tests: 195 passed, 1 failed (test_property_create_browser setup-wizard-skip; fails identically without this change).
Deviations: no 390 px screenshot taken. No existing test selected the moved forms.
