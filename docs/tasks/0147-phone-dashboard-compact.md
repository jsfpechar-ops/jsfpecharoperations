# 0147: phone dashboard, part 1: month calendar as dots, reduced controls

Status: todo
Depends on: 0133-fix-5 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part 2 (one PIN alert, one-line setup banner) is [0148](0148-phone-dashboard-alerts-banner.md). Commit each step as `0147 step k`. Never push, never open a PR. Page file: `docs/design/pages/dashboard.md` (already updated by the orchestrator; read its "Phone" section once).

## 1. Objective

Below 768 px the dashboard month calendar is as tall as the rest of the page (390 px screenshot: each week is 94 px or more because stays render as 46 px text bars). Owner decision:

1. On phone, each day cell shows its stays as small dots (one per stay, property colour, at most 3, then "+n"), never as text bars. Tapping a day opens the existing day dialog (`[data-cal-day-dialog]`, which lists that day's stays and has an Add button). Desktop (768 px and up) is unchanged: bars, drag to create, click a day to create.
2. On phone the controls shrink to the property picker, the previous/next arrows, Today and the month title (orchestrator: Today kept). Hidden below 768 px: the Calendar/Gantt toggle, the settings button, the Month/Week/Year segment, and the month and year selects.
3. Phone = `(max-width: 767px)`, the same breakpoint `host2.css` uses. The cleaning page shares this calendar partial; nothing changes there (`data-cleaning="true"`).

Dots use the three property colours already defined by `[data-cal-color]` (teal, blue, purple). No coral (MASTER 4).

## 2. Context

The month grid is built in `App/app/static/dashboard-calendar.js` `renderCalendar()` (one `.cal-week` per week: a `.cal-week-days` row of seven `.cal-day` cells, each with a `button.cal-day-number[data-cal-day]`, plus a `.cal-week-events` overlay holding the `.cal-event` bars). `openDay(day)` already fills and shows the day dialog; `openCreate(...)` is what a day click does today. `propertyColor(id)` returns "teal", "blue" or "purple"; `displayOverlap(event, from, to)` says whether an event touches a day. `view()` decides gantt vs calendar; `autoView` picks gantt for 3 or more properties, which must never happen on phone.

`App/app/static/dashboard-calendar.css` is not in `enforced_stylesheets` (`docs/design/catalog.json`), but MASTER 10.2 still applies: spacing, radius and font size through tokens (`--space-1`, `--space-2`, `--radius-pill`, `--size-11`); `width`/`height` in px are allowed. Colours only through existing variables.

Anchors (copy exactly; each occurs once in its file).

Anchor A, `dashboard-calendar.js`:
```
  function propertyColor(id) { return ["teal", "blue", "purple"][Math.abs(Number(id)) % 3]; }
```
Anchor B, `dashboard-calendar.js`:
```
  function view() { return autoView(state.mode, state.property ? 1 : state.properties.length); }
```
Anchor C, `dashboard-calendar.js` (two lines):
```
  async function load() {
    const number = ++requestNumber;
```
Anchor D, `dashboard-calendar.js`:
```
    const mobile = matchMedia("(max-width:760px)").matches;
```
Anchor E, `dashboard-calendar.js` (three lines, inside `renderCalendar`):
```
        button.title = labels.keyboard; day.append(button); days.append(day);
      }
      const overlay = el("div", "cal-week-events");
```
Anchor F, `dashboard-calendar.js` (two lines, inside the root click handler):
```
      if (Date.now() < suppressClickUntil || state.loading || !lastLoadedRange) return;
      openCreate(day.dataset.calDay, addDays(day.dataset.calDay, 1), day.dataset.property || state.property, cleaningMode ? "cleaning" : "stay", day); return;
```
Anchor G, `dashboard-calendar.js` (inside the `resize` listener):
```
    if (!state.loading && lastLoadedRange) render();
```
Anchor H, `App/app/templates/_dashboard_calendar.html` line 2 and line 170:
```
<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261016-0123o-0106">
```
```
<script src="/static/dashboard-calendar.js?v=20261016-0123-refresh3" defer></script>
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/dashboard-calendar.js | edit | Anchors A to G (step 1) |
| App/app/static/dashboard-calendar.css | edit | append the block in step 2 |
| App/app/templates/_dashboard_calendar.html | edit | Anchor H cache-bust (step 2) |
| App/tests/test_dashboard_calendar_browser.py | edit | six phone branches (step 3) |
| App/tests/test_dashboard_phone_browser.py | create | step 4 |
| docs/tasks/0147-report.md | create | step 6 |
| docs/tasks/0147-evidence/ | create | two screenshots (step 6) |

No other file may change. `dashboard.html`, `host2.css`, Python and `host_i18n.py` stay untouched in this brief.

## 4. Steps

1. `dashboard-calendar.js`, seven edits, then commit `0147 step 1`:

   a. Below Anchor A add one line:
   ```
     function phoneDots() { return !cleaningMode && matchMedia("(max-width:767px)").matches; }
   ```
   b. Replace Anchor B with:
   ```
     function view() { return phoneDots() ? "calendar" : autoView(state.mode, state.property ? 1 : state.properties.length); }
   ```
   c. Replace Anchor C with:
   ```
     async function load() {
       const number = ++requestNumber;
       if (phoneDots() && state.scale === "year") state.scale = "month";
   ```
   d. Replace Anchor D with:
   ```
       const mobile = matchMedia("(max-width:760px)").matches, dots = phoneDots();
   ```
   e. Replace Anchor E with:
   ```
           button.title = labels.keyboard;
           if (dots) {
             const dayEvents = state.events.filter(event => event.kind !== "cleaning" && displayOverlap(event, date, addDays(date, 1)));
             const marks = el("div", "cal-dots");
             marks.dataset.calDots = String(dayEvents.length);
             dayEvents.slice(0, 3).forEach(event => { const dot = el("span", "cal-dot"); dot.dataset.calColor = propertyColor(event.propertyId); marks.append(dot); });
             if (dayEvents.length > 3) marks.append(el("span", "cal-dot-more", "+" + String(dayEvents.length - 3)));
             button.append(marks);
             if (dayEvents.length) day.classList.add("has-stays");
           }
           day.append(button); days.append(day);
         }
         if (dots) {
           const row = el("div", "cal-week is-dots"); row.style.setProperty("--lanes", "1");
           row.append(days); body.append(row);
           continue;
         }
         const overlay = el("div", "cal-week-events");
   ```
   f. Replace Anchor F with:
   ```
         if (Date.now() < suppressClickUntil || state.loading || !lastLoadedRange) return;
         if (phoneDots()) { openDay(day.dataset.calDay); return; }
         openCreate(day.dataset.calDay, addDays(day.dataset.calDay, 1), day.dataset.property || state.property, cleaningMode ? "cleaning" : "stay", day); return;
   ```
   g. Replace Anchor G with:
   ```
       if (!state.loading && lastLoadedRange) { if (phoneDots() && state.scale === "year") load(); else render(); }
   ```
   Then `node --check App/app/static/dashboard-calendar.js | tail -3` (no output = OK).

2. Append to the end of `App/app/static/dashboard-calendar.css`:
   ```
   /* 0147: phone month view shows dots, not bars; controls shrink to property, arrows, title. */
   .cal-dots { display:flex; align-items:center; justify-content:flex-end; gap:var(--space-1); min-height:8px; pointer-events:none; }
   .cal-dot { flex:0 0 6px; width:6px; height:6px; border-radius:var(--radius-pill); background:var(--cal-ink); }
   .cal-dot-more { font-size:var(--size-11); line-height:1; color:var(--ink-muted); }
   @media (max-width:767px) {
     .dashboard-calendar .cal-week.is-dots .cal-week-days { min-height:0; }
     .dashboard-calendar .cal-week.is-dots .cal-day-number { display:flex; flex-direction:column; align-items:flex-end; justify-content:space-between; height:48px; min-height:48px; padding:var(--space-1) var(--space-2); }
     .dashboard-calendar[data-cleaning="false"] .cal-view-segment,
     .dashboard-calendar[data-cleaning="false"] [data-cal-settings],
     .dashboard-calendar[data-cleaning="false"] [data-cal-scales],
     .dashboard-calendar[data-cleaning="false"] [data-cal-month],
     .dashboard-calendar[data-cleaning="false"] [data-cal-year] { display:none !important; }
   }
   ```
   In `_dashboard_calendar.html` change both Anchor H version strings to `?v=20261019-0147` (keep the rest of each line). `python3 scripts/design_lint.py | tail -3` must print OK. Commit `0147 step 2`.

3. `App/tests/test_dashboard_calendar_browser.py`, six edits, commit `0147 step 3`:

   a. In `open_page`, replace
   ```
           page.wait_for_selector(".cal-gantt-row", timeout=10000)
   ```
   with
   ```
           page.wait_for_selector(".cal-gantt-row, .cal-week", timeout=10000)
   ```
   b. In `test_calendar_geometry_locales_and_screenshots`, replace
   ```
                   for mode in ("gantt", "calendar"):
                       page.locator(f'[data-cal-view="{mode}"]').click()
   ```
   with
   ```
                   for mode in (("calendar",) if width < 768 else ("gantt", "calendar")):
                       if width >= 768:
                           page.locator(f'[data-cal-view="{mode}"]').click()
   ```
   c. Same test, replace
   ```
                       icon = page.locator("[data-cal-settings] svg").bounding_box()
                       assert icon["width"] >= 18 and icon["height"] >= 18, icon
   ```
   with
   ```
                       if width >= 768:
                           icon = page.locator("[data-cal-settings] svg").bounding_box()
                           assert icon["width"] >= 18 and icon["height"] >= 18, icon
   ```
   d. Same test, replace the whole `if width <= 390:` block (from `                    if width <= 390:` down to and including `                        assert box["width"] >= 43.9 and box["height"] >= 44, box`) with
   ```
                       if width < 768:
                           assert page.locator(".cal-week-events .cal-event").count() == 0
                           assert page.locator(".cal-dots .cal-dot").count() >= 3
                           shown = page.locator(
                               ".cal-view-segment, .cal-scale-segment, [data-cal-month], [data-cal-year], [data-cal-settings]"
                           ).evaluate_all("nodes => nodes.filter(node => node.offsetParent).length")
                           assert shown == 0, shown
                           box = page.locator(".cal-day-number").first.bounding_box()
                           assert box["width"] >= 43.9 and box["height"] >= 44, box
   ```
   e. Same test, replace
   ```
                   page.locator('[data-cal-day="2026-10-15"]').click()
                   assert page.locator("[data-cal-create]").is_visible()
   ```
   with
   ```
                   page.locator('[data-cal-day="2026-10-15"]').click()
                   if width < 768:
                       assert page.locator("[data-cal-day-dialog]").is_visible()
                       assert page.locator("[data-cal-day-list] .cal-event").count() >= 1
                       page.locator("[data-cal-day-add]").click()
                   assert page.locator("[data-cal-create]").is_visible()
   ```
   f. In `test_create_popover_reclamps_when_switching_to_taller_stay_form`, replace
   ```
           page.locator("[data-cal-day]:visible").last.click()
           dialog = page.locator("[data-cal-create]")
   ```
   with
   ```
           page.locator("[data-cal-day]:visible").last.click()
           if width < 768:
               page.locator("[data-cal-day-add]").click()
           dialog = page.locator("[data-cal-create]")
   ```
   What changes and why: at 360, 390 and 760 the gantt toggle, settings button and segments are hidden, so the old `.cal-view-segment button` 44 px check and the settings-icon check no longer apply there; a day tap opens the day dialog first, and its Add button opens the create popover with the same prefilled dates. `test_host_quiet_dashboard_browser.py` needs no change (it counts `[data-calendar]` and rows only).

4. Create `App/tests/test_dashboard_phone_browser.py` with exactly this content (0148 adds to it; keep the two `# 0148` comment lines):
   ```python
   """Phone dashboard (0147, 0148): dots instead of bars, reduced controls, one PIN alert, one-line setup banner."""
   from __future__ import annotations

   import os

   import pytest

   REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
   if REQUIRE_BROWSER:
       import playwright.sync_api as sync_api
   else:
       sync_api = pytest.importorskip("playwright.sync_api")

   from tests.test_dashboard_calendar_browser import (  # noqa: F401
       calendar_origin, calendar_workspace, launch, open_page, shot,
   )

   HIDDEN_ON_PHONE = (".cal-view-segment", "[data-cal-settings]", "[data-cal-scales]", "[data-cal-month]", "[data-cal-year]")
   SHOWN_ON_PHONE = ("[data-cal-property]", "[data-cal-prev]", "[data-cal-next]", "[data-cal-period]")


   def visible_count(page, selector):
       return page.locator(selector).evaluate_all("nodes => nodes.filter(node => node.offsetParent).length")


   def test_phone_dashboard_compact(calendar_workspace, calendar_origin):
       with sync_api.sync_playwright() as playwright:
           browser = launch(playwright)
           for width in (390, 1280):
               context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, locale="en", touch=width < 768)
               if width < 768:
                   page.wait_for_selector(".cal-week.is-dots")
                   assert page.locator(".cal-week-events .cal-event").count() == 0
                   assert page.locator(".cal-dots .cal-dot").count() >= 3
                   assert page.locator(".cal-dot-more").first.inner_text() == "+1"
                   for selector in HIDDEN_ON_PHONE:
                       assert visible_count(page, selector) == 0, selector
                   for selector in SHOWN_ON_PHONE:
                       assert visible_count(page, selector) >= 1, selector
                   page.locator('[data-cal-day="2026-10-15"]').click()
                   assert page.locator("[data-cal-day-dialog]").is_visible()
                   assert page.locator("[data-cal-day-list] .cal-event").count() == 4
                   page.locator("[data-cal-day-dialog] [data-cal-close]").click()
                   # 0148: alerts and banner (390)
               else:
                   assert page.locator(".cal-dots").count() == 0
                   assert page.locator(".cal-gantt-row").count() >= 1
                   for selector in HIDDEN_ON_PHONE:
                       assert visible_count(page, selector) >= 1, selector
                   # 0148: alerts and banner (1280)
               assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
               shot(page, f"phone-{width}")
               context.close()
           browser.close()
   ```
   Commit `0147 step 4`.

5. Browser run, from `App/`:
   `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0147 .venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_host_quiet_dashboard_browser.py -q --tb=line -rs 2>&1 | tail -15`
   Expected: pass, 0 skipped.

6. Open `calendar-phone-390.png` and `calendar-phone-1280.png` from the shots dir and confirm by eye: at 390 every week row is one line of day numbers with dots under them (no text bars; a "+1" on 14 to 18 October), the toolbar is arrows left and "October 2026" right, the property select above it, no Gantt/settings/segments/selects (Today stays); at 1280 the page is unchanged from `docs/tasks/0102-evidence` style (gantt with bars, all controls). Copy both files to `docs/tasks/0147-evidence/`. Run ruff: `App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 App/tests/test_dashboard_phone_browser.py | tail -3`. Write `docs/tasks/0147-report.md` (Status: review or blocked; the pytest tail; what you saw in the two screenshots; the two evidence paths). Commit `0147 report` with `git add docs/tasks/0147-report.md docs/tasks/0147-evidence`.

## 5. Do not touch

`dashboard.html`, `_host_alerts.html`, `host2.css`, `host_i18n.py`, any Python, the cleaning page, the gantt and year renderers, `catalog.json`.

## 6. Commands

As in steps 1, 2, 5 and 6. Every command ends with `| tail -N`.

## 7. Acceptance

- [ ] `node --check` and `design_lint.py` print nothing / OK.
- [ ] Step 5 passes with 0 skipped.
- [ ] Step 6 is confirmed in the report with both screenshots committed.
- [ ] No `.cal-event` inside `.cal-week-events` at 390; dots use `data-cal-color`, never coral.

## 8. Stop and ask

Stop if a test fails twice after your fix attempt, if an anchor is not found verbatim (do not guess a nearby line), or if a tap on a day at 390 still opens the create popover. Report the assertion or the anchor verbatim in the report and set Status: blocked.

## 9. Report

As in step 6.
