# 0541: Cleaning redesign, part 2: header with one button, calendar below the tables
Status: todo
Depends on: 0540 (same branch) | Base commit: branch head after 0540 | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
The host cleaning page (`/cleaning`) header follows the approved computer mockup (`ubyhost-redesign-v2.html`, view "clean"): title "Úklid", the subtitle "Úklidy vznikají samy z odjezdů. Uklízečka vidí svůj rozpis přes odkaz.", one primary button "Sdílet rozpis s uklízečkou". The tables from 0540 come first; the cleaning calendar (with drag-to-move) moves below them. The cleaner's shared page keeps its order (calendar first).

## 2. Context
- Header: `App/app/templates/cleaning.html` (blocks `meta`, `primary_action`, `secondary_actions`; `ui_button(label, kind, href=, icon_name=, attrs=)`).
- Body: `App/app/templates/_cleaning_screen.html`, included by `cleaning.html` (host) and `cleaning_shared.html` (cleaner, `read_only=True`). Lines 3-8 are the legend + `{% include "_dashboard_calendar.html" %}` (or the no-properties paragraph); then the `#cleaning-list` section; line 1 is a skip link to `#cleaning-list`.
- Copy: `App/app/cleaning_i18n.py` (`WORDS`, `[en, cs]`), vi in `CLEANING_WORDS` in `App/app/host_vi_i18n.py`. `ct('subtitle')` is used only in `cleaning.html` (checked).

## 3. Files
Create `App/app/templates/_cleaning_calendar.html`, `App/tests/test_0541_cleaning_header.py`. Edit `App/app/templates/cleaning.html`, `App/app/templates/_cleaning_screen.html`, `App/app/cleaning_i18n.py`, `App/app/host_vi_i18n.py`, `docs/design/pages/cleaning.md`, and header assertions under section 8. Screenshots in `docs/tasks/screenshots-0541/`. Report `docs/tasks/0541-report.md`.

## 4. Steps
1. **Header.** In `cleaning.html`: `primary_action` = `ui_button(ct('share_cleaner'), 'primary', href='/cleaning/shares')` (no icon: there is no share icon). `secondary_actions` = `ui_button(ct('add'), 'secondary', href='/cleaning/new', icon_name='plus', attrs='data-calendar-add data-cal-create-type="cleaning"')` then `ui_button(ct('settings'), 'secondary', href='/cleaning/properties')`. Remove the "add stay" button and the old share button. Commit `0541 step 1`.
2. **Copy.** Change `subtitle` to en "Cleanings are created from departures. Your cleaner sees the schedule through a link." / cs "Úklidy vznikají samy z odjezdů. Uklízečka vidí svůj rozpis přes odkaz." / vi "Lịch dọn tự tạo từ ngày khách trả phòng. Người dọn xem lịch qua một đường liên kết.". Add `share_cleaner` en "Share schedule with cleaner" / cs "Sdílet rozpis s uklízečkou" / vi "Chia sẻ lịch với người dọn" at the END of `WORDS` and `CLEANING_WORDS`. Commit `0541 step 2`.
3. **Calendar below.** Move the legend/calendar/no-properties block (lines 3-8 of `_cleaning_screen.html`) unchanged into the new `_cleaning_calendar.html`. In `_cleaning_screen.html` include it before the `#cleaning-list` section when `read_only`, and after that section otherwise (`{% if read_only %}{% include "_cleaning_calendar.html" %}{% endif %}` ... `{% if not read_only %}{% include "_cleaning_calendar.html" %}{% endif %}`). Show the skip link only when `read_only` (on the host page the list is already first). The `<script>` lines stay last. Commit `0541 step 3`.
4. **Design add-on.** In `docs/design/pages/cleaning.md` rewrite the Header and Body sections to what the page now is: primary `cleaning.share_cleaner` -> `/cleaning/shares`; secondary `cleaning.add`, `cleaning.settings`; body = Today / This week / Later tables (Property, Time or Day, Next arrival, Status badge: `action` check the time, `attention` hours missing, `neutral` scheduled), then the cleaning calendar; shared view unchanged (cards, calendar first). Delete the Toolbar section and the tabs line (neither exists). Keep it under 30 lines. Commit `0541 step 4`.
5. **Test** `test_0541_cleaning_header.py` (copy fixtures and login from `tests/test_cleaning.py`): (a) `/cleaning?lang=cs` has exactly one `ui-btn-primary`, labelled "Sdílet rozpis s uklízečkou" and linking to `/cleaning/shares`; (b) no `/reservations?new=1` link in the header; (c) in the host HTML `cleaning-section` comes before `id="calendar"`; (d) in the shared view HTML `id="calendar"` comes before `cleaning-list` and the skip link is present. Commit `0541 step 5`.
6. Screenshots of `/cleaning?lang=cs` at 1280 px and 390 px with seeded cleanings (today, this week, one conflict) into `docs/tasks/screenshots-0541/` (see executor.md, Screenshots). Commit `0541 step 6`.

## 5. Do not touch
`_cleaning_list.html`, `_cleaning_table.html` (0540), `cleaning_shared.html`, `_dashboard_calendar.html`, routes, any JS or CSS file. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0541_cleaning_header.py tests/test_0540_cleaning_tables.py tests/test_cleaning.py tests/test_design_cleaning.py tests/test_copy_cleanup.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5; python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. Two screenshots exist. `git diff --stat HEAD~6` (or since the 0540 report commit) lists only section 3 files.

## 8. Stop and ask
If an existing test asserts the old header buttons (add stay, "Share schedule", "Add cleaning" as primary) or that the calendar comes before the list on `/cleaning`, update only that assertion and list it in the report. Stop if any other existing test changes result, or if a shared-view test fails.

## 9. Report
`docs/tasks/0541-report.md`: Status, test and lint tails, diff stat, screenshot paths, assertions changed, deviations.

## 10. Addendum (orchestrator, after the first run hit the cap)
Steps 1-5 and one browser assertion are committed. Left:
1. `App/tests/test_cleaning_browser.py::test_calendar_popup_types_create_in_place_and_localize_validation` clicks the removed "add stay" header button. Open the dialog with `[data-calendar-add][data-cal-create-type="cleaning"]` instead; assert `[data-cal-type-choice="cleaning"]` is `aria-pressed="true"`; keep the `cleaning-stay-popup-cs` shot after switching to stay; check the date carries both ways (cleaning date to `#cal-arrival`, then back to `#cal-clean-date`); close. Leave the rest of the test as is.
2. Rerun the browser set of section 6 with `-rs` (0 skipped). Fix only host `/cleaning` assertions about header buttons or list/calendar order (section 8); stop on anything else.
3. Step 6 screenshots, the report `docs/tasks/0541-report.md`, commit `0541 step 6`.
