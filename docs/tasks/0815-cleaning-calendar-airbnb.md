# 0815: Cleaning (Úklid) page uses the Airbnb calendar, cleaning tags only

Status: todo
Depends on: 0814 (same branch, already committed) | Branch: claude/project-thread-vnnr9p
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef (2026-11-02): the host cleaning page `/cleaning` must use the same full-page Airbnb-style calendar that 0814 built for `/?cal_view=calendar`, but showing **only cleaning tags** (no bookings), **instead of the rows** (the cleaning table under the calendar), which he finds ugly. Read `docs/tasks/0814-phone-calendar-airbnb.md` section 2 first: same tiles, same tap / long-press range select, same bottom sheet, same dialogs.

Scope: host page only (`data-readonly="false"`). The shared cleaner page (`read_only`, `/cleaning/s/...`) and its list stay exactly as now.

## 2. Design

**Phone (≤767 px):**
1. In `dashboard-calendar.js`, add `function phoneTiles() { return !readOnly && matchMedia("(max-width:767px)").matches; }` and use it where 0814 used `phoneDots()` for tiles, tap, long press and the sheet. `phoneDots()` stays for the host-only things (the `view()` force to calendar etc.); in cleaning mode `view()` must also be `"calendar"` with month scale on phone.
2. Tile marks in cleaning mode: only `event.kind === "cleaning"` events overlapping the day. Instead of bars, each cleaning is a tag: a pill 18 px tall, radius 9 px, background the existing cleaning colour (grep `is-cleaning` in the css for the variable), containing the cleaning icon (`appendCleaningIcon(tag, "cal-cleaning-icon")`, 12 px). Max 2 tags, then `+n` (`cal-dot-more`). Tile with a cleaning gets class `has-cleaning` (no grey fill; grey fill is only for host booked days). Selected tile: tags keep their colour on the ink background.
3. Bookings are not drawn on phone tiles in cleaning mode.
4. Sheet: pill + × as 0814; list = cleanings overlapping the selection (`eventLink`); button label `labels.add_cleaning`, opens `openCreate(start, addDays(end,1), state.property, "cleaning", button)` (scheduled date = start).
5. Hide `.cleaning-legend` and `#cleaning-list` on phone for the host page (`.cleaning-page` + not read-only; check `cleaning.html`/`_cleaning_screen.html` for a usable hook, add a class such as `cleaning-host` on the section if none exists).

**Desktop (≥768 px), host cleaning page:** keep the month bars (they already show cleaning chips) but drop booking bars in cleaning mode (filter them out of `renderCalendar` and gantt when `cleaningMode && !readOnly`), hide `#cleaning-list` and `.cleaning-legend`. Before hiding the table, check `_cleaning_table.html` for actions (edit, delete, done) and confirm each one is reachable from the calendar details dialog (`openDetails` for a cleaning event). If any action is only in the table, do NOT hide the table on desktop; say so in the report.

Turnover logic (cleaning timing from bookings) stays on the server; the events still arrive, they are just not drawn.

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/dashboard-calendar.js` | edit |
| `App/app/static/dashboard-calendar.css` | edit (append `/* 0815 */` block) |
| `App/app/static/cleaning.css` | edit only if needed to hide the list/legend |
| `App/app/templates/_cleaning_screen.html` / `_cleaning_calendar.html` | add a host class hook only if needed |
| templates linking changed static files | bump `?v=` to `20261102-0815`; regenerate `App/tests/static_versions.json` with `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_cleaning_browser.py` | update assertions that need the list or booking bars on the host page; add tests (section 4) |
| `docs/tasks/screenshots-0814/` | add `cleaning-390.png`, `cleaning-range-390.png`, `cleaning-1280.png` |
| `docs/tasks/0815-report.md` | create |

## 4. Tests

Add to `test_cleaning_browser.py`, using its fixtures:
- `test_phone_cleaning_calendar_tags_only` at 390 and 320: host `/cleaning` shows tiles; a day with a cleaning has ≥1 tag with the cleaning icon; a booked day without cleaning has no tag and no grey fill; `#cleaning-list` not visible; no horizontal overflow. Tap a cleaning day → sheet (non-modal) lists that cleaning; Add → create dialog in cleaning kind with `scheduled_date` = that day. Long press + drag (CDP touch as in 0814's test) selects a range.
- At 1280: no booking bars (`.cal-event` without the cleaning class count 0) on the host page; read-only shared page still shows its list (`test_external_dual_view_and_no_javascript_list` must pass unchanged).

Run from `App/` with `UBYHOST_REQUIRE_BROWSER=1`: `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. All pass, 0 skipped.

## 5. Do not touch

The shared cleaner page behaviour, server code, the create/details form fields, the host calendar (0814) look. No new dependency, no new i18n key.

## 6. Stop and ask

A table action has no calendar equivalent (report it, keep the desktop table); the read-only page test fails twice; 25 tool calls without green tests.

## 7. Report

`docs/tasks/0815-report.md`: files, test last lines, changed old assertions and why, deviations.
