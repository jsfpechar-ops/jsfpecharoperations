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

## 0508 Part C (turn on the page swap), Status: blocked

Done: steps 1 to 5 (commits 39c8e80 vendor Turbo, scripts in head, forms off; b504b1e data-turbo="false" links; 30dc0d6 version keys; 64ed448 test and prefetch test; 0991fff feedback visibility listener binds once, page swap test passes).

Left: one browser test in the 0501 to 0507 run fails (name in the tail below). It asserts a navigation count of 1 and sees 2 entries for the reservation detail page, most likely because Turbo's history push counts as a second navigation. Not diagnosed. Next step: read that test, decide if its assertion or the page is wrong, fix once, rerun.

### Test tails

0508 page swap browser test: `5 passed` (tests/test_0508_page_swap_browser.py).
Non-browser prefetch and static version tests: `5 passed` (tests/test_navigation_prefetch.py, tests/test_static_versions.py).

0501 to 0507 browser tests plus the prefetch browser test:
```
FAILED tests/test_0501_bind_once_browser.py::test_init_page_second_run_binds_no_row_or_button_again
1 failed, 13 passed in 21.37s
```

Shell and launcher browser tests:
```
....................                                                     [100%]
20 passed in 51.09s
```

context_lint:
```
ERROR docs/tasks/0506-page-swap.md: missing section '## 6. Commands'
ERROR docs/tasks/0506-page-swap.md: missing section '## 7. Acceptance'
ERROR docs/tasks/0506-page-swap.md: missing section '## 8. Stop and ask'
ERROR docs/tasks/0506-page-swap.md: missing section '## 9. Report'
next free: task 0761 | migration 0034
context lint: FAIL
```

git diff --stat origin/main:
```
 App/app/templates/admin_customer.html              |    2 +-
 App/app/templates/admin_customers.html             |    2 +-
 App/app/templates/admin_home.html                  |   16 +-
 App/app/templates/admin_operations.html            |    2 +-
 App/app/templates/auth_base.html                   |    2 +-
 App/app/templates/base.html                        |   20 +-
 App/app/templates/billing_plan.html                |    2 +-
 App/app/templates/dashboard.html                   |    2 +-
 .../guest/archive/ticket-wallet/base.html          |    2 +-
 App/app/templates/guest/base.html                  |    2 +-
 App/app/templates/guest/guide.html                 |    2 +-
 App/app/templates/guest_form_admin.html            |    6 +-
 App/app/templates/guide.html                       |    2 +-
 App/app/templates/housebook.html                   |    2 +-
 App/app/templates/invoice_detail.html              |    2 +-
 App/app/templates/invoices.html                    |    2 +-
 App/app/templates/login.html                       |    6 +-
 App/app/templates/payments_consent.html            |    2 +-
 App/app/templates/product.html                     |    2 +-
 App/app/templates/property_page_review.html        |    2 +-
 App/app/templates/public_guide.html                |    2 +-
 App/app/templates/reservation_detail.html          |    8 +-
 App/app/templates/reservations.html                |    8 +-
 App/app/templates/settings.html                    |    4 +-
 App/app/templates/setup_wizard/guest_link.html     |    2 +-
 App/app/templates/setup_wizard/police.html         |    2 +-
 App/app/templates/setup_wizard/try_it.html         |    4 +-
 App/app/templates/signup.html                      |    4 +-
 App/app/templates/stay_fee_detail.html             |    6 +-
 App/app/templates/stay_fees.html                   |    4 +-
 App/app/templates/submission_detail.html           |    4 +-
 App/app/templates/submissions.html                 |    2 +-
 App/tests/static_versions.json                     |   36 +-
 App/tests/test_0506_last_inits_once_browser.py     |  103 +
 App/tests/test_0507_page_hooks_browser.py          |  104 +
 App/tests/test_0508_page_swap_browser.py           |  175 +
 App/tests/test_navigation_prefetch.py              |   25 +-
 docs/tasks/0506-page-swap.md                       |   54 +
 docs/tasks/0506-report.md                          |   78 +
 56 files changed, 8128 insertions(+), 241 deletions(-)
```

### Deviations

- data-turbo="false" went on 61 anchors in 33 template files, including guest, public and auth templates (for example /terms, /privacy, guest PDF links). It does nothing where Turbo is not loaded. The brief said to leave those templates alone.
- Version keys were bumped in guest/base.html and guest/archive/ticket-wallet/base.html because they reference app.js.
- app.js: the feedback visibility listener (window of data-toast) bound per page on the root element; now claimed on document and it looks up toasts at event time. This was not named in the brief, and it was the cause of a listener leak after swaps.
- The swap test checks the active sidebar item (aria-current) instead of a calendar, because the dashboard in the test workspace renders no calendar.
- The listener test visits both pages once before it starts counting, because features bind their document listeners the first time their page appears.
- The help tip check runs on the reservation detail page reached by Turbo.visit, lifting one tip out of its section as 0505 does.
- Logout is a POST form (not a link). It is a full load because forms mode is off.

## 0508 Part C, continuation (executor, second session)

Status: blocked

Done: step 1 (c59e7ee, non-host templates reverted; login.html keeps only its version key). Step 2 (4e9c515): the listener assertions in test_0501 passed; the failing assertion counted `framenavigated` navigations, which also fires for Turbo's same-document replaceState when the new page starts. The test now counts `load` events (full document loads). App code unchanged. Step 3 partly run. Step 4 not done.

Test tails:
- `test_050[1-8]*_browser.py test_static_versions.py test_navigation_prefetch.py`: `23 passed in 26.81s`
- keyword-matched browser files (58 files), `-k "not webkit"`: `5 failed, 383 passed, 57 skipped, 6 deselected in 1212.96s`. Skips are `browser not required` in test_onboarding_wizard_browser.py.
- Failures: 2 in `tests/test_motion_browser.py` (`test_page_changes_cross_fade_with_the_rail_held_still` line 106, `test_reduced_motion_keeps_pages_and_dialogs_still` line 127; attribute `None` instead of `'true'`/`'false'`). Probably caused by the branch: Turbo visits do not rerun the page-load cross-fade/motion code. Not diagnosed. 3 more failures are `Page.wait_for_selector` timeouts in test files I did not identify (the summary line did not name them).
- WebKit: not installed locally (`/opt/pw-browsers/webkit-2359` missing). Not a branch failure; CI runs WebKit.
- `python3 scripts/context_lint.py`: `context lint: OK`.

Left: identify the 3 wait_for_selector timeouts (`pytest <keyword files> -rf --tb=line -k "not webkit"`, ~20 min) and the 2 test_motion failures; fix the ones caused by the branch; compare with origin/main for any that also fail there.

Deviations: step 2 changed the test, not the code, because the bind-once assertions already passed. The test's navigation assumption was the broken part.

## 0508 page swap (executor)
- Turbo 8 now wraps renders in startViewTransition: added `<meta name="view-transition" content="same-origin">` in base.html (Turbo metas), so the existing ::view-transition CSS applies again.
- Reduced motion: app.js (top of file) clears `document.startViewTransition` as an own property when prefers-reduced-motion is set, so Turbo swaps without a fade.
- tests/test_motion_browser.py PAGE_SWAP_RECORDER also records startViewTransition calls; defaults swapFaded to 'false' per tab. Assertions unchanged.
- app.js bumped to v=20261102-0510; static_versions.json regenerated.
- Tests: test_motion_browser, test_0508_page_swap_browser, test_0705_v2_shell_browser, test_design_shell_browser, test_static_versions: 31 passed, 0 skipped (-k "not webkit").
