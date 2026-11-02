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

### 0507 Part B, continued session (steps 2 to 6)
Status: review (committed on task/0506-page-swap, not pushed).

Commit: `9f0d3bf 0507 step 2-5`.

- `havel.js`: `panel`, `page`, `root` are shared variables. `refresh()` (registered with `onPage`, direct call without app.js) looks them up, binds `submit`/`click` on `root` once per element (`claimOnce`), binds `close` and the MutationObserver on `panel` once, sets `window.UbyHavel`, and restores the chat, device and counter once per element. Document `click`/`submit` are bound once (claim on document) and return early when `root` is null.
- `dashboard-calendar.js`: the window `resize`/`popstate` listeners are bound once (`window._ubyCalendarBound`). Each run sets `window._ubyCalendarHandlers`; the listeners call it, and each handler returns if `[data-calendar]` is missing.
- `shell.js`, `skeleton.js`, `csrf.js`: checked, no change. shell and skeleton look elements up at event time. csrf keeps the token string read from the meta at load; it is not an element, so the rule did not apply.
- Version keys: `havel.js?v=20261102-0507` in base.html, `dashboard-calendar.js?v=20261102-0507` in _dashboard_calendar.html, `static_versions.json` rewritten (41 files).
- Test `App/tests/test_0507_page_hooks_browser.py` (3 tests).

Test tails (from App/, PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers, timeout 900):
- Batch 1 (0507, 0506, 0505, 0504, 0503, static versions): `14 passed in 14.82s`, no skips.
- Batch 2 (`grep -lE 'havel|data-push|passkey|cleaning|signature' tests/*_browser.py | head -12`, 12 files, one call, -x): `84 passed in 352.88s (0:05:52)`, no skips.

Deviations:
- Calendar: the spec says to only guard and look up `[data-calendar]`. Done, but the body needs the current page's closure (state, load, render). A direct guard would keep the first page's closure, so after a Turbo visit the popstate and resize would act on the old calendar. The handlers therefore go through `window._ubyCalendarHandlers`, set by each run.
- Test: `grep ... | head -12` returned exactly 12 files, so more matching files may exist beyond the cap.
- Test: the dashboard calendar needs `cal_view=calendar` (dashboard.html includes it only then). The push row check proves the claim (`_ubyBound`), not a click.
- Not run: a 390 px screenshot (no template or CSS changed in Part B).

Questions: none.

Owner steps left: none. Part C is next; no push or PR was made.
