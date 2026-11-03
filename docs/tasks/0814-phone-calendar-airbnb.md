# 0814: Calendar like Airbnb (full-page day tiles, touch range select, bottom sheet)

Status: todo
Depends on: none | Base commit: origin/main | Branch: claude/project-thread-vnnr9p
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef (2026-11-02): the host calendar (`/?cal_view=calendar`) must look and work like the Airbnb host calendar, as a full page. Today on phone:
- it sits inside a card titled "Reservations" with a select, 7-column cells with tiny dots;
- dragging across nights does nothing on touch (`pointerdown` returns early for `pointerType === "touch"`);
- tapping a day opens a centred modal "Stays on 5 November 2026" whose title wraps over 3 lines next to a huge red full-width × button;
- a grey hint line "Drag across nights to add a stay…" sits under the grid (fine print, banned).

Target on phone (≤767 px, host calendar, not the cleaning page): Airbnb pattern in Ubyhost style (Manrope, ink `#222`, coral only for today and the one primary button, no money anywhere, no prices).

## 2. Context: design (phone, `phoneDots()` true)

1. **Full page.** `.dashboard-calendar` loses its card look: no border, no background card, no shadow, padding 0 left/right (the page gutter stays). Hide `#calendar-title` (the page h1 already says "Calendar"). Property select: full width, 44 px tall, 12 px radius. Under it the toolbar: month title (`[data-cal-period]`, 20 px, 700) on the left, prev/next as 40 px round icon buttons on the right; hide the Today button on phone. The weekday row is `position:sticky; top:0` with a white background.
2. **Day tiles.** Each `.cal-day` in an `.is-dots` week is a tile: grid gap 6 px between tiles (columns and rows), tile radius 12 px, `1px solid var(--cal-line)`, min-height 64 px, day number centred at top (15 px, 600), status marks centred below. Keep `.cal-dots` and `.cal-dot` (tests use them) but restyle `.cal-dot` as a bar 14 px wide, 4 px tall, radius 2 px, colour from `data-cal-color` as now; `.cal-dots` centred, gap 3 px.
   - booked day (`.has-stays`): background `#f2f2f0`, border transparent (Airbnb's grey blocked tile);
   - outside the month (`.is-outside`): `visibility:hidden` (Airbnb shows only the month's days);
   - past days (date < `data-today`): add class `is-past` in `renderCalendar`; number colour `var(--ink-muted)`, number struck through (`text-decoration:line-through`) only if also `.has-stays`? No: keep it simple, past = muted number only;
   - today: number inside a 28 px coral circle, white text;
   - selected (`.is-selected`): background `#222`, border `#222`, number and bars white (`.cal-dot` gets `background:#fff`). Selection must override `.has-stays`.
   The `.cal-day-number` button fills the whole tile (it is the tap target, ≥44 px).
3. **Selecting on touch.** Replace the phone tap and drag behaviour (phone only; mouse drag on desktop stays exactly as now):
   - Tap a day with no selection, or when the current selection already spans 2+ days, or on a day before the current single selected day: selection = that one day; open the sheet.
   - Tap a day after the current single selected day: selection = anchor..that day; update the sheet.
   - Tap the selected single day again: clear selection, close the sheet.
   - Long press (300 ms without moving more than 8 px) then drag: selection follows the finger (use `document.elementFromPoint` like the mouse code). Implement with `touchstart`/`touchmove`/`touchend` on `body` (`[data-cal-body]`); register `touchmove` with `{ passive:false }` and call `preventDefault()` only while a long-press drag is active, so normal scrolling still works. On `touchend` after a drag, keep the selection and open the sheet. Set `suppressClickUntil = Date.now() + 400` so the synthetic click does not undo it. Add `-webkit-user-select:none; -webkit-touch-callout:none` on the tiles.
   - The `pointerdown` early return for touch stays (pointer code is the desktop mouse path). In the `click` handler, the `if (phoneDots()) { openDay(...) }` branch calls the new `phoneTap(date)` instead.
   - `cancelSelection()` must not run on `lostpointercapture` for touch selections (check that `selection.pointerId` is set before cancelling there).
4. **Bottom sheet** = the existing `[data-cal-day-dialog]`, opened with `dialog.show()` (NOT `showModal`) on phone so the grid stays tappable, via a new `openSheet()` that replaces `openDay()` on phone (desktop `openDay` unchanged, still `show()` helper = modal). On phone, CSS (scoped `@media (max-width:767px)` and `.dashboard-calendar[data-cleaning="false"]`):
   - `position:fixed; left:0; right:0; bottom:calc(64px + env(safe-area-inset-bottom)); top:auto; margin:0; width:100%; max-width:none; max-height:55dvh; overflow:auto; border:0; border-radius:20px 20px 0 0; padding:16px 16px 24px; box-shadow:0 -8px 24px rgba(0,0,0,.12)` (64 px = phone tab bar; check `_shell_tabbar.html` for its real height and use that).
   - Heading row: title is a pill (`#222` background, white text, 40 px tall, radius 20 px, padding 0 16px, 15 px 600, `white-space:nowrap`) showing the range, e.g. `5 – 8 Nov` (use `shortDate(start)` and `shortDate(addDays(end,1))` for a range = check-out day; one day shows just `shortDate(start)`). Close button: 40 px round, background `#f2f2f0`, ink ×, no coral, no border. Pill and × on one line, 12 px gap, centred vertically.
   - Body: the stays overlapping the selected range (same `eventLink(event)` list as `openDay`, using `displayOverlap(event, start, addDays(end,1))`), then the `[data-cal-day-add]` button full width, 48 px, primary coral, label `labels.add_stay`. 12 px between list items and before the button. When no stays: no "none" text (no fine print), just the button.
   - `[data-cal-day-add]` opens `openCreate(selection start, addDays(selection end,1), state.property, "stay", button)`; the sheet closes first.
   - Closing the sheet (× or Escape) clears the selection.
   - Keep `#cal-day-title` as the pill element so `aria-labelledby` still works.
5. **All calendar dialogs on phone** (`.cal-dialog`, includes create and details): bottom sheet style as in 4 (but these stay modal via `showModal`, so `bottom:0`, padding-bottom `calc(24px + env(safe-area-inset-bottom))`). Title 18 px, one line, `overflow:hidden; text-overflow:ellipsis; white-space:nowrap`. The × is the same 40 px round neutral button everywhere (also on desktop: replace the coral/large look; `.cal-dialog .cal-close` gets `width:40px; height:40px; min-width:40px; min-height:40px; border-radius:50%; background:#f2f2f0; color:var(--ink); border:0; font-size:20px; margin:0`). Find what makes it coral and full width on phone (likely a phone `.btn` rule in the shared phone classes) and override it with a more specific `.dashboard-calendar .cal-dialog .cal-close` selector; do not edit the shared phone classes.
6. **Hint.** `#cal-hint` gets class `sr-only` (visually hidden on every width; it stays the `aria-describedby` target). No other text added.

Desktop (≥768 px): only items 5 (close button) and 6 change, plus the selected-range colour: `.cal-day.is-selected, .cal-gantt-slot.is-selected` become `background:#222` with white text, no coral ring. Bars/gantt untouched.

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/dashboard-calendar.js` | edit (phone tap, touch drag, sheet, `is-past`) |
| `App/app/static/dashboard-calendar.css` | edit (append one `/* 0814 */` block at the end; delete rules it replaces in the old `.is-dots` block) |
| `App/app/templates/_dashboard_calendar.html` | `sr-only` on the hint; bump `?v=` on the css and js links to `20261102-0814` |
| `App/tests/static_versions.json` | regenerate with `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_dashboard_phone_browser.py` | add tests (section 6) |
| existing calendar browser tests | update only assertions that check the old phone modal (e.g. tap expects modal → now non-modal sheet still `is_visible()`) |
| `docs/tasks/screenshots-0814/` | 390 px and 1280 px PNGs |
| `docs/tasks/0814-report.md` | create |

No other file. No new dependency. No new i18n key (reuse `add_stay`, `close`).

## 4. Steps

1. Read `dashboard-calendar.js` lines 276-320 (`renderCalendar` dots part), 501-530, 582-590 (`openDay`), 634-760 (create, selection, pointer, click handlers). Read CSS lines 80-100 and 555-583. Read `_shell_tabbar.html` for the tab bar height.
2. JS changes per section 2. Keep functions short; no dead code (remove the phone branch in `pointerup` that called `openDay`, since touch never reaches it).
3. CSS per section 2.
4. Template, version bump, static_versions.
5. Tests, screenshots, report.

## 5. Do not touch

Cleaning page calendar (`data-cleaning="true"`) must look and behave as before: scope every phone rule with `.dashboard-calendar[data-cleaning="false"]` and every JS change with `phoneDots()` (already false in cleaning mode). Gantt, year view, desktop mouse drag, the create form fields and its POST.

## 6. Commands and tests

In `test_dashboard_phone_browser.py`, using the existing fixtures (`calendar_workspace`, `open_page`, `launch`, viewport 390×844, `has_touch=True`, `is_mobile=True` for the touch tests):
- `test_phone_calendar_tiles_and_sheet`: open `/?cal_view=calendar`; tiles ≥44 px tall and wide; gap between neighbouring tiles ≥4 px; `#calendar-title` not visible; `#cal-hint` has zero size or is clipped (sr-only). Tap day 10 → `[data-cal-day-dialog]` visible, `open` attribute set, `document.querySelector('dialog:modal')` is null; tapped tile has `is-selected` and computed background `rgb(34, 34, 34)`. Tap day 12 → tiles 10, 11, 12 selected, pill text contains "13" (check-out day). Sheet: pill and × top centres within 2 px; × is 40×40 and not coral (background not `rgb(208, 69, 45)`); gap pill→× ≥12 px; sheet bottom ≤ tab bar top; Add button ≥44 px tall, ≥24 px from sheet bottom; text inside sheet ≥16 px from its left/right edges. Tap Add → create dialog open with `date_from` = day 10 and `date_to` = day 13.
- `test_phone_calendar_long_press_drag`: with CDP touch events (`page.context.new_cdp_session(page)`, `Input.dispatchTouchEvent` touchStart on day 3 centre, wait 400 ms, touchMove to day 5 centre in 3 steps, touchEnd): days 3-5 selected, sheet visible. A quick swipe (touchStart, immediate touchMove 200 px up, touchEnd) selects nothing.
- Repeat the tiles test at 320 px width (no horizontal overflow: `document.documentElement.scrollWidth <= 320`).
- Save screenshots (`shot()` helper or `page.screenshot`) to `docs/tasks/screenshots-0814/`: `calendar-390.png` (no selection), `calendar-range-390.png` (range + sheet), `calendar-create-390.png` (create sheet), `calendar-1280.png`, `calendar-dialog-1280.png` (day click → create dialog, shows the new ×).

Run (from `App/`): `.venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_cleaning_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, with `UBYHOST_REQUIRE_BROWSER=1` so nothing is skipped. All pass, 0 skipped.

## 7. Acceptance

- [ ] Section 6 tests pass, 0 skipped; old calendar/cleaning tests pass (only phone-modal assertions adjusted, listed in the report).
- [ ] Five screenshots exist.
- [ ] `python3 scripts/context_lint.py` (repo root) clean.
- [ ] Only section 3 files changed.

## 8. Stop and ask

A cleaning-page test fails twice; the tab bar height cannot be found; the × colour comes from a rule you cannot override without editing shared phone classes; 25 tool calls without green tests.

## 9. Report

`docs/tasks/0814-report.md`: files, test command last lines, assertions changed in old tests and why, deviations.
