# 0521: Overview redesign, part 2: the Overview calendar shows 14 days
Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0521-overview-14-days
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
On a computer, the Overview page (`/`) calendar is a 14-day timeline starting today, one row per property, as in the approved mockup (`ubyhost-redesign-v2.html`, view "today", owner approved 2026-11-01). Previous and next move 14 days. The view switch (calendar/timeline) and the month/week/year switch are hidden there. Every other page with this calendar (cleaning, property pages) and the phone layout stay exactly as they are.

## 2. Context
- Markup `App/app/templates/_dashboard_calendar.html` (root `<section id="calendar" ... data-calendar ...>` on line 3). Script `App/app/static/dashboard-calendar.js`, linked at the bottom of that template with `?v=`.
- In the script: `view()` (line ~221 area, `function view()`), `range()` (right after it), `syncControls()` (`function syncControls`), the prev/next click handler (`grep -n 'data-cal-prev\], \[data-cal-next' `). `phoneDots()` makes phones use the dot calendar; keep that winning on phones.
- The cleaning page already has a fixed-length timeline: `cleaningMode && view() === "gantt"` uses `[state.date, addDays(state.date, 30)]` and prints the period as `shortDate(start) + " – " + fullDate(addDays(end, -1))`. Copy that pattern.

## 3. Files
Edit `App/app/templates/_dashboard_calendar.html`, `App/app/static/dashboard-calendar.js`, `App/tests/static_versions.json` (only via `--write`). Create `App/tests/test_0521_overview_14_days_browser.py`. Screenshots in `docs/tasks/screenshots-0521/`. Report `docs/tasks/0521-report.md`.

## 4. Steps
1. Template: on the root section add `data-days="{{ '14' if nav == 'dashboard' else '' }}"`. Bump the script `?v=` to `20261101-0521`. Commit `0521 step 1`.
2. Script, near the top where `cleaningMode` is read: `const fixedDays = Number(root.dataset.days) || 0;`. Then:
   - `view()`: if `fixedDays` and not `phoneDots()`, return `"gantt"`.
   - `range()`: first line, if `fixedDays && view() === "gantt"` return `[state.date, addDays(state.date, fixedDays)]`.
   - Start date: when `fixedDays` and no `cal_date` in the URL, `state.date` starts at `root.dataset.today` (check what it starts at now; change only for `fixedDays`).
   - `syncControls()`: when `fixedDays && view() === "gantt"`, period text is `shortDate(start) + " – " + fullDate(addDays(end, -1))`, and hide the view segment (`.cal-view-segment`), the scales group, and the month and year selects. Keep prev, next, today, and the settings button.
   - Prev/next handler: when `fixedDays && view() === "gantt"`, move `state.date` by `sign * fixedDays` days with `addDays`, keep the existing clamping.
   - Do not save `mode` to localStorage because of `fixedDays` (the forced view must not leak into other pages).
   `node --check App/app/static/dashboard-calendar.js 2>&1 | tail -3`. Commit `0521 step 2`.
3. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0521 step 3`.
4. Test `test_0521_overview_14_days_browser.py` (copy server start, login and fixtures from `tests/test_dashboard_calendar_browser.py`), at 1280 px: on `/` the timeline shows exactly 14 day columns starting today, the view switch is hidden, next moves the first day by 14 days and today returns; at 1280 px on the cleaning calendar page the timeline length is unchanged (30 days); at 390 px `/` still shows the dot calendar. Commit `0521 step 4`.
5. Screenshots of `/?lang=cs` at 1280 px and 390 px into `docs/tasks/screenshots-0521/` (see executor.md, Screenshots). Commit `0521 step 5`.

## 5. Do not touch
The script's start-up (the IIFE wrapper, `DOMContentLoaded`, how it finds `root`), event colours and bar styles, the create and detail dialogs, `dashboard.html`, any CSS file, app.js, other JS files, routes, copy, translations. No new dependency.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0521_overview_14_days_browser.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_calendar.py tests/test_dashboard_phone_browser.py tests/test_static_versions.py -q --tb=short -x -rs 2>&1 | tail -30`, plus every `tests/test_calendar_*browser*.py` and `tests/test_cleaning*browser*.py` that exists. Then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files, plus test files changed under section 8.

## 8. Stop and ask
If an existing test asserts the old month timeline or the view switch on `/` at computer width, update only that assertion to the 14-day behaviour and list it in the report. Stop if a test of another page changes result.

## 9. Report
`docs/tasks/0521-report.md`: Status, test and lint tails, `git diff --stat origin/main`, screenshot paths, updated assertions, deviations.
