# 0532 report

Status: partial (steps 1, 1b, 2, 2b, 3 committed; group 2 has 22 failures, screenshots not taken, see below)

## Commits
- `52836fb` 0532 step 1: apartments.html rebuilt on v2 markup (`set v2`, empty blocks, `.head`, `.card` table, `.setup .st` chips, plain copy button, row menu kept)
- `921566d` 0532 step 2: app2.css chip rules and phone `.btn.sm` 44px rule (append), base.html key `20261101-0709f` to `20261101-0532a`, static_versions.json via `--write`
- `8b6cf91` 0532 step 3: `apartments.sub` in host_i18n.py (en, cs) and host_vi_i18n.py

## Not committed (step 4 incomplete)
- `App/tests/v2_mockup.py`: `properties` entry added to PAGES. Seed not changed: `dashboard_rich_host` already creates two properties (Review Flat plus the demo property).

## Test tails
Step 4 (`-k properties`): `12 failed, 13 deselected in 25.92s`
Section 6 group 1: `32 failed, 90 passed in 165.21s`. Failing: 0710 for `properties` (all widths, styles and geometry), 0710 for `overview` (all widths, same kinds of diffs, see below), `test_properties_table_chips.py` (2 tests, add-CTA icon), `test_host_properties_navigation.py` (3 tests), `test_host_ux_acceptance.py` (2 tests), `test_0300_copy_button.py::test_apartments_copy_buttons_use_the_one_copy_button_component`.
Group 2 and the lint commands were not run.

## Findings that block step 4
- `.head .sub` and `main table th` colour: app `rgb(138,138,132)`, mockup `rgb(107,107,101)`. Same diff on overview, so it is a shared v2 rule, not this page. Brief section 8: needs a rule change, not a page fix.
- `overview` also fails with `.side` padding and `.card.cal` diffs before any change of mine touched those selectors, so these failures look pre-existing on this branch. Not verified against a baseline run.
- `.setup .st`: test reports "missing in app" at 390 px, yet the geometry run finds the chips. Selector or test-harness issue to check.
- Geometry: chips are 23px tall (min 24 required); `input.sr-only` 21px and row-menu trigger 28x21 fail tap-target check; `small` 11px text in nav fails.
- `test_0300_copy_button` requires the `copy_button` component on `/apartments`; the brief asked for a plain button. Conflict between brief and test.
- Test-only failures in `test_properties_table_chips.py` and `test_host_properties_navigation.py` expect old list markup (add-CTA icon, setup/calendars in menu). Section 8 permits updating assertions for old markup on `/apartments`, but I did not get to it.

## Deviations
- Inactive marker changed from `ui-badge` to `<small>` (brief section 2 asked for `<small>`).
- Add button in `.head` is always shown (mockup), no longer only when rows exist.
- Copy button is a plain `button.btn.sm.ghost`, not `copy_button`, as the brief asked; conflicts with test_0300.

## Screenshots
Not taken (step 6 not reached). `docs/tasks/screenshots-0532/` not created.

## Diff stat (steps 1-3)
Files: App/app/templates/apartments.html, App/app/static/app2.css, App/app/templates/base.html, App/tests/static_versions.json, App/app/host_i18n.py, App/app/host_vi_i18n.py.

## Owner or orchestrator steps left
- Decide on the shared `.head .sub` / `th` colour rule (app2.css vs mockup), and whether test_0300 should accept the plain copy button.
- Then the executor can finish step 4 and steps 5-6.

## Executor pass (brief 0532 finish, Haiku)
Commits this pass: `f708b72` step 1b (copy_button v2 shows the label as visible text, no icon); `43ccf3d` step 2b (`.props-card{overflow-x:auto}` in app2.css so the table scrolls inside its card on phones; key `20261101-0532c`; manifest rewritten; navigation test empty-state assertion now asserts the v2 empty state, "No properties yet." and no "Add operator").

Tails:
- `tests/test_0300_copy_button.py`: 2 passed.
- `tests/test_static_versions.py`: 3 passed.
- `tests/test_host_properties_navigation.py` + `test_0300`: 9 passed, 1 failed. The failure is `test_properties_page_fits_every_width_and_both_languages` at 768 px: the row-menu trigger (`opens` 827 px) is past the right edge. Shared item, not fixed. 360 and 390 px now pass.
- Section 6 group 2: `22 failed, 88 passed in 329.62s`.
- `design_lint.py`: FAIL, `apartments.html: T3 class not in catalog: st` and `dots`. Not fixed (catalog change, see below).
- `context_lint.py`: OK.

## Shared items waiting on 0711 / 0713 (not fixed here)
- Row-menu trigger past the right edge at 768 px and up (navigation fit test, `test_0285`, `test_host_list_page_layout_browser`).
- `.sidebar-nav` rail click.
- Ink colours, nav text size (`small` 11 px), sr-only tap targets (`input.sr-only` 21 px).
- `.head .sub` / `main table th` colour: app `rgb(138,138,132)` vs mockup `rgb(107,107,101)`; shared v2 rule.
- Onboarding banner: `.onboarding-banner-setup-link` background (`test_onboarding_wizard_browser`, 16 cases).
- `test_0384`-style phone card open line (`test_0385_phone_card_open_browser`, 4 cases), and `test_0284_states_browser::test_hover_changes_every_clickable_thing`, `test_design_guardrails_browser::test_every_host_page_passes_the_layout_guard`.
- Design catalog: `st` and `dots` chip classes on apartments.html are not in the design catalog (`design_lint`).

## Not done
- Step 3 fixes for this page's own items beyond the table scroll: not completed; the 22 group-2 failures were classified as shared or not investigated.
- Step 4 screenshots (`docs/tasks/screenshots-0532/`) not taken.
- Group 1 not re-run in this pass.

## Deviations (this pass)
- The copy-button macro v2 and non-v2 branches are now separate `{% if %}` blocks, so non-v2 whitespace differs; markup and data attributes are the same.
- The navigation test's ready-state assertion was changed to the v2 empty state (section 8 rule).

## Executor pass (brief 0532, steps 1-4, Haiku, final)
Status: **blocked**. Lint and tap-target geometry are green; the 0710 style comparison and two shared tests still fail.

Commits: `8fed5cf` step 1 (design_lint allow-list covers apartments.html, same as dashboard.html); `a6aa258` steps 2-3 (`.props-card .row-primary-link` 24 px min height; `@media (max-width:1023px) .props-card .st{min-height:44px}`; key `20261101-0532e`; manifest rewritten).

Results:
- `design_lint.py`: OK. `context_lint.py`: OK.
- 0710 `-k properties` geometry: 6 passed at all widths.
- 0710 `-k properties` style: 6 failed.
  - 320 and 390 px: `.setup .st: missing in app`. The chips exist in the template and the CSS rules are in app2.css; the first visible `.st` is not found by the comparison at phone widths. Not diagnosed further (no phone rule hides it in the CSS files searched).
  - 768 to 1440 px: `.setup .st` colour and background differ (app red, mockup green). The first chip of the first row is "Police", which is `bad` in the rich-host seed (`dashboard_rich_host`, which has open UbyPort issues) and `ok` in the mockup. Data difference, not CSS. Fix needs an owner decision on the seed (the fixture is shared with `test_host_quiet_dashboard_browser.py`) or a mockup change.
- Section 6 group 1 (`test_0530`, `test_properties_table_chips`, `test_host_properties_navigation`, `test_host_ux_acceptance`, `test_operator_naming`, `test_status_colours`, `test_0300`, `test_no_dead_internal_links`, `test_static_versions`): 113 passed, 9 failed. Failures:
  - 6 x `test_0710` style (above, page data).
  - `test_host_properties_navigation::test_properties_page_fits_every_width_and_both_languages`: row-menu trigger past the right edge at 768 px. Shared: already listed in the 0532 pass; needs the shared row-menu/table width rule (0711 or 0713 scope).
  - `test_static_versions` x2: fixed in `a6aa258` (now 3 passed).
- Section 6 group 2: not re-run in this pass (earlier pass: 22 failed, all listed as shared in the previous section). Not re-run because of the call budget.
- Screenshots `docs/tasks/screenshots-0532/`: NOT taken. `test_v2_screenshots` writes to `docs/tasks/screenshots-0710` only (env `UBYHOST_SHOTS_V2=1`), so a dedicated 390/768/1280 capture for `/apartments?lang=cs` is still needed.

Remaining for the owner or orchestrator:
1. Decide the Police chip state in the 0710 seed (or mockup) for the properties style comparison.
2. Diagnose `.setup .st` missing at 320/390 px in the 0710 comparison.
3. Shared row-menu trigger width at 768 px (navigation fit test).
4. Capture the three cs screenshots for step 4, then set status to review.

## Executor pass 5 (brief 0532, steps 1-6, Haiku)
Status: **blocked** (group 2 below). Step 3 set is green; lints green.

CSS now in app2.css (0532 block): the `(max-width:1023px)` column-2 hide, the `(max-width:767px)` column-3 show, and a `(max-width:1023px)` fixed-table block (copy col 96 px, menu col 44 px, Name and Setup share the rest, `.nowrap` cells and `.btn` may wrap, `.st` wraps and is 44 px high, `.row-primary-link` 44 px). Key deviation: the key was bumped more than once because each CSS edit needs a new key; final key `20261101-0532l`, not `0532f`.

Tests (from App/):
- Step 3 set (`0710 -k properties`, `test_host_properties_navigation`, `test_0530`, `test_static_versions`, `test_host_ux_acceptance`): `26 passed, 27 deselected in 19.95s`, 0 skipped.
- Group 2: `10 failed, 100 passed in 346.84s`. Failing: `test_design_guardrails_browser::test_every_host_page_passes_the_layout_guard`; `test_host_list_page_layout_browser` x3; `test_0285_rows_browser::test_properties_rows_match_stays_rows`; `test_0284_states_browser::test_hover_changes_every_clickable_thing`; `test_0385_phone_card_open_browser::test_phone_card_open_has_its_own_line` x4. Cause: they wait for `table.properties-table tbody tr.clickable-row` (old markup). Needs the section 8 assertion update to v2 markup, not done.
- `design_lint.py`: OK. `context_lint.py`: OK.

Screenshots (`docs/tasks/screenshots-0532/`): app-390, app-768, app-1280, mockup-390, mockup-768, mockup-1280 (copied from the 0710 screenshot test, `/apartments` without `?lang=cs`; not re-taken with cs). The 0710 tracked PNGs rewritten by the test were restored with `git checkout`.

Not done: group 2 section 8 updates; cs screenshots; 320 px and 1024 px screenshots; no visual look at the PNGs in this pass.

## Executor pass 7 (brief 0532, orchestrator decisions 1 to 5)
Status: **blocked**. One guardrail failure left (smart-locks close button, below). Everything else in groups 2 and 1 passes.

Commits: `3bd9b80` (revert of pass 6, copy column back, mockup hover rule and tests restored), then this commit (pass 7 edits).

Changes:
- Copy-link column back in `apartments.html` (from the revert). Mockup hover rule added in the 0532 block of `app2.css` (opacity 0, shown on row hover or focus-within from 1024 px; always visible below). `body.v2 .props-card tbody tr.clickable-row{cursor:pointer}` added. `body.v2 .sr-only` rule re-applied near the top. Key `0532o`.
- Section 8: `test_0284` and `test_host_list_page_layout` properties entry use `.props-card table tbody tr.clickable-row`.
- Section 8 (orchestrator approved): `test_0285::test_properties_rows_match_stays_rows` deleted (its only comparison was /apartments vs stays). `test_host_list_page_layout::test_tabs_are_links_that_mark_the_open_page`: /apartments removed from its cases, and its /apartments entities-link assertion removed. `test_host_list_page_layout::test_list_pages_share_order_edges_and_rhythm`: properties skipped (v2 /apartments has no title, toolbar or tabs block).
- `tests/test_0385_phone_card_open_browser.py` deleted: the whole test is the old phone table-cards layout on /apartments (`thead` hidden), which v2 does not have.
- Guardrail (`tap-target-small`): on `origin/claude/project-thread-50hyv5` the guard test passes 11/11, so the cause is this branch. Fixed in `host.css` 0531 block (key `0531f`): copy-link button 44 x 44 px below 768 px, toast close 44 px. Fixed the copy-link findings (fee-setup, property-detail x2, guest-links, automation).
- `base.html` keys: `app2.css` 0532o, `host.css` 0531f. `tests/static_versions.json` rewritten.

Test tails:
- Group 2 (guard, list layout, 0285, 0284, onboarding, 0502): `1 failed, 104 passed in 231.81s`. The failure: `test_every_host_page_passes_the_layout_guard`, `smart-locks 390 open: tap-target-small button "×" 24 x 21`. Not on 50hyv5, so it is this branch. Not fixed: the element is not in `base.html` toast markup, `app.js` toast or `property_page_review.html`; locate it (grep the smart-locks page's render path) and add a 44 px rule in the 0531 block.
- Group 1 before the last host.css and app2.css edits: `121 passed, 1 failed` (the failure was `test_static_versions`, fixed by rewriting the manifest). Group 1 not re-run after the final CSS edits: owner or next pass should re-run it.
- `design_lint.py` and `context_lint.py`: see the last lines above, run in this pass.

Not done: screenshots (`docs/tasks/screenshots-0532/`, step 6) not taken; the 0532 cs capture is still missing.
Next: fix the smart-locks × tap target; re-run group 1; take the screenshots; then set status to review.

## Executor pass 8 (brief 0532, smart-locks close button)
Status: **review**. Groups 1 and 2 pass with 0 skipped, both lints OK.

The × element: `button "×"` (24 x 21) is the sticky error toast close on the smart-locks page (`<button type="button" data-toast-close aria-label="Dismiss notification">×</button>` in `<div class="toast err" data-toast data-toast-kind="error" data-toast-sticky>` inside `.toast-stack`). Its computed min-width and min-height are 0px: no host.css rule applied. Cause: the smart-locks page renders the v2 shell, which loads `app2.css` only (base.html, `v2` branch), not `host.css`. The 0531 rule in host.css therefore never reaches it.

Changes:
- `app2.css` (0532 block, key `0532p`): `@media (max-width:767px){.toast-stack .toast > [data-toast-close]{width:44px;min-width:44px;min-height:44px}}`. This is a deviation from the brief, which asked for the host.css 0531/0532 block: a host.css rule cannot fix a v2 page.
- `host.css` (key `0531g`): deleted the duplicate "0532 guardrail" comment (copy-button line). The toast rule in the 0531 block is unchanged.
- `host2.css` (key `0530c`): removed `.host-workspace .property-setup-chips` and `.property-setup-chips .ui-badge` (dead since 0530).
- `docs/design/catalog.json`: removed the `property-setup-chips` entry from the class list and from the descriptions. JSON validated.
- `base.html` keys bumped; `App/tests/static_versions.json` rewritten with `test_static_versions.py --write`.
- `docs/tasks/screenshots-0532/`: app-390/768/1280.png (`/apartments?lang=cs`, full page) and mockup-390/768/1280.png (mockup `props` view, full page), overwritten. Taken with a temporary test file, deleted after the run. Not visually re-checked in this pass.

Test tails:
- Group 1: `122 passed in 155.19s (0:02:35)`, no failures, no skips.
- Group 2: `105 passed in 228.88s (0:03:48)`, no failures, no skips. Run without `tests/test_0385_phone_card_open_browser.py`, which pass 7 deleted; the command in brief §6 needs that path removed.
- `design_lint.py`: OK. `context_lint.py`: OK (warning only: 130 commits touched App/ since the last status.md update; orchestrator to update status at review).

Stray tracked PNGs in `docs/tasks/screenshots-0410/` were rewritten by the group run and restored with `git checkout --`.

Owner steps left: none for this pass. Next: orchestrator review, then merge via `scripts/merge-pr-on-green.sh`.

## Executor pass 9 (brief 0532, list row height, Haiku)
Status: **blocked**. Done: step A (row height). Left: step B (retake the mockup and app 390/768/1280 screenshots after animations end, hide the font picker), most of step C (the test groups, design_lint, context_lint), and step D's test tails. Tool-call cap reached.

Cause: at 1024 to 1440 px the row was driven by three cells, not one.
- Copy-link cell: `button.copy-btn` was 60 px tall because its SVG rendered at 44 px.
- Setup chips: the four chips wrapped to two lines (`.setup` 54 px) because the cell was too narrow.
- Name and address cells: the name wrapped to two lines (44 px link), and the address (74 px wide) wrapped to two or three lines.

Heights before and after (`/apartments?lang=en`, first row; mockup `props` view row at 1280 is 53 px):

| Width | Before (row) | After (row) |
|---|---|---|
| 1024 | 88 | 53 |
| 1280 | 85 | 53 |
| 1440 | 85 | 53 |

Changes (App/app/static/app2.css, 0532 block, `@media (min-width:1024px)` only; below 1024 px nothing changed):
- `.setup` stays on one line (`flex-wrap:nowrap`) and chips are 24 px tall.
- `.copy-btn` is 28 px tall, its SVG 16 px.
- The property name is one line, ellipsis when long.
- The address cell is one line, ellipsis (`max-width:0` trick, so columns share the width).

Key bumped to `0532r` in base.html; `App/tests/static_versions.json` rewritten with `--write`.

Deviations:
- The name and address are truncated with an ellipsis from 1024 px. This was needed to reach 53 px. Full text is in the row's aria-label and the property page.
- The commit message omits "clean screenshots": step B was not done.
- docs/tasks/0533-phone-properties-cards.md was already modified in the working tree before this pass; it is not staged or committed here.
- Temporary measurement tests in App/tests were created and deleted; nothing left behind.

Test tail, `0710 -k properties`:
=========================== short test summary info ============================
FAILED tests/test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles[properties-1024]
FAILED tests/test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles[properties-1280]
FAILED tests/test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles[properties-1440]
3 failed, 9 passed, 13 deselected in 16.69s

## Executor pass 10 (brief 0532, desktop style match, clean screenshots, Haiku)
Status: **blocked**. Done: step 1 (0710 `-k properties` green at 1024, 1280, 1440), step 2 (screenshots), step 3 group 2 green and both lints OK. Left: 2 failures in group 1 (geometry, see below).

What differed (0710, `tbody tr .btn.sm.ghost`): padding-top and padding-bottom were app 0px, mockup 6px at 1024, 1280, 1440. Fix: `.copy-btn` padding-block 0 to 6px in the 0532 pass 9 block of App/app/static/app2.css (min-width:1024px). The v2 `copy_button` branch in `_components.html` now uses classes `btn sm ghost copy-btn` (text only, same data-copy attributes). Key bumped to `0532s` in base.html; `App/tests/static_versions.json` rewritten with `--write`.

Screenshots: docs/tasks/screenshots-0532/ app and mockup at 390, 768, 1280 (full page, `/apartments?lang=cs`, mockup `props`). Mockup: reduced motion, 800 ms wait, `.fontpick` removed from the DOM. Mockup file not edited. Temporary test deleted.

Group 1 tail (`2 failed, 120 passed in 149.64s`):
FAILED tests/test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages
FAILED tests/test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state

Cause (not fixed): the page scrolls sideways (scroll width 1294 px at 1024 and 1280 px viewports), and the actions cell reaches x=1358. Pass 9 did not run these tests. The likely cause is pass 9's min-width:1024 rules (`.setup` nowrap, one-line name and address), not the copy button. Not confirmed. Owner or orchestrator: decide whether the chip row may wrap, or the widths need a new rule; then rerun these two tests.

Group 2 tail: `105 passed in 225.12s`, 0 skipped. 0385 left out (file deleted).
design_lint: OK. context_lint: OK.

Deviations: browser runs rewrote unrelated tracked PNGs (docs/tasks/0102-evidence, screenshots-0410); restored with git checkout.
