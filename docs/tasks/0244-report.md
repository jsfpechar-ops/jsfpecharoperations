# 0244 report

Status: blocked

## Files changed (committed)

- App/app/property_health.py (new, step 1)
- App/app/routes/admin.py (step 2: import and `health` context key)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (step 3: EN, CS, VI strings)
- App/app/templates/_property_overview.html (step 4: the box; old tile grid removed)
- App/app/static/workflow.css, App/app/templates/base.html, App/tests/static_versions.json (step 5)
- docs/design/catalog.json (step 6)

## Commits

- 628aca8 0244 step 1
- 26e881b 0244 step 2
- dfec93e 0244 step 3
- 4673e3c 0244 step 4
- 9daee16 0244 step 5
- 86c53cc 0244 step 6

Step 7 (App/tests/test_property_health_0244.py) is created but NOT committed: it is red.

## Commands (last lines)

- Step 1 import check: no output (import OK).
- Step 2 import check: no output (import OK).
- Step 3 `tests/test_alert_stack.py tests/test_host_i18n.py`: `27 passed, 2 warnings in 2.34s`
- Step 4 grep count: `0`
- Step 5 `tests/test_alert_stack.py tests/test_static_versions.py`: `16 passed, 1 warning in 2.31s`
- Step 6 `tests/test_alert_stack.py tests/test_design_lint.py`: `16 passed, 1 warning in 2.10s`
- Step 7 `tests/test_alert_stack.py tests/test_property_health_0244.py`:
  `1 failed, 17 passed, 1 warning in 2.46s`
  Failing: `test_the_overview_shows_the_health_check`, assertion `'Health check' in page` (lang en).

## Deviations

Done: steps 1 to 6. Left: steps 7 and 8, and command 1 of §6 (includes the step 7 test), command 2 (browser), command 3 (context lint).

Diagnosis of the step 7 failure (a temporary diagnostic test, deleted, not committed): after `property_setup.finish(apartment_id)` the overview page renders `setup-continue-card` (the wizard card) and does NOT render `data-setup-status` or `data-health-check`. The box is only shown when the wizard card is not active (`_property_overview.html`, the `setup_progress and not setup_progress.hidden` condition). This is the case the brief's step 7 says to report and stop on. No fix attempted.

## Questions

1. Does `property_setup.finish()` need to hide the wizard card (`setup_progress.hidden`) for this test, or should the test use a property where the wizard is already hidden? I did not guess; the brief does not say how `setup_progress.hidden` becomes true.
2. Brief §9 asks for `Status: review`; this report says `blocked` because §8 stopped the run.

## Owner steps left

None yet. Steps 7 and 8, the browser test and the lint still need to run once the question above is answered.
