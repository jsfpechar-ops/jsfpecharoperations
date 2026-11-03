# 0891: Calendar and cleaning month view exactly like the Airbnb host calendar

Status: blocked
Depends on: 0842 (merged in the working tree) | Branch: claude/project-thread-6aeyrs (PR #723)
Executor: Haiku 5.5 | Fits one session: about 12 tool calls. All code is in one checked patch script (§4), so nothing is typed by hand.

## 1. Objective

Josef: "just do it exactly the same as airbnb". The host calendar (`/?cal_view=calendar`) and the host cleaning page (`/cleaning`, cleanings only), Month scale, at 390, 768 and 1280 px, look and behave like the Airbnb host calendar (references: `/mnt/project-files/airbnb-calendar-ref/ref-december-pills.png`, `ref-november-today.png`):

1. One continuous vertical scroll of 6 months. Each month is a `section.cal-month` with a bold heading ("October", or "January 2027" when the year is not this year) and its own 7-column grid. Days of other months are blank cells (no tile, no `data-date`).
2. Separate rounded tiles: radius 14 px, 1 px `#dddddd` border, white, 12 px apart both ways, 94 px tall at 768 px+ (phone keeps its 0873 (was 0814) size: 64 px tall, 4 px apart). Day number top-left, 16 px 600 `#222`. Past days: `#ebebeb` with a struck-through grey number. Today: number in the filled coral disc. Selected: `#222` with a white number.
3. Stays (host page only): dark `#222` pills drawn over the tiles in the lower half, spanning the nights, cut at the week end and at the month end and continued on the next row. 32 px tall, radius 16, white 13 px 600 text, a 24 px round initial on the left. More stays on a day: a small dark "+N" on the tile's top right opens the day list. No prices anywhere.
4. Cleaning page: no stay pills; the amber cleaning tags stay (24 px pill shape at 768 px+, the phone tags as today).
5. At 768 px+ a sticky head: the big month title left (32 px 700 at 1024 px+, 24 px at 768-1023) that follows the month under it while scrolling; the controls right as grey 40 px pills; under them the weekday row (small grey, no boxes) and a thin divider.
6. A floating round back-to-top button (48 px, white, shadow) bottom right, shown after 400 px of scroll.
7. Kept as they are: Monday week start (Josef did not ask to change it), the day-click to day-list to prefilled add flow, mouse drag range, phone long-press drag, the practice-mode banner on the phone host page, every hook the tests use (`.cal-day`, `[data-date]`, `[data-cal-day]`, `.cal-dot`, `.cal-tile-chip`, `[data-cal-day-dialog]`, `data-cal-*`).

## 2. Context (verified by the orchestrator; do not re-investigate)

- **Why one patch script.** About 30 edits in 7 files. The script in §4 holds every edit as an exact old/new pair, checks that each old text occurs exactly once in every file **before** writing anything, and stops with `STOP 0891: ...` otherwise. It was applied to a copy of the current files: all anchors unique, `node --check` and `py_compile` pass.
- **Month scroll (JS, `App/app/static/dashboard-calendar.js`).** `tiles()` (line 224) is true for the host calendar and the host cleaning page in Calendar view, Month scale, at every width. `range()` (line 134-141) then loads 6 months (about 190 days; both data routes allow 370: `App/app/routes/dashboard_calendar.py` line 28, `App/app/cleaning.py` line 43). `renderCalendar()` (line 279) wraps its week loop (line 285) in a loop over the 6 months; other scales keep one block. The month section uses `data-cal-section`, **not** `data-cal-month` (that is the month select; tests count `[data-cal-month]:visible`).
- **Pills.** New `pillRow()` builds `div.cal-pills` (a 7-column grid laid over the week row) with `a.cal-pill[data-cal-event][data-cal-from][data-cal-to]`, so a click opens the stay details through the existing `[data-cal-event]` click path (line 816); pointer and touch drags already ignore `[data-cal-event]` and `[data-cal-more]` targets (lines 697-698, 752-753). Pills are not in `.cal-week-events`, so the many `.cal-week-events ... count() == 0` assertions stay true. The per-day chips and dots (`.cal-tile-chips`, `.cal-dots`, `.cal-dot`, `.cal-dot-more`) are still rendered for the tests but hidden on the host page; the stays "+N" moves from `.cal-tile-more` (line 327, removed) to `button.cal-pill-more[data-cal-more]`, so `[data-cal-more="2026-10-14"]` stays unique and visible at 768 px+.
- **Pill geometry and clicks.** Tests click the centre of day buttons on days with stays (`2026-10-15` in `test_calendar_geometry_locales_and_screenshots`, phone long-press from the centre of `2026-10-03`). The pill top is at 50 px of a 94 px tile (centre 47) and at 40 px of a 64 px phone tile (centre 32), so the centre stays on the day button. That is why the pill is 32 px, not Airbnb's 48 px (their tile is about 130 px).
- **Sticky head.** The head controls were two grid areas of the root (0832, `dashboard-calendar.css` lines 710-716) and a root flex row on the cleaning page (0842, lines 735-740), so no single box could stick. The template now wraps `.cal-heading` and `.cal-toolbar` in `div.cal-head[data-cal-head]` (`App/app/templates/_dashboard_calendar.html` lines 4 and 29); the script replaces those 13 CSS lines with comments and puts one flex row on `.cal-head` for both pages (title left, controls right, wraps right-aligned when narrow). It is sticky only while month sections exist (`:has(.cal-month)`); at 768 px+ the JS moves the weekday row into the head. The window scrolls (`App/app/static/app2.css` line 20: `.app` is `min-height:100vh`, no inner scroller). Phone header layout (0873, 0842 phone block) is unchanged.
- **CSS cascade.** Every new rule starts with `body.v2 #calendar.dashboard-calendar[data-readonly="false"]` (1,4,1). That beats `app2.css` lines 895 and 1058-1066 (cleaning `#calendar *` font-size, 24/44 px min sizes) and the earlier tile rules of briefs 0873, 0875 and 0877 (code comments still say 0814, 0816, 0818; 0,2,0 to 0,4,0). The shared cleaner page (`data-readonly="true"`) is untouched. `.cal-week.is-dots` gets `isolation:isolate` so pills (z-index 1) never paint over the phone day sheet. The new buttons have no `.btn` class (`.btn:not(.soft)` forces white text).
- **Arrows in the scroll.** The scroll handler (bound once, like resize/popstate at line 979-983) sets the title to the month under the head and remembers it; prev/next step from that month and scroll to the top. While loading the handler does nothing, so 16 quick "next" clicks (`test_auto_view_threshold_filter_and_manual_override`) still step from `state.date`.
- **Kept on purpose (tell Josef in the report, do not change):** Monday start; our controls (arrows, Today, property, Calendar/Gantt as icons, filter, Month/Week/Year) instead of Airbnb's single "Month" dropdown, because Week, Year and Gantt need them; an initial instead of a guest photo (privacy); no price line (no money metrics); phone tiles 4 px apart (12 px at 320 px leaves 30 px tiles and breaks the 44 px tile test).
- **Existing tests that change (the script does it):** `test_dashboard_calendar_browser.py` line 868 (tiles `>= 96` becomes `>= 93`), lines 908-910 (768 px chip font check becomes "pills shown, chips hidden"); `test_cleaning_browser.py` line 847 (title `24px` becomes `32px`).
- **New tests (the script appends them):** `test_dashboard_calendar_browser.py`: `test_0891_airbnb_month_tiles_and_pills` (390, 768, 1280: 6 sections, 12/4 px neighbour gaps in rows and between rows, 94 px tiles, each pill covers exactly its nights' tiles, sits in the lower half, `#222`; "+N" visible; weekday row in the head; no overflow; shots), `test_0891_sticky_head_title_follows_scroll_and_back_to_top` (1280), `test_0891_calendar_no_horizontal_overflow` (320, 390, 768, 1024, 1280, 1440, top and bottom of the scroll). `test_cleaning_browser.py`: `test_0891_cleaning_airbnb_month` (390, 768, 1280; overflow at the six widths is already covered by `test_0842_cleaning_no_horizontal_overflow`).

## 3. Files

The script edits exactly these, and nothing else: `App/app/static/dashboard-calendar.js`, `App/app/static/dashboard-calendar.css`, `App/app/templates/_dashboard_calendar.html`, `App/app/host_i18n.py` (en and cs `calendar.back_to_top`), `App/app/host_vi_i18n.py` (vi), `App/tests/test_dashboard_calendar_browser.py`, `App/tests/test_cleaning_browser.py`. The test run writes `docs/tasks/screenshots-0891/` (new) and rewrites some `docs/tasks/screenshots-0814/*.png`. You write `docs/tasks/0891-report.md`.
Do not touch anything else. Do not bump `?v=` and do not regenerate `App/tests/static_versions.json` (the orchestrator does both). **Never stage or commit** (this overrides executor.md step 5; the orchestrator commits).

## 4. Steps

**Step 1: extract the script** (from the repo root; one command):
`sed -n '/^```python 0891-patch$/,/^```$/p' docs/tasks/0891-calendar-exact-airbnb.md | sed '1d;$d' > /tmp/0891-patch.py && sha256sum /tmp/0891-patch.py`
It must print `d553970d21f4a82249fb4dd4fb9534c34d28185ab11647e9ad2203117cb3c14d`. Any other hash: STOP (§8). Do not open or retype the script.

**Step 2: apply** (repo root): `python3 /tmp/0891-patch.py 2>&1 | tail -30`
Expect 7 lines starting `ok` (host_i18n 2, host_vi_i18n 1, template 3, js 14, css 3, calendar test 3, cleaning test 2). A `STOP 0891` line: nothing was written; STOP (§8).

**Step 3: syntax** (repo root): `node --check App/app/static/dashboard-calendar.js && python3 -m py_compile App/app/host_i18n.py App/app/host_vi_i18n.py App/tests/test_dashboard_calendar_browser.py App/tests/test_cleaning_browser.py && echo SYNTAX-OK 2>&1 | tail -5`

**Step 4: focused run** (from `App/`, timeout 600 s):
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_dashboard_calendar_browser.py tests/test_cleaning_browser.py -k "i18n or 0891 or month_tiles or mouse_drag or 0842" -q --tb=short -rs -x 2>&1 | tail -30`

**Step 5: full run with shots** (§6, both commands).

**Step 6: look once** at each of the 6 shots in `docs/tasks/screenshots-0891/` (`calendar-390.png`, `calendar-768.png`, `calendar-1280.png`, `cleaning-390.png`, `cleaning-768.png`, `cleaning-1280.png`). Compare with `/mnt/project-files/airbnb-calendar-ref/ref-december-pills.png`. Note in the report anything that looks broken (overlaps, cut text, misplaced pills). Do not fix it.

**Step 7: report** (§9).

The patch script (Step 1 extracts this block; do not edit it):

```python 0891-patch
"""0891 patch: Airbnb month calendar. Extracted from docs/tasks/0891-calendar-exact-airbnb.md.
Run from the repo root: python3 /tmp/0891-patch.py
All anchors are checked first; if one is missing or not unique, nothing is written."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
EDITS = {}


def edit(path, old, new):
    EDITS.setdefault(path, []).append((old, new))


def append(path, text):
    EDITS.setdefault(path, []).append((None, text))


P = 'body.v2 #calendar.dashboard-calendar[data-readonly="false"]'
CSS = "App/app/static/dashboard-calendar.css"
JS = "App/app/static/dashboard-calendar.js"
TPL = "App/app/templates/_dashboard_calendar.html"
EN_CS = "App/app/host_i18n.py"
VI = "App/app/host_vi_i18n.py"
T_CAL = "App/tests/test_dashboard_calendar_browser.py"
T_CLEAN = "App/tests/test_cleaning_browser.py"

# ---------- i18n: one new label for the back-to-top button ----------
edit(EN_CS, '        "calendar.today": "Today",\n',
     '        "calendar.today": "Today",\n        "calendar.back_to_top": "Back to top",\n')
edit(EN_CS, '        "calendar.today": "Dnes",\n',
     '        "calendar.today": "Dnes",\n        "calendar.back_to_top": "Zpět nahoru",\n')
edit(VI, '    "calendar.today": "Hôm nay",\n',
     '    "calendar.today": "Hôm nay",\n    "calendar.back_to_top": "Lên đầu trang",\n')

# ---------- template: one head box (sticky at 768 px+) and the back-to-top button ----------
edit(TPL, '  <div class="cal-heading">\n',
     '  <div class="cal-head" data-cal-head>\n  <div class="cal-heading">\n')
edit(TPL, '  </div>\n  <div class="cal-message cal-enhanced" data-cal-message',
     '  </div>\n  </div>\n  <div class="cal-message cal-enhanced" data-cal-message')
edit(TPL, 'tabindex="-1" aria-busy="false" hidden></div>\n',
     'tabindex="-1" aria-busy="false" hidden></div>\n'
     '''  <button type="button" class="cal-to-top" data-cal-top aria-label="{{ t('calendar.back_to_top') }}" title="{{ t('calendar.back_to_top') }}" hidden><svg class="cal-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>\n''')

# ---------- JS ----------
edit(JS, '  const DAY = 86400000;\n',
     '  const DAY = 86400000, MONTHS = 6; // 0891: the Month scale shows MONTHS month sections in one scroll.\n')
edit(JS, '  const weekday = value => new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(dateValue(value));\n',
     '  const monthOnly = value => new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(dateValue(value));\n'
     '  const weekday = value => new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(dateValue(value));\n')
edit(JS, '  let lastLoadedRange = null;\n',
     '  let lastLoadedRange = null, visibleMonth = "";\n')
edit(JS, '    return monthRange(state.date);\n  }\n',
     '    if (tiles()) return [monthRange(state.date)[0], monthRange(moveMonth(state.date, MONTHS - 1))[1]];\n'
     '    return monthRange(state.date);\n  }\n')
edit(JS, '''  function renderCalendar() {
    const [start, end] = range(), weekdays = el("div", "cal-weekdays");
    for (let day = 0; day < 7; day++) weekdays.append(el("span", "", weekday(addDays(start, day))));
    body.append(weekdays);
''', '''  // 0891: Airbnb stay pills. Whole nights, clipped to the week and to the month section. Lane 0 is drawn;
  // a day with more stays gets a "+N" button (data-cal-more) that opens the day list.
  function pillRow(week, until, month) {
    const monthEnd = month ? moveMonth(month, 1) : until;
    const from = month && month > week ? month : week, to = monthEnd < until ? monthEnd : until;
    const overlay = el("div", "cal-pills"), ends = [], hidden = [0, 0, 0, 0, 0, 0, 0];
    state.events.filter(event => event.kind !== "cleaning" && event.start < to && event.end > from)
      .sort((a, b) => a.start.localeCompare(b.start) || b.end.localeCompare(a.end) || String(a.id).localeCompare(String(b.id)))
      .forEach(event => {
        const left = event.start > from ? event.start : from, right = event.end < to ? event.end : to;
        let lane = ends.findIndex(last => last <= left);
        if (lane < 0) lane = ends.length;
        ends[lane] = right;
        const column = distance(week, left), span = distance(left, right);
        if (lane > 0) { for (let index = column; index < column + span; index++) hidden[index]++; return; }
        const pill = el("a", "cal-pill" + (event.start < from ? " continues-start" : "") + (event.end > to ? " continues-end" : ""));
        pill.href = event.url; pill.draggable = false;
        pill.dataset.calEvent = String(event.id); pill.dataset.calFrom = left; pill.dataset.calTo = right;
        pill.style.gridColumn = String(column + 1) + " / span " + String(span);
        const name = labelFor(event);
        pill.title = name + " · " + fullDate(event.start) + " – " + fullDate(event.end);
        pill.setAttribute("aria-label", pill.title); pill.setAttribute("aria-haspopup", "dialog");
        pill.append(el("span", "cal-pill-avatar", (name.trim().charAt(0) || "·").toUpperCase()), el("span", "cal-pill-name", name));
        overlay.append(pill);
      });
    hidden.forEach((count, index) => {
      if (!count) return;
      const date = addDays(week, index), more = el("button", "cal-pill-more", "+" + String(count));
      more.type = "button"; more.dataset.calMore = date; more.style.gridColumn = String(index + 1);
      more.setAttribute("aria-label", fullDate(date) + " · " + format("more", { count }));
      overlay.append(more);
    });
    return overlay;
  }
  function renderCalendar() {
    const [start, end] = range(), weekdays = el("div", "cal-weekdays");
    for (let day = 0; day < 7; day++) weekdays.append(el("span", "", weekday(addDays(start, day))));
    const head = $("[data-cal-head]");
    if (tiles() && head && matchMedia("(min-width:768px)").matches) head.append(weekdays); else body.append(weekdays);
''')
edit(JS, '    for (let week = start; week < end; week = addDays(week, 7)) {\n',
     '''    // 0891: the Month scale is one scroll of MONTHS month sections; outside days are blank cells. Other scales keep one block ("").
    const months = tiles() ? Array.from({ length: MONTHS }, (_, index) => moveMonth(state.date, index)) : [""];
    for (const month of months) {
    let target = body, weekStart = start, weekEnd = end;
    if (month) {
      const section = el("section", "cal-month"); section.dataset.calSection = month;
      section.setAttribute("aria-label", monthName(month));
      section.append(el("h4", "cal-month-title", month.slice(0, 4) === root.dataset.today.slice(0, 4) ? monthOnly(month) : monthName(month)));
      body.append(section); target = section;
      [weekStart, weekEnd] = monthRange(month);
    }
    for (let week = weekStart; week < weekEnd; week = addDays(week, 7)) {
''')
edit(JS, '''        const date = addDays(week, index), day = el("div", "cal-day");
        day.dataset.date = date;
        if (date.slice(0, 7) !== state.date.slice(0, 7) && state.scale !== "week") day.classList.add("is-outside");
''', '''        const date = addDays(week, index), day = el("div", "cal-day");
        if (date.slice(0, 7) !== (month || state.date).slice(0, 7) && state.scale !== "week") day.classList.add("is-outside");
        // 0891: a day outside its month section is a blank cell; the day itself lives in its own section.
        if (month && day.classList.contains("is-outside")) { days.append(day); continue; }
        day.dataset.date = date;
''')
edit(JS, '          if (dayEvents.length > 2) { const more = el("span", "cal-tile-more", "+" + String(dayEvents.length - 2)); more.dataset.calMore = date; chips.append(more); }\n',
     '          // 0891: the stays "+N" is the .cal-pill-more button from pillRow().\n')
edit(JS, '''        const row = el("div", "cal-week is-dots"); row.style.setProperty("--lanes", "1");
        row.append(days); body.append(row);
        continue;
''', '''        const row = el("div", "cal-week is-dots"); row.style.setProperty("--lanes", "1");
        row.append(days);
        if (!hostCleaning) row.append(pillRow(week, until, month));
        target.append(row);
        continue;
''')
edit(JS, '''      row.append(days, overlay); body.append(row);
    }
  }
  function renderYear() {
''', '''      row.append(days, overlay); target.append(row);
    }
    }
  }
  function renderYear() {
''')
edit(JS, '    cancelSelection(); syncControls(); body.replaceChildren();\n',
     '''    cancelSelection(); syncControls(); body.replaceChildren();
    $$("[data-cal-head] > .cal-weekdays").forEach(node => node.remove());
    visibleMonth = "";
    const toTop = $("[data-cal-top]"); if (toTop) toTop.hidden = true;
''')
edit(JS, '''    if (target.closest("[data-cal-today]")) { state.date = root.dataset.today; load(); return; }
    const movement = target.closest("[data-cal-prev], [data-cal-next]");
    if (movement) {
      const sign = movement.hasAttribute("data-cal-prev") ? -1 : 1;
      const next = view() === "calendar" && state.scale === "week" ? addDays(state.date, sign * 7) :
        moveMonth(state.date, sign * (view() === "calendar" && state.scale === "year" ? 12 : 1));
''', '''    if (target.closest("[data-cal-top]")) { window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    if (target.closest("[data-cal-today]")) { if (tiles()) window.scrollTo(0, 0); state.date = root.dataset.today; load(); return; }
    const movement = target.closest("[data-cal-prev], [data-cal-next]");
    if (movement) {
      const sign = movement.hasAttribute("data-cal-prev") ? -1 : 1;
      // 0891: in the Month scroll the arrows step from the month shown in the sticky title.
      const base = tiles() && visibleMonth ? visibleMonth : state.date;
      visibleMonth = "";
      if (tiles()) window.scrollTo(0, 0);
      const next = view() === "calendar" && state.scale === "week" ? addDays(state.date, sign * 7) :
        moveMonth(base, sign * (view() === "calendar" && state.scale === "year" ? 12 : 1));
''')
edit(JS, '    popstate: () => {\n', '''    scroll: () => {
      // 0891: the title follows the month section under the sticky head; the back-to-top button shows after 400 px.
      if (!document.querySelector("[data-calendar]") || state.loading || !tiles()) return;
      const head = $("[data-cal-head]");
      const line = head && getComputedStyle(head).position === "sticky" ? head.getBoundingClientRect().bottom + 1 : 1;
      let current = "";
      $$(".cal-month").forEach(section => { if (section.getBoundingClientRect().top <= line) current = section.dataset.calSection; });
      visibleMonth = current;
      $("[data-cal-period]").textContent = monthName(current || state.date);
      const toTop = $("[data-cal-top]");
      if (toTop) toTop.hidden = window.scrollY < 400;
    },
    popstate: () => {
''')
edit(JS, '    window.addEventListener("popstate", () => window._ubyCalendarHandlers.popstate());\n',
     '    window.addEventListener("popstate", () => window._ubyCalendarHandlers.popstate());\n'
     '    window.addEventListener("scroll", () => window._ubyCalendarHandlers.scroll(), { passive: true });\n')

# ---------- CSS: retire the 0832 grid and 0842 flex head layouts (moved to .cal-head below) ----------
edit(CSS, '''  .dashboard-calendar[data-readonly="false"] { display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:12px; }
  .dashboard-calendar[data-readonly="false"] > .cal-heading:not([hidden]), .dashboard-calendar[data-readonly="false"] > .cal-toolbar:not([hidden]) { display:contents; }
  .dashboard-calendar[data-readonly="false"] > .cal-message, .dashboard-calendar[data-readonly="false"] > .cal-body { grid-column:1 / -1; }
  .dashboard-calendar[data-readonly="false"] .cal-heading-actions:not([hidden]) { grid-column:1 / 3; grid-row:2; justify-self:end; display:flex; align-items:center; gap:12px; }
  .dashboard-calendar[data-readonly="false"] .cal-toolbar-options { grid-column:3; grid-row:2; display:flex; align-items:center; gap:12px; }
  .dashboard-calendar[data-readonly="false"] .cal-toolbar .cal-navigation { grid-column:2 / 4; grid-row:1; justify-self:end; }
  .dashboard-calendar[data-readonly="false"] .cal-toolbar h3 { grid-column:1; grid-row:1; flex:none; min-width:0; white-space:nowrap; overflow:visible; text-overflow:clip; }
''', '''  /* 0891: the 0832 two-row grid head moved to the .cal-head flex row in the 0891 block. */
''')
edit(CSS, '''  body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] { display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:12px; }
  body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] > :is(.cal-message, .cal-body) { order:5; flex:1 1 100%; min-width:0; }
  body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] .cal-toolbar h3[data-cal-period] { order:1; flex:0 1 auto; min-width:0; margin:0 auto 0 0; text-align:left; font-size:24px; line-height:32px; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] .cal-toolbar .cal-navigation { order:2; display:flex; flex:0 0 auto; gap:12px; }
  body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] .cal-heading-actions:not([hidden]) { order:3; display:flex; flex:0 0 auto; flex-wrap:nowrap; gap:12px; margin:0; }
  body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] .cal-toolbar-options { order:4; display:flex; flex:0 0 auto; gap:12px; }
''', '''  /* 0891: the 0842 one-row head now lives on .cal-head for both pages (0891 block). */
''')
append(CSS, f'''
/* 0891: Airbnb month calendar on the host calendar (/?cal_view=calendar) and the host cleaning page (/cleaning). Month scale = one scroll of .cal-month sections (JS); separate rounded tiles, 12 px apart at 768 px+ (4 px on phone); past days grey with a struck number; today a coral disc; stays are dark pills over the tiles (host only; the cleaning page keeps its amber cleaning tags); at 768 px+ one sticky head row (title left, controls right) with the weekday row under it; a floating back-to-top button. Weeks still start on Monday. The (1,4,1) prefix beats app2.css and the earlier tile rules (briefs 0873, 0875, 0877). */
{P} .cal-month + .cal-month {{ margin-top:32px; }}
{P} .cal-month-title {{ margin:0 0 12px; font-size:20px; line-height:28px; font-weight:700; color:#222; }}
{P} .cal-month-title::first-letter {{ text-transform:uppercase; }}
{P} .cal-week.is-dots {{ position:relative; isolation:isolate; border:0; background:transparent; }}
{P} .cal-week.is-dots + .cal-week.is-dots {{ margin-top:4px; }}
{P} .cal-week.is-dots .cal-day:not(.is-outside) {{ background:#fff; border:1px solid #dddddd; }}
{P} .cal-week.is-dots .cal-day.is-past {{ background:#ebebeb; border-color:#ebebeb; }}
{P} .cal-week.is-dots .cal-day.is-past .cal-num {{ color:#6a6a6a; text-decoration:line-through; }}
{P} .cal-week.is-dots .cal-day.is-selected {{ background:#222; border-color:#222; box-shadow:none; outline:none; }}
{P} .cal-week.is-dots .cal-day.is-selected .cal-num {{ color:#fff; text-decoration:none; }}
{P}[data-cleaning="false"] :is(.cal-tile-chips, .cal-dots) {{ display:none; }}
{P} .cal-pills {{ position:absolute; inset:0; z-index:1; display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); grid-template-rows:minmax(0,1fr); column-gap:4px; pointer-events:none; }}
{P} .cal-pill {{ grid-row:1; align-self:end; display:flex; align-items:center; gap:6px; min-width:0; height:18px; margin:0 0 6px 3px; padding:0 6px; box-sizing:border-box; border-radius:9px; background:#222; color:#fff; font-size:10px; line-height:18px; font-weight:600; text-decoration:none; white-space:nowrap; overflow:hidden; pointer-events:auto; cursor:pointer; }}
{P} .cal-pill:hover {{ background:#000; color:#fff; }}
{P} .cal-pill.continues-start {{ margin-left:0; border-top-left-radius:0; border-bottom-left-radius:0; }}
{P} .cal-pill.continues-end {{ border-top-right-radius:0; border-bottom-right-radius:0; }}
{P} .cal-pill-avatar {{ display:none; }}
{P} .cal-pill-name {{ min-width:0; overflow:hidden; text-overflow:ellipsis; }}
{P} .cal-pill-more {{ display:none; }}
{P} .cal-to-top {{ position:fixed; right:16px; bottom:calc(var(--tabbar-h, 84px) + var(--tabbar-safe, 0px) + 76px); z-index:7; display:inline-flex; align-items:center; justify-content:center; box-sizing:border-box; width:44px; height:44px; min-width:44px; min-height:44px; padding:0; border:1px solid #dddddd; border-radius:50%; background:#fff; color:#222; box-shadow:0 6px 16px rgba(0,0,0,.12); cursor:pointer; }}
{P} .cal-to-top .cal-icon {{ width:20px; height:20px; }}
{P}.has-panel .cal-to-top {{ display:none; }}
@media (min-width:768px) {{
  {P} .cal-head {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:12px; margin:0 0 16px; padding:12px 0 0; background:var(--bg, #f6f6f4); }}
  {P}:has(.cal-month) .cal-head {{ position:sticky; top:var(--app-header-h, 0px); z-index:6; }}
  {P} .cal-head > :is(.cal-heading, .cal-toolbar):not([hidden]) {{ display:contents; }}
  {P} .cal-head .cal-toolbar h3[data-cal-period] {{ order:1; flex:0 0 auto; min-width:0; margin:0 auto 0 0; text-align:left; font-size:24px; line-height:32px; font-weight:700; letter-spacing:-0.02em; color:#222; white-space:nowrap; overflow:visible; }}
  {P} .cal-head .cal-toolbar .cal-navigation {{ order:2; display:flex; flex:0 0 auto; gap:12px; }}
  {P} .cal-head .cal-heading-actions:not([hidden]) {{ order:3; display:flex; flex:0 0 auto; flex-wrap:nowrap; align-items:center; gap:12px; margin:0; }}
  {P} .cal-head .cal-toolbar-options {{ order:4; display:flex; flex:0 0 auto; align-items:center; gap:12px; }}
  {P} .cal-head .cal-segment {{ height:40px; min-height:40px; box-sizing:border-box; padding:3px; border:0; border-radius:20px; background:#f2f2f0; }}
  {P} .cal-head .cal-segment button {{ height:34px; min-height:34px; min-width:0; padding:0 14px; border-radius:17px; font-size:14px; font-weight:600; }}
  {P} .cal-head .cal-view-segment button {{ position:relative; width:34px; min-width:34px; padding:0; }}
  {P} .cal-head .cal-view-segment button span {{ position:absolute; width:1px; height:1px; margin:-1px; padding:0; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }}
  {P} .cal-head select {{ height:40px; min-height:40px; box-sizing:border-box; padding:0 12px; border:0; border-radius:20px; background-color:#f2f2f0; color:#222; font-size:14px; font-weight:600; }}
  {P} .cal-head .cal-settings {{ width:40px; min-width:40px; height:40px; min-height:40px; padding:0; border:0; border-radius:50%; }}
  {P} .cal-head > .cal-weekdays {{ order:9; flex:1 1 100%; position:static; display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:12px; margin:0; padding:4px 0 8px; border:0; border-bottom:1px solid #dddddd; background:transparent; }}
  {P} .cal-head > .cal-weekdays span {{ padding:0; text-align:center; font-size:12px; line-height:16px; font-weight:400; text-transform:none; color:#6a6a6a; }}
  {P} .cal-month + .cal-month {{ margin-top:48px; }}
  {P} .cal-month-title {{ margin:0 0 20px; font-size:26px; line-height:32px; letter-spacing:-0.02em; }}
  {P} .cal-week.is-dots .cal-week-days {{ gap:12px; }}
  {P} .cal-week.is-dots + .cal-week.is-dots {{ margin-top:12px; }}
  {P} .cal-week.is-dots .cal-day {{ min-height:94px; border-radius:14px; }}
  {P} .cal-week.is-dots .cal-day-number {{ padding:12px; font-size:16px; line-height:20px; font-weight:600; color:#222; }}
  {P} .cal-week.is-dots .cal-day-number .cal-num {{ font-size:16px; }}
  {P} .cal-pills {{ column-gap:12px; }}
  {P} .cal-pill {{ height:32px; margin:0 0 12px 8px; padding:0 12px 0 4px; gap:8px; border-radius:16px; font-size:13px; line-height:16px; box-shadow:0 1px 2px rgba(0,0,0,.12); }}
  {P} .cal-pill.continues-start {{ margin-left:0; padding-left:12px; }}
  {P} .cal-pill-avatar {{ display:inline-flex; flex:0 0 24px; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:#6a6a6a; color:#fff; font-size:12px; line-height:24px; font-weight:700; }}
  {P} .cal-pill.continues-start .cal-pill-avatar {{ display:none; }}
  {P} .cal-pill-more {{ grid-row:1; align-self:start; justify-self:end; display:inline-flex; align-items:center; height:24px; min-height:24px; min-width:0; margin:10px 10px 0 0; padding:0 8px; border:0; border-radius:12px; background:#222; color:#fff; font:inherit; font-size:12px; line-height:24px; font-weight:600; cursor:pointer; pointer-events:auto; }}
  {P} .cal-tile-chip.cal-clean-chip {{ height:24px; line-height:24px; padding:0 8px; border-radius:12px; font-weight:600; }}
  {P} .cal-to-top {{ right:24px; bottom:96px; width:48px; height:48px; }}
}}
@media (min-width:1024px) {{
  {P} .cal-head .cal-toolbar h3[data-cal-period] {{ font-size:32px; line-height:40px; }}
}}
''')

# ---------- existing tests that change with the new look ----------
edit(T_CAL, '        assert min(heights) >= 96, heights\n',
     '        assert min(heights) >= 93, heights  # 0891: Airbnb tiles are 94 px\n')
edit(T_CAL, '''        if width == 768:
            chip_sizes = page.locator(".cal-tile-chip").evaluate_all("nodes => nodes.filter(node => node.offsetParent).map(node => getComputedStyle(node).fontSize)")
            assert chip_sizes and all(size == "0px" for size in chip_sizes), chip_sizes
''', '''        if width == 768:
            # 0891: stays are dark pills over the tiles; the per-day chips are hidden.
            assert page.locator(".cal-pill").count() >= 1
            assert page.locator(".cal-tile-chip:visible").count() == 0
''')
edit(T_CLEAN, '        assert title == ["24px", "700"], title\n',
     '        assert title == ["32px", "700"], title  # 0891: Airbnb title size at 1024 px+\n')

# ---------- new tests ----------
append(T_CAL, '''

# 0891: Airbnb month calendar: one scroll of month sections, rounded tiles, dark stay pills, sticky head, back-to-top.
SHOTS_0891 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0891"
ROWS_0891 = """() => [...document.querySelectorAll('.cal-month .cal-week.is-dots')].map(row => ({
    s: [...document.querySelectorAll('.cal-month')].indexOf(row.closest('.cal-month')),
    t: [...row.querySelectorAll('.cal-day[data-date]')].map(tile => { const r = tile.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })
})).filter(row => row.t.length)"""
PILLS_0891 = """() => [...document.querySelectorAll('.cal-pill')].map(pill => {
    const r = pill.getBoundingClientRect(), all = [...pill.closest('.cal-week').querySelectorAll('.cal-day[data-date]')];
    const nights = all.filter(t => t.dataset.date >= pill.dataset.calFrom && t.dataset.date < pill.dataset.calTo).map(t => t.getBoundingClientRect());
    const covered = all.filter(t => { const b = t.getBoundingClientRect(), mid = b.left + b.width / 2; return mid > r.left && mid < r.right; }).length;
    const want = Math.round((Date.parse(pill.dataset.calTo) - Date.parse(pill.dataset.calFrom)) / 86400000);
    return {want, nights: nights.length, covered, left: r.left - nights[0].left, right: nights[nights.length - 1].right - r.right,
            top: r.top - nights[0].top, bottom: nights[0].bottom - r.bottom, half: nights[0].height / 2,
            color: getComputedStyle(pill).backgroundColor, cut: pill.classList.contains('continues-start')};
})"""
FITS_0891 = "document.documentElement.scrollWidth <= innerWidth + 1"


def save_0891_shot(page, name):
    if os.environ.get("UBYHOST_TASK_SHOTS") != "1":
        return
    SHOTS_0891.mkdir(parents=True, exist_ok=True)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS_0891 / name), full_page=False)


def check_tiles_0891(rows, width, tile_height=None):
    gap = 12 if width >= 768 else 4
    assert rows, "no month tiles"
    for row in rows:
        for a, b in zip(row["t"], row["t"][1:]):
            assert abs(b[0] - a[1] - gap) <= 1, ("column gap", width, a, b)
        if tile_height:
            assert all(abs(t[3] - t[2] - tile_height) <= 1 for t in row["t"]), ("tile height", width, row)
    for upper, lower in zip(rows, rows[1:]):
        if upper["s"] == lower["s"]:
            assert abs(lower["t"][0][2] - upper["t"][0][3] - gap) <= 1, ("row gap", width, upper, lower)


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_0891_airbnb_month_tiles_and_pills(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        sections = page.locator(".cal-month").evaluate_all("nodes => nodes.map(node => [node.dataset.calSection, node.getAttribute('aria-label')])")
        assert [s[0] for s in sections] == ["2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", "2027-03-01"], sections
        assert sections[0][1] == "October 2026", sections
        assert page.locator('.cal-day[data-date="2026-10-31"]').count() == 1
        assert page.locator('.cal-day[data-date="2026-11-01"]').count() == 1
        check_tiles_0891(page.evaluate(ROWS_0891), width, 94 if width >= 768 else None)
        pills = page.evaluate(PILLS_0891)
        assert pills, "no stay pills"
        inset = 8 if width >= 768 else 3
        for pill in pills:
            assert pill["want"] == pill["nights"] == pill["covered"], pill
            assert abs(pill["left"] - (0 if pill["cut"] else inset)) <= 1, pill
            assert abs(pill["right"]) <= 1, pill
            assert pill["top"] >= pill["half"] and pill["bottom"] >= 0, pill
            assert pill["color"] == "rgb(34, 34, 34)", pill
        assert page.locator(".cal-tile-chip:visible, .cal-dots:visible, .cal-week-events").count() == 0
        if width >= 768:
            assert page.locator('[data-cal-more="2026-10-14"]').is_visible()
            weekdays = page.locator("[data-cal-head] > .cal-weekdays span").all_inner_texts()
            assert len(weekdays) == 7 and weekdays[0] == "Mon", weekdays
        assert page.evaluate(FITS_0891)
        save_0891_shot(page, f"calendar-{width}.png")
        context.close()
        browser.close()


def test_0891_sticky_head_title_follows_scroll_and_back_to_top(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        top = page.locator("[data-cal-top]")
        assert top.is_hidden()
        assert page.locator("[data-cal-period]").inner_text() == "October 2026"
        page.mouse.move(640, 700)
        page.mouse.wheel(0, 1800)
        page.wait_for_function("scrollY > 1000")
        page.wait_for_timeout(300)
        head = page.locator("[data-cal-head]").bounding_box()
        assert abs(head["y"]) <= 1, head
        assert page.locator("[data-cal-head] > .cal-weekdays").is_visible()
        title = page.locator("[data-cal-period]").inner_text()
        assert title in ("November 2026", "December 2026", "January 2027"), title
        assert top.is_visible()
        box = top.bounding_box()
        assert abs(box["width"] - 48) <= 1 and box["x"] + box["width"] <= 1280 - 23, box
        page.locator("[data-cal-next]").click()
        wait_loaded(page)
        expected = {"November 2026": "2026-12-01", "December 2026": "2027-01-01", "January 2027": "2027-02-01"}[title]
        assert page.locator(".cal-month").first.get_attribute("data-cal-section") == expected
        page.mouse.move(640, 700)
        page.mouse.wheel(0, 1800)
        page.wait_for_function("scrollY > 1000")
        page.wait_for_timeout(300)
        top.click()
        page.wait_for_function("scrollY === 0")
        assert page.locator("[data-cal-head]").bounding_box()["y"] >= 0
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440])
def test_0891_calendar_no_horizontal_overflow(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        assert page.evaluate(FITS_0891), (width, "top")
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(300)
        assert page.evaluate(FITS_0891), (width, "bottom")
        context.close()
        browser.close()
''')
append(T_CLEAN, '''

# 0891: the host cleaning page uses the Airbnb month scroll with amber cleaning tags and no stay pills.
SHOTS_0891 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0891"
ROWS_0891 = """() => [...document.querySelectorAll('.cal-month .cal-week.is-dots')].map(row => ({
    s: [...document.querySelectorAll('.cal-month')].indexOf(row.closest('.cal-month')),
    t: [...row.querySelectorAll('.cal-day[data-date]')].map(tile => { const r = tile.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })
})).filter(row => row.t.length)"""


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_0891_cleaning_airbnb_month(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        page.wait_for_selector(".cal-month")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        assert page.locator(".cal-month").count() == 6
        assert page.locator(".cal-pill").count() == 0
        assert page.locator(".cal-day.has-cleaning").count() >= 1
        gap = 12 if width >= 768 else 4
        rows = page.evaluate(ROWS_0891)
        assert rows
        for row in rows:
            for a, b in zip(row["t"], row["t"][1:]):
                assert abs(b[0] - a[1] - gap) <= 1, (width, a, b)
        if width >= 768:
            chip = page.locator(".cal-day.has-cleaning .cal-tile-chip.cal-clean-chip").first
            assert chip.is_visible()
            assert chip.evaluate("node => getComputedStyle(node).borderTopLeftRadius") == "12px"
        else:
            assert page.locator(".cal-day.has-cleaning .cal-clean-tag").first.is_visible()
        assert page.evaluate(FITS)
        if os.environ.get("UBYHOST_TASK_SHOTS") == "1":
            SHOTS_0891.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS_0891 / f"cleaning-{width}.png"), full_page=False)
        context.close()
        browser.close()
''')

# ---------- apply: check every anchor first, then write ----------
css_now = (ROOT / CSS).read_text(encoding="utf-8")
if "/* 0891:" in css_now:
    sys.exit("STOP 0891: the patch is already applied (dashboard-calendar.css has a 0891 block). Nothing written.")
texts = {}
for path, pairs in EDITS.items():
    text = (ROOT / path).read_text(encoding="utf-8")
    for old, new in pairs:
        if old is None:
            text = text.rstrip("\n") + "\n" + new
            continue
        count = text.count(old)
        if count != 1:
            sys.exit(f"STOP 0891: {path}: anchor found {count} times, nothing written: {old.splitlines()[0][:90]!r}")
        text = text.replace(old, new)
    texts[path] = text
for path, text in texts.items():
    (ROOT / path).write_text(text, encoding="utf-8")
    print("ok", path, len(EDITS[path]), "changes")
```

## 5. Do not touch

The shared read-only cleaner page (`data-readonly="true"`), Week, Year and Gantt views (they must look as before), the phone header layout, the stay create form, fee and invoice code, `app2.css`, `cleaning.css`, server code. Do not "fix" anything you notice; put it under Questions.

## 6. Commands

From `App/`, timeout 600 s each:
1. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1 .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py -q --tb=short -rs 2>&1 | tail -30`
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py -q --tb=short -rs 2>&1 | tail -30`

A failing test: rerun only that test once (flake check). It fails again: do not edit code or tests (this overrides executor.md "fix it once"); STOP and put the assertion and the last 30 lines in the report.

## 7. Acceptance

- [ ] Step 1 hash matches; step 2 prints 7 `ok` lines; step 3 prints `SYNTAX-OK`.
- [ ] Both §6 commands pass, 0 skipped.
- [ ] The 6 shots exist in `docs/tasks/screenshots-0891/`: month heading, rounded separate tiles, grey struck past days, dark pills over the tiles on `calendar-*`, amber tags and no pills on `cleaning-*`, one head row at 1280 with the weekday row under it.
- [ ] `git status --short` shows only the 7 §3 files, `docs/tasks/screenshots-0891/`, changed `docs/tasks/screenshots-0814/*.png` and `docs/tasks/0891-report.md`. Nothing staged.

## 8. Stop and ask

Step 1 hash differs. Step 2 prints `STOP 0891` (the files changed since this brief; the orchestrator re-bases the script). Step 3 fails. A test fails twice (§6). A fix would need any edit outside the script. At 25 tool calls: write the report with `Status: blocked` and the step you reached.

## 9. Report

`docs/tasks/0891-report.md`, 600 tokens at most: the step 2 output, the last 5 lines of each §6 command, §7 ticked, one line per shot (looks right / what is wrong), Deviations, Questions. Owner steps: none; the orchestrator bumps `?v=` for `dashboard-calendar.css` and `.js` in `_dashboard_calendar.html` (lines 2 and the last line), regenerates `App/tests/static_versions.json`, commits, and tells Josef the "kept on purpose" list from §2. Set this brief to `Status: review` (or `blocked`). No PR.
