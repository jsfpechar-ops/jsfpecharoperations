# 1004: Calendar month/year jump selects in Month view, week-view cleaning chip fixes

Status: todo
Depends on: 1001 (touches the same CSS and JS; merge it first) | Base commit: HEAD after 1001 | Branch: task/1004-ux-calendar-view-controls
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner feedback on the host full calendar (`/?cal_view=calendar`): the Month view has no month and year jump selects, while the Week view does; they must look the same in both, and the Year view shows only the year select. In the Week view the amber "Cleaning" chip sits over the Sunday day number and shows a dark left border; both are CSS-only fixes.

## 2. Context

Rules: light mode only; host UX gate (AGENTS rule 10); no new dependency; no copy change (the selects already carry `calendar.month_label` / `calendar.year_label`). Read nothing else.

Root causes found by the orchestrator:

- The selects `[data-cal-month]` and `[data-cal-year]` already exist in the toolbar and `changePeriod` (JS lines ~939-944) already handles both. They are hidden in Month scale only by CSS rule 0832 (at 768 px and up). `syncControls` in the JS already hides the month select in Year view (`currentView === "calendar" && state.scale === "year"`), so the CSS rule can simply go. No JS change.
- At 767 px and below, a separate rule (0955 phone decision) hides the selects on purpose. Keep it. Phone stays as is.
- The cleaning chip in the Week view is `.cal-event.is-cleaning-marker` inside `.cal-week-events`, which starts `top:28px`, which is inside the day-number band. Its dark left edge is `border-left:3px solid var(--amber)`.
- Bookings and cleanings already live in separate lanes in the Week view (`lanes()` and `cleaningRows`), so they do not overlap each other; no lane change needed.
- The Week-view reservation pill starts and ends part-way through a day cell on purpose (check-in and check-out times, `startFraction` and `endFraction` in `lanes()`). It runs from Thursday into Sunday because the stay departs on Sunday. That is the data model, not CSS. Do NOT change it (see §8).

Anchors (each must be found verbatim, else STOP):

`App/app/static/dashboard-calendar.css`, in the 0832 block (grep: `grep -n "0832: full-page calendar" App/app/static/dashboard-calendar.css`), the whole line:
```
  .dashboard-calendar[data-readonly="false"]:has([data-cal-view="calendar"][aria-pressed="true"]):has([data-cal-scale="month"][aria-pressed="true"]) :is([data-cal-month],[data-cal-year]) { display:none; }
```
Same file, the week overlay rule:
```
.cal-week-events { position:absolute; left:1px; right:1px; top:28px; display:grid;
```
Same file, the cleaning chip rule (4 lines inside it, the border line):
```
  border:1px solid var(--status-action-border); border-left:3px solid var(--amber); border-radius:6px;
```
`App/app/templates/_dashboard_calendar.html` line 2: `<link rel="stylesheet" href="/static/dashboard-calendar.css?v=` (match up to `?v=`; the value after it changes).

`App/tests/test_dashboard_calendar_browser.py`, function `test_month_tiles_and_side_panel` (grep `-n "def test_month_tiles_and_side_panel"`), two identical lines:
```
        assert page.locator("[data-cal-month]:visible, [data-cal-year]:visible").count() == 0
```
(they are at about lines 864 and 908; both are in Month scale at widths 768, 1024, 1280, 1440).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/dashboard-calendar.css | edit | delete 1 rule; `top:28px` to `top:40px`; drop the 3 px left border |
| App/app/templates/_dashboard_calendar.html | edit | bump the CSS cache key |
| App/tests/test_dashboard_calendar_browser.py | edit | the 2 assertions above now expect both selects visible |

No other file may change. The JS file stays untouched.

## 4. Steps

1. CSS: delete the whole anchor line `.dashboard-calendar[data-readonly="false"]:has(... [data-cal-scale="month"] ...) :is([data-cal-month],[data-cal-year]) { display:none; }` (leave the `@media (min-width:768px) {` line and the two rules after it). Check: `grep -c ':is(\[data-cal-month\],\[data-cal-year\])' App/app/static/dashboard-calendar.css | tail -30` prints `0`.
2. CSS: in `.cal-week-events` change `top:28px;` to `top:40px;` (only that declaration; the mobile override `top:46px` stays). Check: `grep -n "^.cal-week-events { position:absolute" App/app/static/dashboard-calendar.css | tail -30` shows `top:40px`.
3. CSS: in the cleaning chip rule replace `border-left:3px solid var(--amber); ` with nothing, so the line reads `  border:1px solid var(--status-action-border); border-radius:6px;`. Check: `grep -n "border-left:3px solid var(--amber)" App/app/static/dashboard-calendar.css | tail -30` prints nothing (if it still prints a line inside a `.cal-tile-chip` rule, leave that one; only the `.is-cleaning-marker` rule changes).
4. Template: set the CSS cache key to `?v=20261107-1004` (same line, only the value after `?v=`). Check: `grep -n "dashboard-calendar.css?v=" App/app/templates/_dashboard_calendar.html | tail -30`.
5. Tests: in `test_month_tiles_and_side_panel`, replace each of the two anchor lines with:
```
        assert page.locator("[data-cal-month]:visible, [data-cal-year]:visible").count() == 2
```
6. Run the commands in §6. Open the screenshots (§7). If a layout-lint finding appears on the toolbar, do not silence it: report it.

## 5. Do not touch

`dashboard-calendar.js`, `host_i18n.py`, the 767 px and below rule hiding the selects (`[data-cal-month]` / `[data-cal-year]` with `display:none !important`), pill fraction logic (`lanes`, `placeEvent`, `pillRow`), `.cal-tile-chip` rules, any other test file. Hard rules: no new dependency, light mode only, no em dashes.

## 6. Commands

From `App/`, each ending as shown:

1. `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0955_calendar_toolbar_stable_browser.py tests/test_dashboard_calendar.py -q --tb=short -x 2>&1 | tail -30` (test-map row "Calendar": the `test_dashboard_calendar*` files; 0 skipped, use `UBYHOST_REQUIRE_BROWSER=1`). Expect all pass.
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expect 0 findings on host pages, 0 skipped.
3. `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0956_calendar_rule_colours_browser.py -q --tb=short -x 2>&1 | tail -30` (the cleaning chip lives on the cleaning page too). Expect pass.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] At 768, 1024 and 1280 px, Month view shows both selects in the same place and size as the Week view; changing the month or year select reloads the calendar to that month (0955 tests prove it).
- [ ] Year view shows only the year select (month select hidden by `syncControls`); phone (390 px) toolbar is unchanged.
- [ ] Week view: the cleaning chip starts below the day-number row and has a 1 px border all round (no dark left edge); it overlaps no number and no reservation pill.
- [ ] Commands 1 to 4 pass; layout lint green with 0 skipped.
- [ ] Screenshots opened from `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` for the calendar page, plus your own of Month and Week view at 1280 (`/?cal_view=calendar&cal_scale=week`), attached in the report with one line per width: "390: ...; 768: ...; 1280: ...". Also tick the [design-system checklist](../design/design-system.md) in the PR.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (1001 may have moved it: report the new text, do not guess);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens;
- a file outside §3 needs a change;
- the owner's pill complaint is still visible: the Week-view reservation pill running from mid-Thursday to mid-Sunday is the check-in and check-out fraction logic in `lanes()`, not CSS. Do not attempt it. Report instead: the stay's dates, the pill's start and end fractions (`data-cal-from`/`data-cal-to` or the inline `margin-left` / `margin-right`), and the screenshot, so the orchestrator writes a separate brief (decision needed: clip fractions to whole day cells or keep the times);
- the cleaning chip still overlaps the day number at 768 px after `top:40px`: report the measured heights instead of guessing another value.

## 9. Report

Write `docs/tasks/1004-report.md` (600 tokens at most), set `Status: review`: files changed (`git diff --stat`), last 5 lines of each command, §7 ticked, deviations, what you still see in the screenshots. Hand merge and deploy to the owner.

## Extra request (owner, added later; do after the steps above, same files family)

Cleaning calendar page, desktop width (>=1024px): picking a date range opens the "Add cleaning" side panel as a column next to the month grid, which squeezes the grid into a narrow column and truncates the Reservation and Cleaning pills ("Clean", "Reser..."). Fix small: grep `cleaning-page` and the panel class in `App/app/static/app2.css` and `App/app/templates/cleaning*.html`. On >=1024px make the panel an overlay (position: fixed or absolute, right side, width 360px, full height or below the header, soft shadow, z-index above the grid) so the grid keeps its full width and does not reflow when the panel opens; keep the existing bottom-sheet behaviour below 1024px unchanged. Take a 1280 screenshot with the panel open and a range selected and confirm the grid width is unchanged; if the panel is not reachable in the browser tests, say so in the report. Report in `1004-report.md`.
