# 0832: Full-page calendar at every width, Airbnb-clean toolbar

Status: done
Depends on: 0818 (committed 8d8f24c) | Branch: claude/project-thread-6aeyrs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef (2026-11-02 15:18/15:25): the calendar page must be a full page like the Airbnb host calendar on phone, tablet and desktop. The 0818 screenshots (`docs/tasks/screenshots-0814/calendar-range-768.png`, `calendar-range-1280.png`) still show dashboard blocks around the calendar and a crowded two-row toolbar with a truncated month title ("Octo…"). Fix both.

## 2. Context

1. **Full page (owner decision, orchestrator 0818 review: option a).** In `App/app/templates/dashboard.html` every block that carries `ph-hide` when `cal_view` (police banner, setup card, needs-you `section#needs-action`, `.ov-cal-block` heading/grid/"Full calendar" link, "Today" table and heading, the "Add stay" header button, the desktop page title) must be hidden at **every** width when `cal_view` is true. Add a class `cal-hide` next to `ph-hide` in those `{{ ' ph-hide' if cal_view }}` expressions (and the `{% if cal_view %} class="ph-hide"` one), and one CSS rule `.cal-hide{display:none!important}` in the 0832 block. Do not change `admin.py`. Phone look must stay the same.
2. **Tests that used the blocks on the calendar page.** `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place` (clicks `[data-dashboard-refresh="stats"] .needs-you-more > summary`, appends a banner to `[data-dashboard-refresh="work"]`) and `test_calendar_geometry_locales_and_screenshots` (expects the stats block and `.ov-cal-more` to have height at ≥1024) assume the blocks are visible. Change those parts: the refresh test checks the refresh in place on the calendar itself (the new event appears in the grid without a reload); drop the stats/`.ov-cal-more` height expectations and assert the opposite (hidden) instead. Keep every other assertion in those tests.
3. **Toolbar like Airbnb (≥768 px).** Row 1: month title left (24 px, 700, never truncated: `white-space:nowrap; flex:none`), then prev / Today / next. Row 2 (right-aligned, wraps if needed): property select, Calendar/Gantt segment, Month/Week/Year segment, filter button. The filter button must be soft (background `#f2f2f0`, ink icon, no coral, add class `soft` if it is a `.btn`). Hide the month and year `<select>`s in Month scale at ≥768 px (the arrows navigate; at 768 they render as empty boxes). Gaps 12 px. With the side panel open nothing may sit under the panel (0818's `margin-right` stays).
4. At 768 with the panel open the page heading "Calendar" must not be cut by the panel. Item 1 should remove it; if a heading remains, it must fit left of the panel.

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/dashboard.html` | item 1 classes |
| `App/app/templates/_dashboard_calendar.html` | item 3 only if a class is needed on the filter button or selects; do NOT bump `?v=` (orchestrator does it) |
| `App/app/static/dashboard-calendar.css` | append a `/* 0832 */` block at the end; do not edit other blocks |
| `App/tests/test_dashboard_calendar_browser.py` | items 2-4; new assertions in `test_month_tiles_and_side_panel` |
| `docs/tasks/0832-report.md` | create |

Another executor (0815) works in parallel on the same branch and checkout, in `dashboard-calendar.js`, the `/* 0815 */` CSS block and `test_cleaning_browser.py`. Do not touch those, and do not touch `static_versions.json`. Never stage or commit anything; never touch `docs/tasks/screenshots-0387/`.

## 4. Steps

1. `grep -n "cal_view" App/app/templates/dashboard.html`; `grep -n "0816\|0818" App/app/static/dashboard-calendar.css` and read the 0818 block.
2. Items 1, 3 (CSS), then tests 2 and new assertions, run tests, then report.

## 5. Do not touch

`admin.py` and any Python, JS, phone rules (≤767 px), cleaning mode, week/year/gantt views.

## 6. Commands

From `App/` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1`: `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_0199_phone_geometry_browser.py -q --tb=short 2>&1 | tail -30` (600 s timeout). Skip `test_static_versions.py` (orchestrator bumps versions after both briefs).

New assertions in `test_month_tiles_and_side_panel` at 768 and 1280 on `/?cal_view=calendar`: no visible `#needs-action`, `.ov-cal-more`, "Today" table; month title `scrollWidth <= clientWidth`; filter button background not coral; month/year selects hidden in Month scale; with the panel open every visible toolbar control's right edge ≤ the panel's left edge.

## 7. Acceptance

- [ ] Section 6 tests pass, 0 skipped. Screenshots retaken by the run.
- [ ] Only section 3 files (plus retaken screenshots) changed.

## 8. Stop and ask

Item 1 needs a Python change; a phone test fails twice; 25 tool calls.

## 9. Report

`docs/tasks/0832-report.md`: files, test last lines, changed old assertions and why, deviations.
