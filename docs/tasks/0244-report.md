# 0244 report

Status: review

## Files changed (committed)

- App/app/property_health.py (new, step 1)
- App/app/routes/admin.py (step 2: import and `health` context key)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (step 3: EN, CS, VI strings)
- App/app/templates/_property_overview.html (step 4: the box; old tile grid removed)
- App/app/static/workflow.css, App/app/templates/base.html, App/tests/static_versions.json (step 5)
- docs/design/catalog.json (step 6)

## Commits (step 7 and 8 added after the coordinator answer)

- 628aca8 0244 step 1
- 26e881b 0244 step 2
- dfec93e 0244 step 3
- 4673e3c 0244 step 4
- 9daee16 0244 step 5
- 86c53cc 0244 step 6

Step 7 (App/tests/test_property_health_0244.py) committed after the fix below.

## Commands (last lines)

- Step 1 import check: no output (import OK).
- Step 2 import check: no output (import OK).
- Step 3 `tests/test_alert_stack.py tests/test_host_i18n.py`: `27 passed, 2 warnings in 2.34s`
- Step 4 grep count: `0`
- Step 5 `tests/test_alert_stack.py tests/test_static_versions.py`: `16 passed, 1 warning in 2.31s`
- Step 6 `tests/test_alert_stack.py tests/test_design_lint.py`: `16 passed, 1 warning in 2.10s`
- Step 7 `tests/test_alert_stack.py tests/test_property_health_0244.py`:
  `1 failed, 17 passed` before the fix; after the fix `18 passed, 1 warning in 2.34s`.
- Step 8 §6 command 1 (`test_alert_stack`, `test_property_health_0244`, `test_host_i18n`, `test_static_versions`, `test_design_lint`, `test_property_form_nav`, `test_guest_links_bilingual`): `53 passed, 2 warnings in 4.01s`
- Step 8 §6 command 2 (browser, `PLAYWRIGHT_BROWSERS_PATH` and `UBYHOST_REQUIRE_BROWSER=1`, `-rs`): `109 passed, 1 warning in 291.98s (0:04:51)`, no skips.
- §6 command 3 `python3 scripts/context_lint.py`: `context lint: OK`

## Deviations

- Step 7 test change (coordinator answer): in `test_the_overview_shows_the_health_check`, the line `property_setup.finish(apartment_id)` was replaced with `property_setup.set_hidden(apartment_id, False)  # stores a setup state so finish() can mark it` followed by `property_setup.finish(apartment_id)`. Reason: `finish()` does nothing for a new property because no setup state is stored yet (`load()` returns None). No other change to the brief's test.
- Step 8: `test_onboarding_followup_browser.py` edited as the brief says (replaced the tile assertions, renamed the screenshot to `40-overview-health-{lang}-{width}.png`).

Diagnosis of the step 7 failure (a temporary diagnostic test, deleted, not committed): after `property_setup.finish(apartment_id)` the overview page renders `setup-continue-card` (the wizard card) and does NOT render `data-setup-status` or `data-health-check`. The box is only shown when the wizard card is not active (`_property_overview.html`, the `setup_progress and not setup_progress.hidden` condition). This is the case the brief's step 7 says to report and stop on. No fix attempted.

## Questions

1. Resolved by the coordinator answer (see Deviations).

## Owner steps left

None. Not pushed, no PR opened. Untracked docs/tasks/0102-evidence/* and docs/tasks/0246-needs-you-review-fixes.md were not committed.
