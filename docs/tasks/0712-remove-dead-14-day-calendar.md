# 0712: remove the unused 14-day mode of the old JS calendar
Status: todo
Depends on: 0710 | Base commit: task/0710-v2-match-tests | Branch: task/0712-dead-14-days
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Delete the 14-day mode added to the old JS calendar by brief 0521. The v2 Overview now draws its own server-side 14-day grid, and the old calendar is only included with `?cal_view=calendar`, where the 14-day mode never turns on. Owner rule: no dead code.

## 2. Context
- `App/app/static/dashboard-calendar.js`: everything using `fixedDays`, `state.fixed`, and `[data-cal-days]` (lines near 78, 110-111, 128, 134-136, 191, 204-208, 425, 433, 791). Restore those lines to their `origin/main` form: `git fetch origin main && git diff origin/main -- App/app/static/dashboard-calendar.js` shows exactly the 0521 additions; remove all of them (the file should then equal `origin/main`; check with `git diff origin/main -- <file>` being empty).
- `App/app/templates/_dashboard_calendar.html`: drop the `data-days` attribute and the `data-cal-days` button (same check against origin/main).
- Keys `calendar.days14` in `App/app/host_i18n.py` (en, cs) and `App/app/host_vi_i18n.py`: delete if `grep -rn "days14" App/app/templates App/app/static App/app/*.py` finds nothing else.
- Delete `App/tests/test_0521_overview_14_days_browser.py`. Grep `App/tests` for `data-cal-days`, `days14`, `is-fixed-days` and fix or remove only the assertions about the 14-day mode.
- Any i18n parity test must still pass.

## 3. Files
The four app files above, the deleted test, any test that referenced the removed parts, report `docs/tasks/0712-report.md`. Do NOT edit `base.html` or `tests/static_versions.json` (the orchestrator bumps the JS version key after merging with brief 0711).

## 4. Steps
1. JS and template back to origin/main. Commit `0712 step 1: drop the unused 14-day calendar mode`.
2. Keys and tests. Commit.
3. Run the commands. Commit the report.

## 5. Do not touch
`App/app/static/app2.css`, `dashboard.html`, `v2_mockup.py`, anything brief 0711 lists.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar.py tests/test_dashboard_calendar_browser.py tests/test_i18n_parity.py -q --tb=line -rs 2>&1 | tail -30` (if a listed file does not exist, find the calendar and i18n-parity tests with `ls tests | grep -i "calendar\|parity"` and run those). Expect `tests/test_static_versions.py` to fail on the JS hash; that is fine and is fixed after merge. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -2`.

## 7. Acceptance
`git diff origin/main -- App/app/static/dashboard-calendar.js App/app/templates/_dashboard_calendar.html` is empty. Listed tests pass, 0 skipped.

## 8. Stop and ask
Stop if restoring the JS to origin/main would remove anything not added by 0521 (compare `git log --oneline origin/main..HEAD -- App/app/static/dashboard-calendar.js`).

## 9. Report
`docs/tasks/0712-report.md`: status, test tails, deleted assertions, deviations.
