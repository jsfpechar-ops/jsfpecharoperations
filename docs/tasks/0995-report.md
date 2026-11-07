# 0995 report

Status: blocked

## Files changed
- App/app/static/app2.css (steps 1, 2, 4)
- App/app/templates/_property_calendars.html (step 3)
- App/app/templates/_property_editor.html, App/app/host_i18n.py (step 5)
- App/app/static/app.js (step 6)
- App/app/templates/base.html (step 7)
- App/tests/static_versions.json (manifest regenerated)
- App/tests/test_host_property_deeplink_browser.py (step 8, new)

Commits are local only (not pushed, no PR): "0995 step 1", "0995 step 4", "0995 step 2", "0995 step 3", "0995 step 5", "0995 step 6", "0995 step 7", "0995 step 7 manifest", "0995 step 8".

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_property_*.py tests/test_host_*.py tests/test_host_geometry.py tests/test_host_property_deeplink_browser.py -q -rs --tb=short -x`
   Result: 1 failed, 357 passed, stopped at first failure.
   `E   AssertionError: (390, {'count': 8, 'vw': 390, 'bad': []})` / `assert (8 >= 10)`
   Cause: test_host_property_controls_browser.py line 832 expects 10 fit elements. The URL collapse is gone, so there are 8. Line 842 selects `.feed-url-details[open] .feed-url-value`, which no longer exists. Fixing this needs a change to that test file, which brief section 3 does not list.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_property_deeplink_browser.py -q -rs --tb=short`
   Result: 1 failed. `assert 0 <= summary["y"] <= 900` with `{'y': -426.296875, 'height': 52}` at 1280 x 900. The section summary ends up above the viewport. Not verified: the test checks as soon as details.open is true, possibly before the load-event scroll.

## Not run
Second command set, context lint, UX gate, screenshots. No screenshots were taken.

## Deviations
- Brief line numbers were off (focus rule at 2600, not 2597; .sc-actions at 2611). All anchors matched verbatim, so I applied them by text.
- Step 2's flex:1 1 140px went on the `.sc-main` rule (the brief said line 2605, which is a different rule).
- Step 4 was committed before steps 2 and 3 because of a scripting error. Content matches the brief.
- The test imports the host and base fixtures from test_host_property_controls_browser.py instead of copying them.
- The dead `.feed-url-details` rules in app2.css (around lines 2813 to 2817) were left in place.

## Questions
1. OK to change line 842 of test_host_property_controls_browser.py (and the count at line 832) to match the new markup?
2. How should the deep-link test wait for the load-event scroll?

## Owner steps left
None until the questions above are answered.
