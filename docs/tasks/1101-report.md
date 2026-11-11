# 1101 report

Status: review

Files: admin.py (create redirect, test_connection wizard branch, police_letter_read wizard render), property_setup.py (mark_tested_in_wizard), onboarding_wizard.py (wizard_ready, ready_qr), _police_fields.html (police_in_wizard wrap), _setup_ready_card.html (new), _property_editor.html, setup_wizard/police.html and done.html, host_i18n.py (guest message "property"), new tests test_setup_wizard_reuse_1101(.py, _browser.py), five existing test files (expectations only).

Tests: new server file failed 9 of 15 before the change, 15 pass after. Browser file 6 pass. Brief row 1: 500 passed, 0 skipped. Row 3: 73 passed. Row 4: 396 passed. Layout lint: 4 passed, 0 skipped. Row 2 (full host/design set) did not finish in time; subset 0884 geometry + police paste/letter + design guardrails: 58 passed, 1 known-red (guest-new 390 Cancel 43<44).

Deviations: footer buttons are 36 px at 1280 by existing wizard CSS (44 px checked below 1024). The 1100 partial differs from the brief (it already holds the no-credentials line and facility heading), so the wizard h2 help tip was dropped as briefed and nothing else changed.

Screenshots: docs/tasks/screenshots-1101/ (calendar, police, guest_link, done at 390/768/1280, editor-first-setup-390).
