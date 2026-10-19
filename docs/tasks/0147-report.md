# 0147 report (via 0147-cont-1)

Status: blocked

## Done
- 0147-cont-1 step 1: `phoneDots()` single-day early return in the pointerup handler, cache string bumped to `20261019-0147b`. `node --check` passed. Commit `284773b` (`0147-cont-1 step 1`).

## Left
- Step 2 (browser tests): 3 failed, 11 passed, 0 skipped.
- Step 3 (screenshots, evidence, report): not done.

## Failing assertions (verbatim, from `App/` run of the step 2 command)
- `tests/test_dashboard_phone_browser.py::test_phone_dashboard_compact` (line 41):
  `assert page.locator("[data-cal-day-dialog]").is_visible()` -> `AssertionError: assert False`, after `page.locator('[data-cal-day="2026-10-15"]').click()` at 390 px.
- `tests/test_dashboard_calendar_browser.py::test_calendar_geometry_locales_and_screenshots` (line 355):
  `assert page.locator("[data-cal-day-dialog]").is_visible()` -> `AssertionError: assert False`.
- `tests/test_dashboard_calendar_browser.py::test_create_popover_reclamps_when_switching_to_taller_stay_form[360]`:
  `Locator.click: Timeout 30000ms exceeded` on `[data-cal-day-add]` ("Add stay" resolved, "element is not visible").

## Notes
- The three failures share one symptom: a single click on `[data-cal-day="2026-10-15"]` at phone width does not make the day dialog visible.
- The click handler (`root.addEventListener("click", ...)`, line ~738) routes phone taps to `openDay()`. It is skipped if `Date.now() < suppressClickUntil`, `state.loading` or `!lastLoadedRange`. Not yet diagnosed which guard blocks it; the brief's rule is to stop after a second failure.
- The step 2 count of 4 on 2026-10-15 was not reached, so it is unverified.
- Not checked: whether these failures predate commit `284773b`.
