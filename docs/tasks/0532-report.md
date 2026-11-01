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

## Executor pass 6 (brief 0532, sections 5, 6, 8; orchestrator fix list)
Status: **blocked**. Two stop cases (below). Committed as the working state so the owner can see it; nothing pushed.

Changes:
- `app2.css`: `body.v2 .sr-only` visually-hidden rule placed in the shared section near the top (after the reset rules), per coordinator message. Copy-column width rule now `th/td:nth-child(4){width:44px}` (menu column); 96 px rule removed. Key bumped `20261101-0532m`; `static_versions.json` regenerated.
- `apartments.html`: Copy link `<th>` and `<td>` removed; `copy_button` removed from the import.
- `_components.html`: `copy_button` v2 branch removed (no template with `v2 = true` calls it any more; the `dashboard.html` v2 page does not). No `.copy-btn` rule in app2.css to remove (`host2.css` `.host-workspace .copy-btn` is another shell, left alone).
- Section 8 selector/assertion updates: `test_host_list_page_layout_browser.py` (properties entry), `test_0285_rows_browser.py` (selector), `test_0284_states_browser.py` (selector), `test_0385_phone_card_open_browser.py` (2 selectors), `test_0300_copy_button.py` (`copy-btn` now `not in` the /apartments page).

Test tails:
- Group 1: `7 failed, 115 passed in 154.65s`. Six are `test_0710 properties` at 320/390/768/1024/1280/1440: `tbody tr .btn.sm.ghost: missing in app`. Plus `test_0300` (fixed to the no-column assertion in this pass; the run above was before that edit).
- Group 2: `9 failed, 103 passed in 229.37s` (run after the test_0300 edit, which is in the same command as group 2).
  - `test_0385_phone_card_open_has_its_own_line` x4: `rows == []` (selector now `.props-card table tbody tr.clickable-row`; rows exist, see `apartments.html` line 30, so the remaining cause is not diagnosed).
  - `test_design_guardrails_browser::test_every_host_page_passes_the_layout_guard`: 6 `tap-target-small` findings on property pages (fee-setup, property-detail x2, guest-links, automation at 390 px: the copy-link button 32 px; smart-locks: "x" button 24 px). None on /apartments. Another page: STOP case.
  - `test_host_list_page_layout_browser::test_tabs_are_links_that_mark_the_open_page`: `/apartments` has no `ui-tabs` / `sub-tabs` nav on v2 (`assert nav` fails). STOP case: the assertion has no v2 counterpart; not changed.
  - `test_host_list_page_layout_browser::test_list_pages_share_order_edges_and_rhythm` and `test_every_row_opens_on_click_and_enter_and_inner_controls_do_not`: failing, not diagnosed in this pass.
  - `test_0285_rows_browser::test_properties_rows_match_stays_rows`: compares the `/apartments` row computed style to the `/reservations` stays rows: v2 rows have `borders none / radius 0 / spacing 2px`, stays rows `solid / 12 / 0px 8px`. This is the STOP case from brief section 8 (a comparison to another page's old markup that cannot hold on v2). Not skipped, not changed.

STOP 1 (mockup contradicts the orchestrator's premise): `docs/design/mockup/ubyhost-redesign-v2.html` props rows DO have a fourth cell with a `<button class="btn sm ghost">Kopírovat odkaz</button>` (line 174 etc.), under an unlabelled `<th>`. The header is `Název | Adresa | Nastavení | (empty) | (empty)`. So the mockup has a copy-link button in each row. Removing the column is what made the six 0710 `.btn.sm.ghost` failures. Decision needed: restore the copy column in `apartments.html` (keep the sr-only rule, keep the v2 copy_button branch), or change the mockup.
STOP 2: the 0285 stays-row comparison and the `/apartments` tabs assertion (above).

Not done: screenshots (step 6), lints, cs capture. Not run since blocked: `design_lint.py`, `context_lint.py`.
Owner or orchestrator next: decide STOP 1; decide how STOP 2 items should be asserted for v2; diagnose the 0385 empty rows and the tap-target findings on property pages.
