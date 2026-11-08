# 1011 report: street mandatory

Status: blocked
Done: steps 1 to 5 (partly). Left: step 5 (4 host failures, see below), step 6 (UX gate screenshots), step 7 (PR, not opened here by brief instruction).

## Files changed
- App/app/routes/admin.py: `_create_address_errors` refuses a blank `addr_street` (validate_apartment untouched).
- App/app/validation_i18n.py (CS), App/app/host_vi_i18n.py (VI): "Street is required." strings.
- App/app/templates/_property_address_fields.html: street gets `required` and the star.
- App/app/host_i18n.py (EN, CS), App/app/host_vi_i18n.py: street hint text.
- Tests flipped or added: test_wizard_old_look_0953.py, test_required_stars.py, test_property_address_required.py (5 new tests, pass).
- Street added to POST fixtures: test_property_create_browser.py, test_property_operator_defaults.py, test_property_navigation_browser.py, test_property_form_save.py.

## Commands (last lines)
- validation_i18n + validation: 37 passed.
- host_i18n + ruian: 23 passed.
- required_stars + wizard_old_look_0953 + property_address_required: 19 passed (then 15 passed after new tests).
- test_property_create_browser.py: 13 passed.
- test_onboarding*/test_property_*/test_first_*: 294 passed, 57 skipped ("browser not required" gate in test_onboarding_wizard_browser.py), 0 failed.
- Any host template row (guardrails, layout lint, 0884, 0953 browser, 0850): 34 passed, 0 skipped.
- Host pages row (test_host_*, test_host_geometry): 241 passed, 1 skipped (UBYHOST_REQUIRE_BROWSER gate), 3 failed. Rerun with --lf: 4 failures listed below.

## Open failures (not fixed, executor stopped per brief §8)
- test_host_flash_outcomes.py:181 and :202: a property create POST without `addr_street` (400). Likely fixed by adding `addr_street` to that POST, unverified.
- test_host_property_controls_browser.py:369 `test_required_operator_controls_in_browser`: `#operator-message` not visible on /apartments/new. Not yet checked whether it is a street issue.
- test_door_code_window_browser.py:126 (webkit): Playwright webkit binary missing in this container (environment, not this change).

## Deviations
- Step 6 (390 px screenshots and PR text) not done.
- Step 7 PR not opened (brief said do not open PR here).
- Brief lists `_property_address_fields.html` line 23 as optional; the replacement line in the brief was applied exactly.
- Existing `_create_address_errors` docstring extended ("and street").

## Questions
- Should the browser-gated tests (UBYHOST_REQUIRE_BROWSER) run in CI with the browser enabled? Skips were not verified.

## Owner steps left
- Executor or next session: fix the 3 open host failures, then run step 6 screenshots.
