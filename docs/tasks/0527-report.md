# 0527 report: stays list v2, tests and screenshots

Status: blocked

Done: step 0 (bf1cef19); step 1 (420e13a2: one h1, Czech path, chevron 20, head actions hidden below 1024, key 20261101-0527c, manifest 41 files). Left: step 2 (old tests) and step 3 (screenshots). Steps 2 and 3 need a new session.

## Step 1 result
`pytest tests/test_0710_v2_mockup_match_browser.py -k stays -q --tb=no -rfs`: 3 failed, 9 passed, 0 skipped. Geometry passes at 320-1440 (1024 overlap gone with the upcoming range). Phone h1 is the single `.head h1` at every width.

## Remaining mismatches
- Waiting on shell (Overview thread): `.top .round` font-size, colour, padding (0718); `.chip.on` red background and border (app2.css global `!important`); `.head h1` 32 px and `.head .btn` styling at 768.
- Expected by decision 3 (not a bug): at 768 the table and head buttons are hidden, so `main table *`, `main td small` and `.head .btn` are missing in the app when compared with the desktop mockup. Table is not visible at 768.
- Row (`.list .row`): app uses `<a class="row">` (must link), mockup uses `<button>`. Border colour (text colour in app) and height 101 vs 103 px remain; `.row .t` 184 vs 180 px at 320 (4 px). Listed, not fixed with CSS on shared classes.
- Pill width `.row .pill.p-warn` 122 vs 161 px: label text differs from mockup copy. The shared test does not accept missing_ok for width mismatches, so this stays failing (not loosened).

## Step 2 (not done)
Old stays tests run once in this session: the run was cut at the 120 s tool limit and moved to the background (task bhvdhb4a0). Output shows many ERROR lines in unrelated browser tests (sidebar, a11y, design guardrails, host wide geometry) with no detail, plus FAILED entries in the list-page tests. Next session: run one file at a time with `--tb=short` to find whether the errors are a fixture problem.

## Commands
- `pytest tests/test_0710_v2_mockup_match_browser.py -k stays -q --tb=no -rfs`: `3 failed, 9 passed` (see above, 0 skipped).
- `pytest tests/test_static_versions.py -q --tb=line -rs`: `3 passed`.
- Design and context lint not run.

## Deviations
- Stays path is `/reservations?range=upcoming&lang=cs`, not `range=all`. The template has no "all" chip, so `range=all` shows no `.chip.on`; the mockup's selected chip is "upcoming". Czech labels now match (the test appends `?lang=en`, so `lang=cs` was not used alone).
- Phone h1 is `<h1 class="big">` on the `.head` h1 (no separate phone h1). Head is shown below 1024 as `display:block`, and the shell underline `.head h1:after` is hidden for `.stays-head` below 1024 (page-scoped; mockup phone h1 has no underline).
- `.chevron-right` icon size 16 changed to 20 (mockup `svg.chev`).
- Pagination and filter tap sizes from earlier step kept.

## Questions / owner
- Shell (Overview thread): approve `.top .round`, `.chip.on` !important, and `.head h1` / `.head .btn` below 1024.
- Copy: approve chip and pill label length (owner).
- Confirm `range=upcoming` as the stays test fixture.

## Session 3 (section 10 fix list)
Status: blocked (budget). Commits: 9ec057d7 (items 1 to 5, 7), 389e83de (filter panel collapse, key 20261101-0527e, manifest 41 files).

Done:
- Item 1: `body.v2 [hidden]` and `body.v2 .hidden` set to `display:none!important` (app2.css, shell section). Filter panel also collapsed (`body.v2 .stays-filter.is-collapsed`), because the existing rule lives under `.host-workspace` and does not apply on v2.
- Item 2: `.stays-phone` top row (+ button) moved before the `.head` in reservations.html. Screenshot at 390 shows the + button first.
- Item 3: page-scoped panel CSS (padding 16px, label 12px --ink2, `.in`-style controls, 2-column grid from 1024). Panel buttons still use `ui-btn` classes (not `.btn ghost sm`).
- Item 4: pager replaced by one `<nav class="stays-pager">` with "Strana 1 z 2" and two links (disabled one is a span with aria-disabled). Verified at 390: "Předchozí  Strana 1 z 2  Další".
- Item 5: count line has class `stays-count` (13px, --ink3).
- Item 7: the header th already held an sr-only span. Added `body.v2 .stays-desk .sr-only` clip rule.

Test runs (App/, browser env set):
- `tests/test_0710_v2_mockup_match_browser.py -k stays`: 3 failed, 9 passed, 0 skipped. Failures at 320, 390, 768 are the shell-owned ones (`.top .round`, `.chip.on`, `.head h1` and `.head .btn` at 768) plus the known `.row` height, `.row .t` width and pill width. The 768 list also has `.chip` padding (0718 phone class applies up to 1023 px), which is not in the brief's list.
- `-k screenshots` (UBYHOST_SHOTS_V2=1): 1 passed. Output went to `docs/tasks/screenshots-0710/` (test hard-codes SHOTS_DIR), overwriting the untracked 0710 files there. Not committed.
- `tests/test_static_versions.py`: 3 passed.

Left:
- Item 6 NOT fixed. The bottom "Stáhnout domovní knihu" row still shows at 1280. Cause: `.link{display:flex}` in the `min-width:1024` block (app2.css, around line 305) overrides `.stays-phone-only{display:none}`. Fix: add `@media (min-width:1024px){body.v2 .stays-phone-only{display:none}}` at the end of app2.css, then bump the key and `--write`.
- Step 2 (old tests) not started.
- Step 3 (screenshots into docs/tasks/screenshots-0527/ with app-<w>.png names, cs locale, mockup pairs) not started. Current shots are in the 0710 folder, en locale.
- Visual differences seen at 1280 and 390: the table header "Otevřít" column is no longer visible; the filter panel is now collapsed behind the "Filtry" chip. Re-check after the item 6 fix.

Deviations: no new subagents, no push. Untracked `docs/tasks/screenshots-0710/*` is not committed.

## Session 4 (Haiku executor)
Status: blocked
Done: step 0 item 6 (commit 622a1781: `body.v2 .stays-phone-only{display:none}` at min-width 1024, key `20261101-0527f`, manifest 41 files; `test_static_versions.py` 3 passed). Step 1 unchanged: `-k stays` 3 failed, 9 passed, 0 skipped (the three are the shell-owned items above).
Left: step 2 (old tests) and step 3 (screenshots, not started; the retake test is `tests/test_0710_v2_mockup_match_browser.py` with `UBYHOST_SHOTS_V2=1`).

Step 2 triage, one file at a time, `--tb=short -rs`, no test edited yet:
- `test_0523_stays_list.py`: 2 passed, 6 failed. Helper at line 84 uses `</tr>` (table removed in 0526); line 196 asserts `.stays-view` count 1 (replaced by `.stays-phone`).
- `test_design_stays.py`: 1 passed, 2 failed. Line 10 expects `class="ui-toolbar" data-filter-toolbar data-list-toolbar` (removed); line 27 forbids `style="` and `class="btn` in `reservations.html` (both present now).
- `test_archive_stays_on_page.py`: 10 passed. No change needed.
- `test_stays_empty_workspace.py`: 13 passed, 1 failed. Line 232 expects `data-list-toolbar` (removed); `stays-filter-panel` and `data-filter-panel` still present.
- `test_host_list_layouts_browser.py`: 2 failed. `_check_pairs` gets 0 pairs for stays/en/360 and the ONE_LINE row probe finds 0 rows (selector `row-open`/`.row` no longer matches).
- `test_host_list_page_layout_browser.py`: 3 failed. Tab-strip regex at line 178 finds no `sub-tabs` nav on `/reservations` (tabs removed); stays geometry matrix "missing block"; line 300 "no clickable row" for stays (new row is `a.row`).
- `test_host_filter_panels_browser.py`: 1 passed, 3 failed. `[data-save-view]` click times out (button dropped in 0526, owner told); `[data-filter-toolbar]` not visible at 360 px en `/reservations`.
- `test_0199_phone_geometry_browser.py`: 3 passed.
- `test_host_wide_geometry_browser.py`, `test_design_guardrails_browser.py`, `test_a11y_guard_browser.py`: setup ERRORs (10, 11, 4). Shared fixture `wide_base` line 199 asserts `data-host-alerts` in a signed-in host page; the response is a 200 page without it. Not triaged: may be a login/fixture problem or a shell change. Stop-and-ask item (brief section 8): not edited.
- `test_static_versions.py`: 3 passed.

Next session: start with `test_0523_stays_list.py` (update the `</tr>` helper and `.stays-view` assertion to `.stays-phone`/`a.row`), then the two template assertions, then the rest. Commit after each 2-3 files as `0527 step 2`.

Not pushed. No PR opened (brief says do not push; owner decides).

## Session 5 (Haiku executor)
Status: blocked
Commits: cf78aa36 `0527 step 2` (0523 + design_stays); next commit `0527 step 2` (filter panels, empty workspace, app2 calendar CSS, key bump).

Step 2 results, `--tb=short -rs`, 0 skipped:
- `test_0523_stays_list.py`: 8 passed. Edited: `_row` helper now finds `data-href="/reservations/<id>?return_to="` inside `<tr>`; header check counts 6 `<th>` and reads labels from `<th>`; property regex uses `data-card="meta"`; deadline check uses `data-deadline=`; capture test counts `.stays-desk`.
- `test_design_stays.py`: 3 passed. Edited: `ui-toolbar` assert replaced by `<div class="chips">`; add-stay panel assert now `class="action-panel hidden stays-panel"`; template check keeps the no-`style="` assert, drops the `class="btn` and `class="pill` bans (the pill is the v2 `.pill` class).
- `test_stays_empty_workspace.py`: 14 passed. `data-list-toolbar` assert replaced by `.chips`.
- `test_host_filter_panels_browser.py`: 3 passed, 1 FAILED. Edited: save-view steps deleted from `test_filter_draft_calendar_and_month_grid_commit_once` (the rest of that test kept); `.stays-view tbody tr` to `.stays-desk tbody tr`; `.chips .chip.on` replaces the `ui-chip` selector; geometry test uses `.chips` as the lane on /reservations and exempts the lane's internal scroll for `.chips` only (mockup chips scroll sideways by design).
- `test_static_versions.py`: see the run line below.

CSS added (app2.css, end of file): `body.v2 .range-day` and `body.v2 .range-draft-fields input[type=date]` at 44px under 1023 px (the host.css phone rule does not apply on v2).

Still failing: `test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_czech`, 360 px en /reservations: the date-range popover measures y 706.8 + height 481 = 1187 > 1001 (viewport 1000). Shared date-range component (`_date_range.html`), not stays CSS. Question for the orchestrator: fix the popover placement (open upward, or scroll it into view on open) or allow the test to scroll the popover first? I did not loosen the assertion.

Not started: `test_host_wide_geometry_browser.py`, `test_design_guardrails_browser.py`, `test_a11y_guard_browser.py` (setup errors; decided fixture change: `wide_base` readiness to `[data-host-alerts], body.v2`, line ~199, not applied yet); `test_host_list_layouts_browser.py`, `test_host_list_page_layout_browser.py`, `test_0199_phone_geometry_browser.py` (3 passed earlier, not re-run), the `-k stays` shared test, and step 3 (screenshots, not started). Also pending: the reservations.html inline-style check passes (0 `style=`), no change needed there.

Deleted tests: none. Deleted assertions: the save-view steps inside `test_filter_draft_calendar_and_month_grid_commit_once` (button dropped in 0526, owner's decision).

Deviations: 1) pill ban removed from `test_design_stays.py` (not in the orchestrator list; the pill is a v2 class, see above). 2) Step count exceeded: this session stopped at the 25-call checkpoint.
Owner steps left: none. Not pushed. No PR.
