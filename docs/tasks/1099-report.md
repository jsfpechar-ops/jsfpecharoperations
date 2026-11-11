# 1099 report

Status: review

## Files changed
App/app/property_setup.py (tested flag, SECTION_MINUTES, SETUP_ORDER, mark_tested, is_first_setup, section_done, open_section, setup_complete), App/app/routes/admin.py (mark_tested at the two ok sites, auto-finish guard, short-editor context and ready card in _render_apartment_detail, create redirect), App/app/templates/_property_editor.html (sec_open / sec_state macros, labels, letter disclosures, ready card, data-start-section, return_to, continue link), App/app/host_i18n.py (_SHORT_EDITOR_1099_STRINGS en+cs), App/app/static/app2.css (ready card), base.html (app2.css 20261111-1099b), static_versions.json, tests/test_first_setup_open_section.py, tests/test_host_short_editor_browser.py, screenshots-1099 (12 PNGs).
Existing tests edited (open-state only): test_police_letter_flow.py, test_host_police_letter_browser.py, test_host_police_letter_guard_browser.py (open the letter disclosures with `d.open = true` instead of a summary click; one geometry test closes the find disclosure first).

## Tests (fix round)
- New server tests: 13 failed and 1 passed on unchanged main; 14 passed after.
- Server rows (section 6 cmd 1 plus test_property_*, test_apartment*, all test_*_i18n, test_property_readiness, test_required_stars): 349 passed.
- Layout lint: 4 passed, 0 skipped, no new ALLOW.
- v2 row: 183 passed, 0 skipped (after the 320 px state-line fix).
- Browser row (section 6 cmd 2): 173 passed, 1 failed, 0 skipped. The failure is the known local guest-new 390 "Cancel" 43<44 in test_design_guardrails_browser.py (green on CI main).
- Known on clean main and not fixed: test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state, test_reporting_help_0097.py browser test.
- ruff, design_lint, context_lint: OK.

## Existing test edits and why
- test_police_letter_flow.py, test_host_police_letter_browser.py, test_host_police_letter_guard_browser.py: the letter disclosures now start open in first setup, so the tests set `open = true` instead of clicking the summary (a click closed them); one geometry test closes the find disclosure first.
- test_onboarding_wizard_browser.py: `_create` now asserts the create redirect lands on the editor; the tests already open the wizard steps directly. New test `test_create_lands_on_the_editor_in_first_setup`.
- test_property_navigation_browser.py: the editor-shape test uses a finished property and checks all closed by default plus Basic details open with `?section=property`; the create test asserts the editor redirect, then opens `/setup/calendar` directly; the no-JS notes save opens `?section=property`.
- test_0541_property_page_phone_browser.py: the property is marked tested and finished (later-edit rules keep `section=` in return_to).
- test_host_ux_acceptance.py: p1 is marked tested and finished; two tests open Basic details through `?view=settings&section=property` (a finished property opens closed, as D4 says).
- test_required_stars.py, test_property_readiness.py: the new police label keys (setup.label.*); intent unchanged.

## Two changes from the brief
- A success inline flash still opens its section in later-edit mode (keeps the 0955 notice visible); in first setup and on the ready render only an error flash opens it.
- An explicit `?section=` or `?view=bookings` wins over the first-setup open section (keeps test_0534 as written).

## Other
- 320 px: the state line wrapped (v2 mockup check), so it is 13 px with the same line height under 360 px. app2.css key 20261111-1099d.


## Fix round 2
- Letter first: in first setup the police "Missing" list is hidden while the letter picture and paste box lead; new geometry assertion (picture above any visible missing block).
- Ready card: Copy link and Copy PIN are `ui-btn-secondary` (no primary on the card); the custom card rule with raw `#fff` is gone (`ui-section-card` styles it from 768 px; flat on phone like other section cards); 16 px gap below on phone; text without "PIN" when there is no PIN (new key `setup.ready.text_no_pin`, en+cs). app2.css key 20261111-1099f.
- test_police_letter_flow.py: one real summary click restored (close and reopen "Where do I find these?").
- test_property_create_browser.py: create redirect asserts the editor in first setup; wizard steps opened directly. The Page.fill timeout had the same cause. 13 passed, 0 skipped.
- Runs: layout lint 4 passed; v2 row + static versions 186 passed; browser row 220 passed, 1 failed (known local guest-new "Cancel" 43<44); all 0 skipped. Short-editor browser file and static versions rerun after the last margin fix: 18 passed.
