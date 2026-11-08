# 1011 report: street mandatory

Status: review
Done: steps 1 to 6. Step 7 (PR) not opened, per owner/coordinator instruction.

## Files changed
- App/app/routes/admin.py: `_create_address_errors` refuses a blank `addr_street`. validate_apartment untouched.
- App/app/validation_i18n.py (CS), App/app/host_vi_i18n.py (VI): "Street is required." strings.
- App/app/templates/_property_address_fields.html: street gets `required` and the star.
- App/app/host_i18n.py (EN, CS), App/app/host_vi_i18n.py: street hint text.
- Tests flipped or added: test_wizard_old_look_0953.py, test_required_stars.py, test_property_address_required.py (5 new tests).
- Street added to create POST fixtures: test_property_create_browser.py, test_property_operator_defaults.py, test_property_navigation_browser.py, test_property_form_save.py, test_host_flash_outcomes.py.
- test_host_property_controls_browser.py: fills `#addr_street` before the blank-operator submit (client-side `required` on street blocked the submit, so the server alert never showed).

## Test results
- validation_i18n + validation: 37 passed. host_i18n + ruian: 23 passed. Pinned address tests: 15 + 19 passed.
- test_property_create_browser.py: 13 passed.
- test_onboarding*/test_property_*/test_first_*: 294 passed, 57 skipped ("browser not required" gate in test_onboarding_wizard_browser.py), 0 failed.
- Any host template row (guardrails, layout lint, 0884, 0953 browser, 0850): 34 passed, 0 skipped.
- test_host_flash_outcomes.py + test_host_property_controls_browser.py: 34 passed.
- Not rerun after the last fixes: the full test_host_*/test_host_geometry row (last full run: 3 failed, now fixed; 1 skipped by UBYHOST_REQUIRE_BROWSER gate).
- Ignored as environmental: test_door_code_window_browser.py webkit (Playwright webkit binary missing).

## UX gate (rule 10), 390 px, EN
- New property form (/apartments/new?lang=en), screenshot /mnt/project-files/ux-shots/street/new-property-390-en.png: "Street" shows the red star, same as House number and Postcode; the help "?" sits beside it; the input has the same width as the others; no horizontal overflow (scrollWidth 390). Orientation number stays unstarred.
- Editor address section (/apartments/{id}?view=settings&section=property&lang=en), screenshot /mnt/project-files/ux-shots/street/editor-address-390-en.png: label "Street*", no horizontal overflow (scrollWidth 390). Image not inspected in detail.
- Checklist from docs/design/design-system.md not ticked: not run in this session.

## Deviations
- Step 6 screenshots were taken from a temporary pytest file (deleted again); 360 and 1280 px not taken (layout did not change).
- The operator-controls browser test was not run on origin/main (git stash not allowed); its failure is explained by the new required street blocking submit client-side.

## Owner steps left
- Open the screenshots above and confirm the street star.
- Open the PR against main (not done here) and merge with scripts/merge-pr-on-green.sh once green.
