# 0702: Overview look, part 2: the 14-day calendar as a calm card with colour bars
Status: todo
Depends on: PR #657 branch | Base commit: claude/project-thread-50hyv5 | Branch: task/0702-overview-calendar-card
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
On Overview (`/`) at computer width, in the 14-day mode (`state.fixed` in `dashboard-calendar.js`, set by 0521), the calendar looks like the mockup's "Kalendář" card (`/mnt/project-files/ux-redesign/overview/mockup-overview-1280.png`; mockup CSS `.cgrid .cd .crow .cn .bar .b-ok .b-warn .b-grey` in `/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`): heading "Kalendář" (use the existing calendar heading text), one white card (`#fff`, `1px solid #ebebe7`, radius 12px), day headers 11px ink-3 with today's column tinted `#fdece8` and coral text, property names 13px/600 on the left, row lines `#ebebe7`, rows 44px high, stays as fully rounded 28px bars with 12px/600 text: done -> `#e6f5ec`/`#167044`, action and ready -> `#fff4d6`/`#8a5200`, overdue -> `#fdecea`/`#b42318`, neutral -> `#efefeb`/`#55554f`. The month view stays one click away (owner's pick): in 14-day mode the toolbar shrinks to one quiet row on the right of the heading: the view switch (14 dní / Kalendář / Gantt) and the prev/today/next arrows; the property filter, settings button and period title are hidden in 14-day mode only.

## 2. Context
- `App/app/static/dashboard-calendar.css` styles the calendar (`.cal-gantt-*`, `.cal-event`, `.cal-heading*`, `.cal-toolbar*`). Event bars get `cal-event is-<tone>` (tones: neutral, overdue, action, ready, done; see `App/app/routes/dashboard_calendar.py` ~line 85).
- Mark 14-day mode for CSS with ONE line in `syncControls()` of `App/app/static/dashboard-calendar.js`: `root.classList.toggle("is-fixed-days", Boolean(state.fixed) && view() === "gantt");`. All styling then hangs off `.dashboard-calendar.is-fixed-days` inside `@media (min-width:768px)`, so month view, phone and the cleaning page are untouched.

## 3. Files
Edit `App/app/static/dashboard-calendar.css`, `App/app/static/dashboard-calendar.js` (that one line only), `?v=` keys for both (in `App/app/templates/base.html` for the CSS if linked there, and `_dashboard_calendar.html` for the JS; value `20261101-0702`), `App/tests/static_versions.json` (via `--write`), `docs/design/catalog.json` (add `is-fixed-days` if design lint asks). Create `App/tests/test_0702_overview_calendar_card_browser.py`. Screenshots `docs/tasks/screenshots-0702/`. Report `docs/tasks/0702-report.md`.

## 4. Steps
1. The JS line, `node --check`, commit `0702 step 1`.
2. CSS block at the end of `dashboard-calendar.css` headed `/* 0702 Overview 14-day card (mockup v2) */` with the values in section 1. Commit `0702 step 2`.
3. Version keys + `--write`; design lint. Commit `0702 step 3`.
4. Test at 1280 px on `/`: root has `is-fixed-days`; the property filter and settings button are not visible; a `done` stay bar has background rgb(230, 245, 236) and `border-radius` >= 14 px; clicking "Kalendář" removes `is-fixed-days` and the toolbar controls are visible again. At 1280 px on `/cleaning` the root never has `is-fixed-days`. Commit `0702 step 4`.
5. Screenshot `/?lang=cs` calendar area at 1280 px with several stays of different tones. Commit `0702 step 5`.

## 5. Do not touch
Calendar logic, dialogs, month/week/year views, phone dots, cleaning page, templates other than the version key, `dashboard.html`, `workflow.css`, `host2.css`.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0702_overview_calendar_card_browser.py tests/test_0521_overview_14_days_browser.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_calendar.py tests/test_dashboard_phone_browser.py tests/test_cleaning_browser.py tests/test_static_versions.py -q --tb=short -x -rs 2>&1 | tail -30`; `python3 scripts/design_lint.py | tail -3`; `python3 scripts/context_lint.py 2>&1 | tail -3` from the repo root.

## 7. Acceptance
All pass, 0 skipped; diff only section 3 files.

## 8. Stop and ask
Stop if any existing test changes result.

## 9. Report
`docs/tasks/0702-report.md`: Status, tails, diff stat, screenshots, deviations.
