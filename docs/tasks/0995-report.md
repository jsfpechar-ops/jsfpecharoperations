# 0995 report

Status: blocked

## Files changed
- App/app/static/app2.css, App/app/templates/_property_calendars.html, App/app/templates/_property_editor.html, App/app/host_i18n.py, App/app/static/app.js, App/app/templates/base.html (steps 1 to 7)
- App/tests/static_versions.json (manifest regenerated)
- App/tests/test_host_property_deeplink_browser.py (new; step 8; settle-wait added in step 9)
- App/tests/test_host_property_controls_browser.py (step 9: count 10 to 8, feed-url-details selectors removed, URL asserted visible)

Local commits only, nothing pushed, no PR. Latest: "0995 step 9" (daaea8c).

## Commands (from App/)
1. `tests/test_host_property_controls_browser.py`: 10 passed, 0 skipped (42 s).
2. `tests/test_host_property_deeplink_browser.py`: FAILED. `assert 0 <= summary["y"] <= 900` with y = -531 at 1280 x 900, after the scroll-settle wait.
3. `tests/test_layout_lint_browser.py`: 4 passed, 0 skipped (242 s).
Not run: the brief's full first and second command sets, context lint, the design-guardrails browser test.

## Deep-link cause (not fixed)
Instrumented run: scrollIntoView is called on `#sec-messages` three times (host.js revealTarget, app.js openSection on load and on the load event, app.js openTarget). Target is at scrollY 1501 when first scrolled. Afterwards the section's document position moves from about 1501 to 1773 and scrollY keeps rising to about 2300, so the summary ends above the viewport. Content above the section keeps growing after load, and nothing re-scrolls. A minimal fix is not identified; the test is not satisfied.

## Screenshots (property-detail, layout-lint)
- 390: Guest link card wraps; "Copy link" sits on its own row under the status text. Leon row is below the fold, not checked.
- 768: "Copy link" sits under the status text in the narrow card, not beside the label. Acceptable, not clipped.
- 1280: "Copy link" on the same row as the Guest link label and status, right side. Matches the brief.
Focus ring not captured in these screenshots.

## Deviations
- Step 9 test edits go beyond the owner's answer: the removed collapse-click lines and the collapsed-state asserts were dropped, since the URL is now always visible.
- Commit "0995 step 9" has the trailer Co-Authored-By: Claude Sonnet 5.5.

## Questions
1. Approve a deeper change to app.js deep-link scrolling (for example, re-scroll after late layout settles), or a different approach?

## Owner steps left
None until question 1 is answered.
