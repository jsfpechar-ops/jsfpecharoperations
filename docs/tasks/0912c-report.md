# 0912c report

Status: review

## 1. Files changed (uncommitted, this run and the earlier run on disk)
- App/app/static/host2.css line 1193: `.host-workspace .page-help[open] > .page-help-body` width `min(20rem, calc(100vw - 2rem))` -> `min(360px, calc(100vw - 32px))`. Also max-height `calc(100vh - 2rem)` -> `calc(100vh - 32px)` (same value; deviation, see 6).
- App/app/static/app.js `place()`: floorY from first visible fixed element of `nav.tabs, .ui-tabbar` (its top minus 16), else `innerHeight - 16`.
- App/app/templates/base.html: host2.css `?v=20261104-0911` -> `20261104-0912d`; app.js `?v=20261104-0912d` -> `20261104-0912e`.
- App/tests/static_versions.json: regenerated (48 files).
- Earlier run, still on disk: app2.css line 1219 `left:-4px` (fix 1); line 2040 `min(360px` (fix 2). Both grep-verified (count 1).
- No commit, no push, no branch. Test file not edited.

## 2. Commands
1. `.venv/bin/python tests/test_static_versions.py --write`: wrote 48 files.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_static_versions.py tests/test_stay_fee*.py -q --tb=short -rs`: 214 passed, 1 failed, 0 skipped (284 s). Failing: `test_opened_help_stays_inside_the_viewport`, three entries at 390 only: setup-property, setup-police, setup-guest-link, trigger 9: "last link cut off or covered after scroll", body 636.3 to 677.2, left 16, right 374, `hit: false`. The 320 entries and the payments dialog entries now pass.
3. Temporary diagnostic (file created and deleted): at 390 on setup-property, trigger 9 open, the tooltip body was fixed, z 70, at top 386 to 427 in that run. The trigger button (388 to 432) was the element at its centre. The fixed `a.havel-fab` (x 325 to 376, y 651 to 702, z 40) is a second fixed bottom element that `place()` does not see. This run did not reproduce the 636 position from command 2, so the cause is not confirmed.
4. `python3 scripts/design_lint.py`: OK. `python3 scripts/context_lint.py` (WARN filtered): OK.

## 3. Acceptance (section 7)
- Browser test: NOT green (1 failed).
- Test file unchanged: yes.
- Gutters: not re-measured this run. Page-help dialogs and stays-how box pass the test at 320 and 390.
- host2.css dialog width: done. `place()` tab-bar floor: done. Versions and manifest: done.
- Screenshots: not taken (step 7 not reached).

## 4. Not done
Screenshots (step 7). Brief Status and 0912b Status left as they were (not set to review).

## 5. Questions for the orchestrator
1. Tooltips at 390 on setup pages: decide whether `place()` must also re-place on scroll and resize, and whether `a.havel-fab` (fixed bottom) joins the floor. Not decided by the brief; test not relaxed.

## 6. Deviations
- app.js `?v=` went to 0912e, not 0912d: the manifest tool refused a second write under the same key after the content changed.
- host2.css max-height changed too (same value in px).

## 7. Owner steps left
None.
