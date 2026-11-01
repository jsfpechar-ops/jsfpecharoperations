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
