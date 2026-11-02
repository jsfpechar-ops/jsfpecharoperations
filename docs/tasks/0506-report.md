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

## 0507 Part B (partial, Status: blocked)
Status: blocked at the executor cap. Done: steps 1, 2 (host.js, pwa.js, passkeys.js), 3 (cleaning.js) and the version keys. Left: steps 2 (havel.js), 3 (dashboard-calendar.js), 4, 5 and 6.

### Done
- `app.js`: `pageHooks`, `window.UbyHost.onPage`, and `initPage` sets `pageStarted` and runs the hooks. Commit `0507 step 1`. `node --check` passes.
- `host.js`: local `claimOnce` (same `_ubyBound` store as `claimNode`) and `onPage` (falls back to a direct call without app.js). Signature, account parts, wsUser/ubyMark, phone country code, adjust mode, door-code windows and the alerts observer run through `onPage` with claims. The wizard demo and wait listeners are claimed once and read their state at event time. Commit `0507 step 2`.
- `pwa.js`: `pushRowEl()` looks the row up at event time; the csrf meta is read in `post()`; `paintInstall` and the push init run through `onPage`. Commit `0507 step 2b`.
- `passkeys.js`: the same helpers; the add and login buttons are claimed; `DOMContentLoaded` replaced by `onPage(init)`. Commit `0507 step 2b`.
- `cleaning.js`: `saving` moved onto `root.saving`; `refresh` looks up the current calendar and list at event time; the interval and document/window listeners are guarded by `window._ubyCleaningBound`. Commit `0507 step 3`.
- Version keys bumped to `20261102-0507` in base.html, login.html, auth_base.html and _cleaning_screen.html. `test_static_versions.py --write` wrote 41 files.

### Not done, and why
- `havel.js` (step 2): `panel`, `page` and `root` are captured once at load and used in about 60 places, including document handlers and `root.addEventListener`. Making it page-swap safe needs a restructure (refresh the roots in one `onPage` function, guard the document listeners with claims, and return early when no root). Not attempted: no safe small edit fits the executor rules.
- `dashboard-calendar.js` (step 3): 899 lines, not reviewed. Its document/window listeners need the same guard.
- Step 4 (`shell.js`, `skeleton.js`, `csrf.js` check): not done.
- Step 5: `App/tests/test_0507_page_hooks_browser.py` not written.
- Step 6: the browser run started (50 files) was terminated (exit 143) before it printed anything. No test result exists for Part B, and the Part A and app.js changes have not been re-tested since step 1.

### Test tails
- None for Part B. The run was killed (`[exited with code 143]`) before pytest printed.

### Deviations
- `test_static_versions.py --write` refused until the keys were bumped. I bumped them by hand, then ran `--write`.
- The test run regenerated `docs/tasks/screenshots-guide/*.png`. They were restored with git checkout and not committed.

### Questions
- Havel: keep root as one shared variable refreshed by `onPage`, or split the document handlers into their own claimed function? Either works; the owner or orchestrator should choose.

### Owner steps left
- None.
