# 0547 report: cleaning phone layout

Status: blocked (steps 1 to 5 done; step 6 screenshots not taken; 390 and 320 acceptance not met)

## Done
- Step 1 (`0547 step 1`): key `subtitle_short` (cs, en, vi). Phone subtitle shown below 1024 px, desktop subtitle hidden there. Key `20261101-0547a`.
- Step 2 (`0547 step 2`): the 11 px extra height of `.big` is the `.head h1:after` bar (3 px plus 8 px margin). Neutralised in the cleaning block below 1024 px. Cause shown by arithmetic and by the test; no throwaway script. Key `0547b`.
- Step 3 (`0547 step 3`): `body.v2 .cleaning-today{margin-top:8px}` below 1024 px. Fixture stay NOT kept (see Deviations).
- Step 4 (`0547 step 4`): cleaning entry selectors `.list .row:has(.p-ok)` and `.row .t .pill.p-ok`. Also `body.v2 .cleaning-head>div{flex:1 1 100%;min-width:0}` (h1 and sub were 175 px wide, mockup 350 px). Key `0547d`.
- Step 5: regression run, no code change (13 failed, same count as 0546, now named).

## Test tails
- `tests/test_static_versions.py`: `3 passed in 0.16s`
- overview baseline (before step 3): `1 failed, 11 passed, 21 deselected` (768 px, shared)
- overview with the fixture stay: 4 failed (1024, 1280, 1440 added): reverted
- `test_0710 -k cleaning` (final): `3 failed, 9 passed, 21 deselected in 48.01s`
- step 5: `13 failed, 73 passed in 414.09s`
- `scripts/design_lint.py`: `design lint: OK`

## Left at 390 px (test_0710 cleaning-390, 8 differences)
- `.tab.on` missing: shared shell (brief 0719).
- `.actbar` padding-bottom 12 vs 30 px, height 75 vs 93 px: shared `.actbar` rule.
- `.actbar .btn` missing in mockup: selector mapping (`.bar .btn`).
- `.card` height 57 vs 121 px, margin-top 0 vs 8 px: no departure-today item in the fixture.
- `.list .row:has(.p-ok)` and `.row .t .pill.p-ok` missing in app: the fixture has no green row.

## Left at 320 px
`cleaning-320` fails in `_open_app` (test_0710 line 57), before the style comparison: the security prompt "Not now" button is visible but the click is intercepted by the cleaning `.actbar` share button (sometimes the `.tab` bar). The prompt lives in shared `app.css`, and `_open_app` is outside brief section 3, so stopped per section 8. 0546 reported 320 as passing; not bisected.

## Regression failures (step 5, by name)
- `test_cleaning_browser.py`: `test_calendar_and_large_list_geometry_and_filtering[en-360]`, `[en-390]`, `[cs-360]`, `[cs-390]`; `test_fractional_checkout_and_same_day_cleaning_geometry[360-en]`, `[390-cs]`; `test_three_property_auto_gantt_keeps_cleaning_markers_visible[360-en]`, `[390-cs]`; `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`; `test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs[390-844]`; `test_cleaning_form_pages_fit_the_viewport_and_take_screenshots[390]`. Cause: 10 `Page.wait_for_selector` timeouts (30 s). The first one waits for `.cal-gantt-row, .cal-week, .cal-year` to be visible, which the 0542 rule hides below 767 px. Other causes not inspected.
- `test_0541_cleaning_header.py::test_header_has_one_primary_share_button_in_czech`: `<a class="btn" href="/cleaning/shares"` count 2, expected 1 (the phone `.actbar` adds a second share link, from 0546 step 2).
- `test_design_cleaning.py::test_cleaning_pages_have_the_v2_shell_and_one_stylesheet`: same count 2 on `/cleaning`.

## Deviations
- Step 3 fixture stay reverted: `stay("cleaning-today", ...)` changed the overview baseline (`main tbody tr:first-child td border-bottom-color`, 1024 to 1440 px). Revert restores the original test file (git checkout), so no test changed.
- Step 6 not done: `docs/tasks/screenshots-0547/` is not written.
- Commit trailer: Claude Opus 5.5, as the owner instructed.
- Nothing pushed.

## Owner decisions left
1. Fixture: a departure-today cleaning and a green cleaning row (fixes the 390 card and row rows; will change the overview baseline).
2. 320 px: security prompt intercepted by the cleaning `.actbar` (shared `app.css` or the `_open_app` helper).
3. Calendar tests at 360 and 390 px: the phone layout hides the calendar; the tests expect it.
4. Share-button count tests (0541, design_cleaning): one share link or two.
5. Step 6 screenshots at 390 px: next session.
