# 0410 report

Status: review

- Files: `_components.html` (`choice_card` macro), `setup_wizard/automation.html`, `host.css` (old wizard radio rules removed), `host2.css` (0410 block, radio/checkbox focus and accent, 0284 lists), `guest_form_admin.html`, `_smart_locks_panel.html`, `base.html` (host 20261025-0410, host2 20261025-0410b), `static_versions.json`, `test_onboarding_wizard_browser.py`.
- Tests: wizard browser, static versions, design guardrails, smart locks, host geometry: 116 passed, 0 skipped.
- New test `test_choice_card_selects_from_anywhere`: EN/CS/VI at 390, 1280, 2000, sidebar open and collapsed; clicks the empty card area, checks the "?" does not select, no outline or box-shadow on mouse focus, coral accent, keyboard ring on the card. Shots: `screenshots-0410/`.
- Deviations: the test walks the wizard to the automation step first, scrolls the card to the centre (phone bars), clicks the card's left padding.
- Owner: merge, deploy (new `?v=` keys).
