# 0147 report

Status: blocked

## Files changed and commits

- `App/app/static/dashboard-calendar.js` (step 1, 7 anchors): commit `3af2f8c` (`0147 step 1`). `node --check` clean.
- `App/app/static/dashboard-calendar.css` and `App/app/templates/_dashboard_calendar.html` (step 2): commit `edf4bd1` (`0147 step 2`). `design_lint.py`: OK.
- `App/tests/test_dashboard_calendar_browser.py` (step 3, six edits): commit `7f2173d` (`0147 step 3`). py_compile clean.
- `App/tests/test_dashboard_phone_browser.py` (step 4, new): commit `ddd4ff6` (`0147 step 4`).

## Step 5 (browser run): FAILED

Command: `.venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_host_quiet_dashboard_browser.py -q --tb=line -rfs`

Last lines (run 2):

```
FAILED tests/test_dashboard_phone_browser.py::test_phone_dashboard_compact - ...
FAILED tests/test_dashboard_calendar_browser.py::test_calendar_geometry_locales_and_screenshots
FAILED tests/test_dashboard_calendar_browser.py::test_create_popover_reclamps_when_switching_to_taller_stay_form[360]
3 failed, 11 passed, 1 warning in 86.26s (0:01:26)
```

Failing assertions (verbatim):

- `test_dashboard_phone_browser.py:41: AssertionError: assert False` (`[data-cal-day-dialog]` is_visible after a tap on `[data-cal-day="2026-10-15"]` at 390)
- `test_dashboard_calendar_browser.py:355: AssertionError: assert False` (same check, in the geometry test)
- `test_create_popover_reclamps...[360]`: `Locator.click: Timeout 30000ms exceeded` on `[data-cal-day-add]` (element is not visible), because the day dialog never opened.

## Cause (read, not guessed)

A tap on a day at 390 opens the create popover, not the day dialog. `root.addEventListener("pointerup")` (`dashboard-calendar.js` ~line 690) calls `openCreate(...)` for any pointer selection, and sets `suppressClickUntil`, so the click handler that now calls `openDay` returns early. Probe (temporary test, deleted, not committed): after the tap, `[data-cal-day-dialog]` `open` = false, no page errors, `aria-busy` = false.

This is the brief §8 stop condition ("a tap on a day at 390 still opens the create popover").

## Screenshots

Not taken as evidence. The phone test fails before its `shot()` call. Nothing in `docs/tasks/0147-evidence/` yet. Step 6 not done.

## Deviations

- A first Bash attempt hung on a stray `cat` with no file argument, before any edit. Nothing was written from it.
- Steps 1 to 4 applied exactly as the brief gives them.
- Step 5 test failures above are not in the known-local-failures list.

## Done and left

Done: steps 1 to 4 (committed), step 5 run (failed).
Left: step 5 pass with 0 skipped; step 6 (screenshots, ruff, evidence); report Status: review.

## Questions for the orchestrator

1. Fix the pointer path: in `pointerup`, skip `openCreate` when `phoneDots()` so the click handler opens the day dialog. This is outside the brief's anchors A to G, so it needs an owner or orchestrator decision.
2. Expected count: the brief's `[data-cal-day-list] .cal-event` count of 4 for 2026-10-15 is not yet verified (the assertion was never reached).

## Owner steps left

None yet. After the fix, the owner reviews the screenshots in step 6.
