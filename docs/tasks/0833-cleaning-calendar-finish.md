# 0833: Finish the cleaning calendar (0815 left red) and the refresh test

Status: todo
Depends on: 0815 + 0832 (WIP committed on the branch) | Branch: claude/project-thread-6aeyrs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

0815 (cleaning page = Airbnb calendar, cleaning tags only) and 0832 (full-page calendar, clean toolbar) are committed but not green. Read `docs/tasks/0815-report.md`, `docs/tasks/0832-report.md`, `docs/tasks/0815-cleaning-calendar-airbnb.md`. Finish them.

## 2. Context

1. Phone host `/cleaning`: `section.dashboard-calendar` is `display:none` (cards only, also at HEAD before 0815). Find the hide rule (`grep -n "dashboard-calendar" App/app/static/cleaning.css App/app/static/app2.css App/app/static/*.css`, also `ph-hide`/`ph-only` in `cleaning.html` / `_cleaning_screen.html`), show the calendar on phone for the host page (not read-only), keep `.cleaning-legend`/list hidden there. The shared read-only page is unchanged.
2. 15 tests in `App/tests/test_cleaning_browser.py` fail because they expect bars, labels or the visible table on the host page. Rewrite each for the tag UI (tiles with `.cal-cleaning-tag`, side panel/sheet lists the cleaning, Add cleaning). Read-only page tests pass unchanged. Do not delete a test; if a flow is obsolete, replace it with the tag equivalent and say so in the report.
3. `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place` fails at the /cleaning step (line ~492-507, expects a bar in week view): update to the tag in month view.
4. Phone long-press range test at 390 (CDP touch as in 0814's test) on `/cleaning`.
5. 0815's CSS edit changed `[data-cleaning="false"]` selectors to `[data-readonly="false"]` and edited the 0832 block; check the host dashboard calendar and the phone dashboard still look the same (their tests are the check).
6. Year view on the host cleaning page still counts bookings: show cleanings only there too.
7. Screenshots: run with `UBYHOST_TASK_SHOTS=1`, add `cleaning-390.png`, `cleaning-range-390.png`, `cleaning-768.png`, `cleaning-1280.png`, `cleaning-range-1280.png` to `docs/tasks/screenshots-0814/`.

## 3. Files

`App/app/static/dashboard-calendar.js`, `dashboard-calendar.css` (append `/* 0833 */`), `cleaning.css`, `App/app/templates/cleaning.html` / `_cleaning_screen.html` (hook only), `App/tests/test_cleaning_browser.py`, `App/tests/test_dashboard_calendar_browser.py`, `docs/tasks/screenshots-0814/`, `docs/tasks/0833-report.md`. Do not bump `?v=` or touch `static_versions.json`. Never stage or commit; never touch `docs/tasks/screenshots-0387/`.

## 4. Commands

From `App/` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1`: `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py -q --tb=short 2>&1 | tail -30` (600 s timeout; split by file if it times out).

## 5. Acceptance

All pass, 0 skipped. Five cleaning screenshots exist. Only section 3 files changed.

## 6. Stop and ask

Phone hide rule not found in 8 tool calls; a test fails twice; 30 tool calls (hand back the list of what is left).

## 7. Report

`docs/tasks/0833-report.md`: files, last test lines, rewritten tests, deviations.
