# 0908: Calendar stay bars end halfway into the departure day

Status: todo
Depends on: nothing | Base commit: current main | Branch: the orchestrator's branch (do not create one)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Length: about 70 lines.

## 1. Objective

On the host calendar (month view, v2, `data-readonly="false"`), a stay bar now ends at the right edge of the last night. The departure day is an empty cell, so the host cannot tell which day the guest actually leaves (Josef, 2026-11-04, phone screenshots: bars "Vivus Apartment..." end on Tue 3 and the white Wed 4 looks free).

Make the bar end **halfway into the departure day** (the Airbnb look). To keep back-to-back stays readable, the bar also **starts halfway into the arrival day**. Result for a stay 5 Nov to 8 Nov: the bar runs from the middle of the 5th to the middle of the 8th. Two stays that touch (one leaves the 8th, the next arrives the 8th) then meet in the middle of that cell with a small gap, never overlapping.

## 2. Context

- Code: `App/app/static/dashboard-calendar.js` around lines 286 to 310 (the `.cal-pills` overlay, one pill per stay per week, `event.start` = arrival date, `event.end` = departure date, exclusive). CSS: `App/app/static/dashboard-calendar.css` lines 763 to 802 (pill rules, phone 1 lane, 768 px and up 3 lanes). `app2.css` lines 2213 to 2220 are the cleaning page thin bars: leave them as they are (cleaning bars are not stays to leave).
- **Do not** touch the dashboard phone tile dots, `cal-event` (list view) or the Gantt view.
- No new dependency. `dashboard-calendar.css` is not linted for px; keep the existing style of the file.

## 3. Files

- `App/app/static/dashboard-calendar.js` (pill code, lines 286 to 310)
- `App/app/static/dashboard-calendar.css` (lines 763 to 802)
- `App/tests/test_dashboard_calendar_browser.py` (one new test)
- `docs/tasks/0908-report.md` (new)

## 4. Steps
1. **Half-cell grid.** Change the `.cal-pills` grid from 7 to 14 columns (`repeat(14,minmax(0,1fr))`, both the phone and the 768 px rules). In the JS, a pill's `gridColumn` becomes: start line `column*2 + 1 + (event.start >= from ? 1 : 0)`, end line `(column+span)*2 + 1 + (event.end < to && event.end > from ? 1 : 0)`, written as `start / end`. In plain words: a real arrival starts at the middle of its cell; a real departure that falls inside this week ends at the middle of its cell; a bar that continues from or into another week keeps the full edge on that side (the existing `continues-start` / `continues-end` classes already square those corners).
2. **Departure on the next week's Monday.** A stay whose `event.end` equals the next Monday is currently dropped from that next week (`event.end > from` is false). Keep it dropped; its bar ends at the Sunday edge as today. Do not add stub bars. Write this edge case as one comment line in the JS.
3. **Lanes and the "+N" fold.** Keep lane assignment on whole days (`ends[lane] = right`, `last <= left`) so back-to-back stays still share a lane; with the half-cell columns they sit in the same lane without touching. `hidden[index]++` still counts by whole-day index; do not change it.
4. **Overflow guard.** Where the CSS gives the pill `margin:0 0 0 3px` or `margin:0 0 0 8px`, reduce the left margin to 0 for pills that start halfway (`:not(.continues-start)`), because the half cell is the offset now. Keep `.continues-start` as it is. Add 2px of right margin (`margin-right:2px`) so two touching bars never fuse.
5. **Avatar and name.** The name must still show at 390 px for a 1-night stay (half + half = 1 cell, about 50 px): that is allowed to ellipsize, as today. Do not change font size or height.

## 5. Do not touch

`app2.css` cleaning bars, the dashboard phone tile dots, the list view, the Gantt view, any other test file (except changing one pinned edge number, said in the report).

## 6. Commands

From `App/`: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_cleaning_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- A stay 5 to 8 renders a pill from the middle of the 5th cell to the middle of the 8th (1 px tolerance) at 390 px and 1280 px; the new test pins it.
- A stay that starts in the previous week keeps its left edge on the Monday cell edge; one that runs into the next week keeps its right edge on the Sunday cell edge.
- Two touching stays (one leaves the 8th, one arrives the 8th) share a lane and do not overlap.
- The three test files above pass with 0 skipped.

## 8. Stop and ask

STOP and report if: a line range above no longer matches, `event.end` turns out to be the last night and not the departure date, or the 14-column grid breaks the "+N" button placement.

## 9. Report

`docs/tasks/0908-report.md`. Per rule 7: one 390 px screenshot of the month view with a stay ending mid-week, one with two back-to-back stays on the same day, and one 1280 px; one line each on what you saw. Do not commit, do not push.
