# 0986 report

Status: blocked
Done: steps 1 to 8 (step 3 applied but not verified). Left: "?" inline fix, feed URL box check, two failing 0534 tests (pre-existing, see Deviations).

## Files changed
- App/app/templates/apartment_form.html: restored from origin/main (step 2).
- App/app/static/app2.css: help-mark rules (step 3), tiles to main's grid (step 4), setup card rule (step 5), feed-url-details padding and summary gap (step 6).
- App/app/templates/base.html: cache key 20261106-0986. App/tests/static_versions.json regenerated.
- App/tests/v2_mockup.py: one page-scoped override `property:.pv` (setup card is class `pv`; radius 14px, border rgb(235, 235, 231)).
- App/tests/test_0541_property_page_phone_browser.py: strip row pin 1280 and 1600 from 1 to 2 (main's 3-column grid at 640 px+).
- docs/tasks/screenshots-0986/: four PNGs copied.

## Commands (last lines)
- test_layout_lint_browser.py: 4 passed, 0 failed, 0 skipped.
- test_0710 -k propert: 28 passed, 0 failed, 0 skipped (after the `property:.pv` override; before it, 4 failed).
- test_property_readiness + test_0534 + test_static_versions: 32 passed, 2 failed (both in test_0534).
- test_host_property_controls_browser + test_0541 + test_property_navigation_browser: 36 passed, 1 failed before the pin change; test_0541 alone now 7 passed, 0 skipped.
- context_lint: OK. design_lint: OK.

## Screenshot at 390 (property-detail-configured-390.png)
- Round back button: yes (main style).
- "?" after the name: NO. It still sits alone on its own line under the title.
- Tiles: even 2-column grid, equal rows.
- Setup card: below the tiles, full width, tile style. Partly covered by the bottom tab bar in the shot (sticky bar, not a layout change).
- "SETTINGS" label: visible above the accordion.
- Feed URL box padding: not checked in the open-390 shot (not reviewed).

## Deviations
- Step 3 "?" inline: CSS applied but the 390 shot shows it still on its own line. Not fixed.
- test_0534 test_0536_setup_continue_is_the_first_card_under_the_pills and test_aside_has_cards_and_links_to_each_section fail with substring not found: they search for `<div class="form prop-form-single">`, but the template (identical to origin/codex base) renders `class="form prop-form-single property-detail"`. Not caused by this brief; assertions not changed.
- v2_mockup.py override and test_0541 pin changes are brief step 7 pins, with comments.

## Questions / owner steps
- Owner: decide whether the 0534 string pin should match `property-detail` or the class be dropped.
- Owner: review the `property:.pv` override (setup card deliberately differs from the mockup radius and border).
