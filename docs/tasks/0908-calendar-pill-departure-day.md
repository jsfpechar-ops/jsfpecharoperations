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
3. **The "+N" button (line 313).** It sits on a 7-column index. On the 14-column grid change `more.style.gridColumn = String(index + 1);` to `more.style.gridColumn = String(index * 2 + 1) + " / span 2";` so it still covers its whole day. Nothing else about "+N" changes.
3b. **Month edge.** A stay that departs on the 1st of the next month behaves like the Monday case in step 2: its bar ends at the edge of the last cell. No stub bar.
3c. **Lanes and the "+N" fold.** Keep lane assignment on whole days (`ends[lane] = right`, `last <= left`) so back-to-back stays still share a lane; with the half-cell columns they sit in the same lane without touching. `hidden[index]++` still counts by whole-day index; do not change it.
4. **Overflow guard.** Where the CSS gives the pill `margin:0 0 0 3px` or `margin:0 0 0 8px`, reduce the left margin to 0 for pills that start halfway (`:not(.continues-start)`), because the half cell is the offset now. Keep `.continues-start` as it is. Add NO right margin: the g/2 rule in 4b already keeps two touching bars one normal day gap apart, so the pill margin is `0` on both sides (remove the `margin-right:2px` an earlier run added at CSS lines 764 and 798).
5. **Avatar and name.** The name must still show at 390 px for a 1-night stay (half + half = 1 cell, about 50 px): that is allowed to ellipsize, as today. Do not change font size or height.

## 4b. Gap rule (orchestrator decision, 2026-11-04)

Keep the CSS `column-gap` on the 14-column grid as it is. Because the gap sits between the half-tracks, a bar starts g/2 to the right of the arrival cell's middle and ends g/2 to the left of the departure cell's middle (g = the grid column gap: 4 px phone, 12 px desktop). That is wanted: two touching stays end up exactly one normal day gap apart. So the tests expect: left edge = cell middle + g/2, right edge = cell middle - g/2, 1 px tolerance. Read g from `getComputedStyle(.cal-pills).columnGap`. Fix the new 0908 test and the 0891 right-edge assertion with that rule; change no CSS for it. The brief's earlier "middle of the cell" means these edges.

## 4c. Cache keys (found by CI, 2026-11-04)

`dashboard-calendar.css` and `dashboard-calendar.js` changed, so `tests/test_static_versions.py` requires a new `?v=` key for each in every template that loads them, then the manifest rewritten: bump the keys (for example `20261104-0908a`), then from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Run `tests/test_static_versions.py` and the three calendar files again, all passed, 0 skipped.

## 4d. Tap target of a Sunday arrival (found by CI browser shard 4, 2026-11-04)

`test_cleaning_browser.py` (layout lint, cleaning page at 768 px) fails with `tap target 41x44 (min 44): <a class="cal-pill continues-end">`: a stay that arrives on a Sunday and runs into the next week is now half a cell wide (41 px). Fix in `dashboard-calendar.css`, in the 768 px and up pill rule only (line ~798, where the pill is 32 px high): `min-width:44px`, and for `.cal-pill.continues-end` add `justify-self:end` so a narrow bar grows to the left and stays inside the week row. Do not change the phone rule (thin 8 px cleaning bars are not tap targets). Then run `test_cleaning_browser.py`, `test_dashboard_calendar_browser.py`, `test_0905_cleaning_calendar_stays_browser.py` and `test_static_versions.py`; if the CSS file changed, bump its `?v=` key again (`20261104-0908b`, `_dashboard_calendar.html` line 2) and rerun `tests/test_static_versions.py --write`. Add to the new 0908 test (or a second one) a Sunday-arrival stay at 768 px that asserts the bar is at least 44 px wide and its right edge is inside the row.

## 4e. Minimum width 48, not 44 (found by CI browser shard 1, 2026-11-04)

After 4d the layout lint reports `clipped-text` on `a.cal-pill.continues-end` at cleaning@768 and cleaning@1024 (`48>44`): the pill's content (24 px avatar + 8 px gap + 4 px left and 12 px right padding) needs 48 px, the min-width gives 44. In the 768 px+ pill rule change `min-width:44px` to `min-width:48px` (44 px tap target still holds). Bump both `?v=` keys to `20261104-0908d`, rerun `tests/test_static_versions.py --write`, and run in full: `tests/test_static_versions.py`, `tests/test_cleaning_browser.py`, `tests/test_dashboard_calendar_browser.py`, `tests/test_0905_cleaning_calendar_stays_browser.py` (0 skipped). The Sunday-arrival test keeps its 44 px floor.

## 5. Do not touch

`app2.css` cleaning bars, the dashboard phone tile dots, the list view, the Gantt view, any other test file (except changing one pinned edge number, said in the report).

## 6. Commands

From `App/`: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_cleaning_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- A stay 5 to 8 renders a pill from the middle of the 5th cell plus g/2 to the middle of the 8th minus g/2 (1 px tolerance, step 4b) at 390 px and 1280 px; the new test pins it.
- A stay that starts in the previous week keeps its left edge on the Monday cell edge; one that runs into the next week keeps its right edge on the Sunday cell edge.
- Two touching stays (one leaves the 8th, one arrives the 8th) share a lane and do not overlap.
- The three test files above pass with 0 skipped.

## 8. Stop and ask

STOP and report if: a line range above no longer matches, `event.end` turns out to be the last night and not the departure date, or the 14-column grid breaks the "+N" button placement.

## 9. Report

`docs/tasks/0908-report.md`. Per rule 7: one 390 px screenshot of the month view with a stay ending mid-week, one with two back-to-back stays on the same day, and one 1280 px; one line each on what you saw. Do not commit, do not push.
