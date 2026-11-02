# 0741 report

Status: review

## Files changed
- App/app/static/app2.css (phone rules edited in place, 0540 block; 0542 copy-button rule replaced)
- App/app/templates/base.html (app2.css ?v=20261102-0741)
- App/tests/static_versions.json (regenerated)
- App/tests/v2_mockup.py (property entry: phone_mockup, phone_selectors, overrides, missing_ok)
- App/tests/test_0530_properties_chips.py, App/tests/test_properties_table_chips.py, App/tests/test_host_controls_browser.py (step 0)
- docs/tasks/0741-report.md

## Commits (not pushed)
- 1db66ce 0740: update phone-card tests (step 0)
- 7989e32 0741 step 1: phone v2 property page CSS
- final commit: see git log (steps 4 and 5 test edits, report)

## Command tails
- step 0 (3 files): 20 passed in 21.10s
- step 5 property mockup: 12 passed in 17.97s
- step 5 bundle (7 files): 43 passed, 2 failed before the manifest rewrite; the 2 failures were stale static_versions manifest (app2.css edited after --write), fixed by rewrite
- design_lint: OK; context_lint: OK; `git grep -n "props-top" App`: empty

## Overrides added (BOX_OVERRIDES, v2_mockup.py)
- text-dependent: .guest-pin-value@320/390 width 95.3125px (demo PIN); .guest-card .sub@320/390 height 46px and .guest-card@320/390 height 299.8px (permalink wraps to two lines)
- .big, .head h1@320/390 margins 8px (phone title); removed stale 0740 width overrides 150.547px (title now 264px at 320)

## Deviations
- missing_ok `.prop-phone-sub`: the demo property has no street address, so the address line is not rendered.
- catalog.json not changed: no new classes were added.
- Step 5 commands run with -rs; no skips.
- Screenshots skipped (orchestrator takes them).
- test_0250_property_cards.py was not run (not in the named commands).

## Questions
- None.

## Owner steps left
- Push branch and open PR after review.
