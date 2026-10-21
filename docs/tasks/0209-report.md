# 0209 report

Status: blocked

## Files changed
App/tests/test_stay_fee_property_panel.py (step 0), App/app/templates/_fee_signature_fields.html (new), _stay_fee_fields.html, _property_editor.html, setup_wizard/stay_fee.html, _entity_business_fields.html, App/app/routes/admin.py, App/app/routes/onboarding_wizard.py, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/tests/test_host_ux_acceptance.py, App/tests/test_property_navigation_browser.py, App/tests/test_fee_signature_0209.py (new). No PNGs committed.

## Commands
1. pytest §6.1 set: 127 passed, 4 failed (all in tests/test_entity_editor_fields.py: test_the_remove_checkbox_only_shows_with_a_stored_signature, test_the_entity_forms_keep_their_contract, test_entity_lookup_keeps_typed_identity, plus one more). Not fixed: the file is not in brief §3.
2. §6.2 browser set: 115 passed, 0 skipped.
3. design_lint: OK.
4. Screenshots: skipped (budget).

## Test pins
Step 8b: added fee_signature_section and signature_file to SETTINGS_NAMES. Known failures left as is (three_views_four_groups, create_offers_the_calendar_first).

## Deviations
Done: steps 0 to 9. Left: resolve the 4 test_entity_editor_fields.py failures (they assert the signature on Business details, which step 4 removes); needs owner decision on editing that file; screenshots.

## Owner steps left
Decide whether to update tests/test_entity_editor_fields.py, then rerun §6.1.
