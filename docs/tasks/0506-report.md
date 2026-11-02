# 0506 report: last app.js start-up functions bind once (Part A)
Status: blocked (Part A done except the 390 px drawer check, see Questions)

## Test tails
- `test_0506_last_inits_once_browser.py`: `2 passed in 4.04s`
- `test_0501`..`test_0505`, `test_design_shell_browser.py`, `test_0705_v2_shell_browser.py`: `26 passed in 43.87s` (0 skipped)

## Files changed
- `App/app/static/app.js`: claims in initFilterPanels, initDateRanges, initMonthPickers, initNavigation, initPowerTools; one claimed document pointerdown/keydown pair per date-range and month-picker function (closes via `el._ubyClose`); `navState` holds railWasCollapsed, animateTimer and the tablet media query.
- `App/tests/test_0506_last_inits_once_browser.py` (new).

## Deviations
- Commits: `0506 step 1` (app.js, covers steps 1 to 3) and `0506 step 4` (test).
- Test page: the brief's `/dashboard?lang=cs` returns "Stránka nenalezena". The dashboard route is `/` (`App/app/routes/admin.py`), so the test uses `/?lang=cs`.
- initPowerTools: the one document keydown handler delegates to `powerToolsKeydown`, which is set by the latest initPowerTools call. Its element lookups happen in that call, not at event time, because render, updateSelection and runItem share the dialog variables. Element listeners are claimed per element.
- Filter/date/month init bodies run for a second time, but per-element setup is claimed, so a second run adds no listeners.

## Questions (stopped)
- The 390 px drawer check cannot be written as briefed: no template renders `[data-nav-toggle]` (grep of App/app/templates is empty). Only the sidebar collapse button `[data-sidebar-collapse]` exists. Owner or orchestrator: which opener should the test use, or should the drawer toggle be added to the shell? Until then the Escape-closes-drawer path is untested.

## Owner steps left
- None for Part A.
