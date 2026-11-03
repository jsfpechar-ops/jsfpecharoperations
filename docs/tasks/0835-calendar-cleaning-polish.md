# 0835: Polish found in the 0834 screenshot review

Status: todo
Depends on: 0834 (committed) | Branch: claude/project-thread-6aeyrs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Review of `docs/tasks/screenshots-0814/calendar-range-1280.png`, `cleaning-390.png`, `cleaning-1280.png` (retaken after 0834). Fix section 2 in the Airbnb style, retake the shots with `UBYHOST_TASK_SHOTS=1`.

## 2. Context

1. `calendar-range-1280.png` (`/?cal_view=calendar`): a "Guest / Property / Dates" table (the Today table) still shows under the calendar. Find why `cal-hide` (0832) does not hide it on that test URL (the test may use a `cal_date` URL or a different template block) and hide it. A leftover heading-less red bar and "! Guest link has a new six-digit PIN" banner above the title: check if they come from the test fixture only; if they are real app blocks, give them `cal-hide` too.
2. `cleaning-1280.png`: toolbar is 4 stacked rows. Make it one row like the host calendar (title left; prev/Today/next; then property select, Calendar/Gantt, filter, Month/Week/Year right-aligned, wrap only if needed). Remove the fine-print line "Cleanings are created from departures..." from the page (move into help "?" if a help hook exists, else drop; no-fine-print rule) and make "+ Add cleaning" / "Property instructions & codes" real soft 40 px buttons (12 px gap) or move them into the filter menu. Month title "October 2026" 24 px 700 like the calendar page.
3. `cleaning-390.png`: tags are tiny 18 px icons without label: fine for tiles, but also the page police banner and the property select take 40% of the screen; at ≤767 px hide the police banner on the cleaning page (as on the calendar page, `cal-hide`) and put the month title and arrows on one row with the select above at 48 px. Add `cleaning-range-390.png` (long-press range selection on `/cleaning`, CDP touch as in 0814's test) and `cleaning-range-1280.png`.
4. Year view on the host cleaning page must draw cleanings only (no bookings).

## 3. Files

`App/app/static/dashboard-calendar.css` (append `/* 0835 */`), `dashboard-calendar.js` (item 4 only), `cleaning.css`, `App/app/templates/cleaning.html` / `_cleaning_screen.html` / `dashboard.html` (class hooks and the removed text only), `App/tests/test_cleaning_browser.py`, `App/tests/test_dashboard_calendar_browser.py`, `docs/tasks/screenshots-0814/`, `docs/tasks/0835-report.md`. Do not bump `?v=`; the orchestrator does. Never stage or commit; never touch `docs/tasks/screenshots-0387/`. i18n: no new key; removing text means keeping the key if tests reference it.

## 4. Steps

1. `grep -n "cal-hide" App/app/templates/dashboard.html`, `grep -n "Today\|today" ` the calendar test for the URL used.
2. Items 1-4, tests, shots, report.

## 5. Do not touch

Shared read-only cleaner page, phone host calendar look (0817), server code.

## 6. Commands

From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py -q --tb=short 2>&1 | tail -30` (600 s). New assertions: no visible Today table on `?cal_view=calendar` at 1280; cleaning toolbar controls share one row at 1280; no element with more than 90 characters of plain text in `.cleaning-page` header at ≥768.

## 7. Acceptance

All pass, 0 skipped. 5+ cleaning shots. Only section 3 files changed.

## 8. Stop and ask

A fix needs Python; a test fails twice; 30 tool calls.

## 9. Report

`docs/tasks/0835-report.md`: files, last test lines, deviations.
