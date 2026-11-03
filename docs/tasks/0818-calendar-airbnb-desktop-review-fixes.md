# 0818: Fix what the 0816 screenshot review found (tablet and desktop calendar)

Status: done
Depends on: 0816 (committed) | Branch: claude/project-thread-6aeyrs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The orchestrator reviewed `docs/tasks/screenshots-0814/calendar-range-768.png` and `calendar-range-1280.png`. Tiles, chips, selection and the side panel work (tests green), but the page is not Airbnb-clean yet. Fix section 2, retake the 0816 screenshots.

## 2. Context

1. Prev / Today / next are coral filled buttons at ≥768 px. Make them like the phone (0817): 40 px, background `#f2f2f0`, ink text/chevron, no border; Today a 40 px soft pill. Toolbar order: month title left (24 px, 700), controls right, 12 px gaps.
2. With the panel open the toolbar controls (property select, Month/scale segment) slide under the panel. Apply the panel padding-right to the whole `.dashboard-calendar` (toolbar and grid), not only the grid body, so nothing sits under the panel. At 1280 px the grid must use the full width left of the panel (it stops ~40 px short now).
3. At 768-1023 px the chips are too narrow for text (they show "R", "O"). There, show chips as 6 px tall coloured bars (no text, same left-border colour as background), max 3, then `+n`. Text chips stay at ≥1024 px.
4. The help bubble `.havel-fab` overlaps the panel bottom: hide it while the panel is open at every width (0817 hides it on phone only).
5. Desktop (≥1024) `/?cal_view=calendar` still shows the dashboard blocks around the calendar ("Full calendar →" link, setup card above, "Today" table below). Josef wants a full-page calendar: when `cal_view=calendar`, show only the calendar at every width (the phone already does this; find how in the 0765 / 0814 template logic and extend it). If this needs a route change, stop and ask.

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/dashboard-calendar.css` | edit the 0816 block |
| `App/app/templates/_dashboard_calendar.html` | bump `?v=` css and js to `20261102-0818` |
| dashboard template that renders the blocks around the calendar (grep `cal_view`) | item 5 only |
| `App/tests/static_versions.json` | regenerate |
| `App/tests/test_dashboard_calendar_browser.py` | assertions for items 1-5 in `test_month_tiles_and_side_panel` |
| `docs/tasks/screenshots-0814/` | retake with `UBYHOST_TASK_SHOTS=1` |
| `docs/tasks/0818-report.md` | create |

## 4. Steps

1. `grep -n "0816" App/app/static/dashboard-calendar.css`, read that block.
2. CSS 1-4, template 5, tests, screenshots, report.

## 5. Do not touch

JS selection logic, cleaning mode (`data-cleaning="true"`), phone rules (≤767 px), week/year/gantt views.

## 6. Commands

From `App/` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1`: `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_cleaning_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (600 s timeout). Repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

New assertions: arrow and Today background not coral; with the panel open no visible `.cal-toolbar`/`.cal-heading` control has its right edge past the panel's left edge; at 768 chips have no visible text; `.havel-fab` hidden while the panel is open; at 1280 `/?cal_view=calendar` has no "Today" table and no "Full calendar" link.

## 7. Acceptance

- [ ] All tests pass, 0 skipped. Screenshots retaken.
- [ ] Lint OK. Only section 3 files changed.

## 8. Stop and ask

Item 5 needs a route or Python change; a cleaning test fails twice; 25 tool calls.

## 9. Report

`docs/tasks/0818-report.md`: files, test last lines, deviations.
