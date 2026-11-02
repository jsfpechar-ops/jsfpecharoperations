# 0816: Airbnb calendar on tablet and desktop too

Status: done
Depends on: 0814 (same branch, committed first) | Branch: claude/project-thread-vnnr9p
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef (2026-11-02 15:25Z): "Apply this airbnb to everywhere even on desktop and tablet." 0814 built the Airbnb-style calendar on phone only (≤767 px): full page, day tiles, tap / long-press range select, ink selection, non-modal bottom sheet, round neutral ×. This brief brings the same look and behaviour to the host calendar month view at ≥768 px (tablet 768-1023, desktop ≥1024). Read `docs/tasks/0814-phone-calendar-airbnb.md` section 2 and the 0814 diff (`git log --oneline -3`, then `git show <0814 commit> -- App/app/static/dashboard-calendar.js App/app/static/dashboard-calendar.css`) first.

## 2. Context: design (host calendar, `data-cleaning="false"`, month scale)

1. **One tile renderer for all widths.** Introduce `function tiles() { return !cleaningMode && view() === "calendar" && state.scale === "month"; }` and use it where 0814 uses `phoneDots()` for rendering tiles and for the tap / sheet logic. `phoneDots()` keeps only its phone-only jobs (forcing calendar view, hiding toolbar controls). Week and year scales and the gantt view stay as they are on desktop (the view and scale buttons remain at ≥768 px).
2. **Full page at every width:** no card border, background or shadow around `.dashboard-calendar`; `#calendar-title` hidden; toolbar = month title (24 px, 700) left, prev / Today / next and the view controls right, all 40 px tall, 12 px gaps. Weekday row sticky, white.
3. **Tiles ≥768 px:** gap 8 px, radius 12 px, `1px solid var(--cal-line)`; min-height 96 px (tablet) and 112 px (≥1024 px); day number top-left 15 px 600 with 12 px inset. Below it up to 2 stay chips: 22 px tall, radius 6 px, background `#f2f2f0`, 3 px left border in the property colour (`propertyColor`, same palette as the bars), text = `labelFor(event)` 12 px, one line, ellipsis; then `+n` (`cal-dot-more`) if more. Chips are `pointer-events:none` (the whole tile is the tap target; stays open from the panel). Keep `.cal-dots` / `.cal-dot` in the DOM (tests use them) but hide `.cal-dots` at ≥768 px. Booked day = `has-stays` grey fill as on phone; today = coral circle; past = muted; outside month = hidden; selected = `#222` tile, white number, chips white text on `rgba(255,255,255,.14)`.
4. **Selection at ≥768 px:** mouse: click = 0814 tap rules (single day, then later day = range); mouse drag across tiles (existing pointer code) also selects a range and, on release, opens the panel (not the create dialog). Touch on tablets uses 0814's tap / long-press code unchanged. Keyboard: Shift+arrows extends, Enter opens the panel for the selection (not the create dialog directly).
5. **Side panel ≥768 px** = the same `[data-cal-day-dialog]` sheet, opened non-modal with `show()`, styled as Airbnb's right panel: `position:fixed; top:var(--app-header-h, 0px); right:0; bottom:0; width:360px; max-height:none; border-radius:0; border-left:1px solid var(--cal-line); padding:24px; box-shadow:-8px 0 24px rgba(0,0,0,.08)`. At 768-1023 px use width 320 px. Check the shell (`_shell_v2.html`) for the top header height and the tablet icon rail; the panel must not cover the rail or header. Content as phone: pill + round ×, stay list, full-width primary "Add stay" (48 px). While open, the calendar body gets `padding-right` equal to the panel width so no tile hides under it.
6. **Create and details dialogs ≥768 px:** centred modal (as now), 480 px wide, 24 px padding, radius 16 px, the 0814 round × (40 px, neutral), title one line with ellipsis, 12 px between buttons, primary full width at the bottom.
7. Old overlay bars (`.cal-week-events`) are not rendered in month scale for the host calendar any more (tiles replace them). Week scale keeps them.

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/dashboard-calendar.js` | edit |
| `App/app/static/dashboard-calendar.css` | edit (append `/* 0816 */` block; delete rules it replaces) |
| `App/app/templates/_dashboard_calendar.html` | bump `?v=` on css and js to `20261102-0816` |
| `App/tests/static_versions.json` | regenerate (`.venv/bin/python tests/test_static_versions.py --write`) |
| `App/tests/test_dashboard_calendar_browser.py` | update assertions that need month bars or the create dialog opening straight from a day click; add tests (section 6) |
| `docs/tasks/screenshots-0814/` | add 768 / 1024 / 1280 / 1440 PNGs (section 6) |
| `docs/tasks/0816-report.md` | create |

## 4. Steps

1. Read the 0814 diff, `_shell_v2.html` (header and rail sizes), and `renderCalendar`.
2. JS: `tiles()`, render branch, mouse/keyboard to panel, side-panel open/close, no bars in host month scale.
3. CSS per section 2.
4. Version bump, static_versions, tests, screenshots, report.

## 5. Do not touch

Cleaning mode (`data-cleaning="true"`): 0815 handles it next; keep every change behind `!cleaningMode`. Phone behaviour from 0814. Gantt and year views. The create form fields and POSTs. No new dependency, no new i18n key.

## 6. Commands and tests

Add to `test_dashboard_calendar_browser.py` (existing fixtures), parametrised over widths 768, 1024, 1280, 1440:
- `test_month_tiles_and_side_panel`: `/?cal_view=calendar` month view: no `.cal-week-events .cal-event` in month scale; tiles ≥96 px tall; gap ≥6 px; a booked day shows ≥1 `.cal-tile-chip` (name the chip class this) with the stay label; no horizontal overflow. Click day 10, then day 12: tiles 10-12 have background `rgb(34, 34, 34)`; panel visible, `dialog:modal` is null, panel right edge = viewport right, panel left edge ≥ last tile's right edge (no tile under it); pill and × centres within 2 px; × 40×40 not coral; Add ≥44 px tall, ≥24 px above panel bottom; text ≥16 px from panel edges. Add opens the create dialog with `date_from` day 10, `date_to` day 13; create dialog × is 40×40.
- `test_mouse_drag_opens_panel` at 1280: mouse down on day 3, move to day 5, up → 3-5 selected, panel open.
- Screenshots: `calendar-768.png`, `calendar-range-768.png`, `calendar-1024.png`, `calendar-1280.png`, `calendar-range-1280.png`, `calendar-create-1280.png`, `calendar-1440.png`.

From `App/` with `UBYHOST_REQUIRE_BROWSER=1`: `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_cleaning_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. All pass, 0 skipped. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] Section 6 tests pass, 0 skipped; 0814 phone tests and cleaning tests still pass.
- [ ] Seven screenshots exist.
- [ ] Lint OK. Only section 3 files changed.

## 8. Stop and ask

The header or rail height cannot be found; a cleaning test fails twice; 25 tool calls without green tests.

## 9. Report

`docs/tasks/0816-report.md`: files, test last lines, old assertions changed and why, deviations.
