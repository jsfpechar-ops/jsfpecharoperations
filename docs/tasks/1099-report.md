# 1099 report

Status: blocked (60 tool-call stop and the "more than 6 existing test files" stop; see Deviations)

## Files changed
App/app/property_setup.py (tested flag, SECTION_MINUTES, SETUP_ORDER, mark_tested, is_first_setup, section_done, open_section, setup_complete), App/app/routes/admin.py (mark_tested at the two ok sites, auto-finish guard, short-editor context and ready card in _render_apartment_detail, create redirect), App/app/templates/_property_editor.html (sec_open / sec_state macros, labels, letter disclosures, ready card, data-start-section, return_to, continue link), App/app/host_i18n.py (_SHORT_EDITOR_1099_STRINGS en+cs), App/app/static/app2.css (ready card), base.html (app2.css 20261111-1099b), static_versions.json, tests/test_first_setup_open_section.py, tests/test_host_short_editor_browser.py, screenshots-1099 (12 PNGs).
Existing tests edited (open-state only): test_police_letter_flow.py, test_host_police_letter_browser.py, test_host_police_letter_guard_browser.py (open the letter disclosures with `d.open = true` instead of a summary click; one geometry test closes the find disclosure first).

## Tests
- New server tests on unchanged main: 13 failed, 1 passed. After: 14 passed.
- Section 6 command 1 (server row): 172 passed, 0 failed.
- New browser file: 15 passed, 0 skipped. Police letter browser files: green, 0 skipped.
- Section 6 command 2 (browser row): 80 failed, 93 passed, 0 skipped. 75 in test_onboarding_wizard_browser.py (asserts create redirects to /setup/calendar; D7 changes that, but the brief says wizard tests stay untouched). Others: test_property_navigation_browser.py (2: create redirect; Basic details open by default), test_0541_property_page_phone_browser.py (1: Basic details open by default), test_required_stars.py (1: greps the old `t('automation.password')` label), test_design_guardrails_browser.py (1: the known guest-new 390 Cancel 43<44).
- Not run: layout lint, v2 row (stopped at the cap).
- ruff, design_lint, context_lint: OK.

## Deviations
- Inline success flash still opens its section in later-edit mode (keeps the 0955 notice visible); in first setup and on the ready render only an error flash opens it.
- An explicit `?section=` or `?view=bookings` wins over the first-setup open section (needed for test_0534 to stay as written).
- Done: steps 1 to 4. Left: fix the 4 existing browser files above (needs an orchestrator call: brief says wizard tests stay untouched but D7 breaks 75 of them; total edited files would be 7 > 6), step 5 (layout lint + UX gate), section 6 commands 2 and 3 green.
