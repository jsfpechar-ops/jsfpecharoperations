# 0986: property page: restore main's header and status tiles, keep the setup card, fix the feed URL box

Status: todo
Depends on: 0985 | Base commit: origin/codex/ux-remediation-handoff | Branch: codex/ux-remediation-handoff
Executor: Haiku 5.5 | Fits one session: 25 tool calls.

## 1. Objective
On the property detail page (`/apartments/<id>`, layout-lint shot `property-detail-configured`) bring back main's page header and status tiles, keep the branch's "Continue setup" card below the tiles, and give the Calendars feed "URL" box inner padding. CSS and two templates only; no behaviour change.

## 2. Context
Owner decision, 2026-11-06 (quoted): the owner compared this page on origin/main and on this branch at 390 px and said main "looks better, more organized". Restore MAIN's layout exactly for the page header and the status tiles, but KEEP the branch's new "Continue setup · N of 4 done" card (Continue button + "Hide setup guide"), placed full width BELOW the tile grid, in the same card style as the tiles.

What main has and the branch lost (found by diffing `origin/main..HEAD`):
1. Round icon back button (main) vs text "← Back" link (branch). Cause: branch commits 83d513fe, d7419665, e6094132, 1313d17b made `apartment_form.html` use the `host_page.html` `.ui-ph` header for editing.
2. Help "?" inline right after the property name (main) vs alone on its own right-aligned line (branch). Cause: 551808e7 (`page-help-wrap`) plus branch CSS `.airbnb-header:has(>.page-help-wrap)` grid (app2.css ~1845-1849) and `.ui-ph-title-row` (~1856-1863).
3. Status tiles: main is an even 2-column grid with equal rows (Calendars | Guest link; Foreigner police | Business details; Stay fee | Smart lock). Branch is a flex-wrap with unequal widths and a small Copy link button (app2.css ~2578-2602).
4. Label "SETTINGS" above the accordion: `<h2 class="sec prop-phone-only">` exists on both main and branch (`_property_editor.html` ~line 138), shown below 1024 px by `.prop-phone-only{display:block}`. Check in the 390 shot why it is not visible on the branch (probably the new `.prop-after-strip`/`.form` wrapper or a rule hiding it); fix only by CSS or by moving it, never by deleting it.
5. (owed from 0977 review) Calendars accordion, expanded feed "URL" box (`.feed-url-details`, `.feed-url-value`, `_property_calendars.html`, block "0984 connection states" in app2.css ~2789-2797): the URL text touches the box's left edge and the caret touches the word "URL".

Branch hooks to KEEP (they carry behaviour or tests):
- `_property_editor.html`: the whole `<div class="prop-after-strip">` block with `.setup-continue-card` (`wizard.continue_card*`, `setup_guide.hide`/`show` form, `setup_progress.*`), `leon_card`, the hidden readiness block, `section_missing` macro and `data-missing` notes, `#lock-setup-state`, `#lock-connected-off`, `#lock-unavailable`, `.prop-archive-row`, `class="form prop-form-single property-detail"`, `data-strip`/`data-state` attributes on tiles, `id="overview-guest-url"` copy button.
- `_property_calendars.html` feed `<details class="feed-url-details">` markup.
- `copy_settings_dialog` include (the "copy settings" action in the header).
- app2.css: `.setup-continue-card` rules (~961-965, ~1025), `.prop-after-strip` (~2604-2606), `.lock-state` rules, tile focus rule (~2582) and tile state-colour rules (identical on main).

## 3. Files
- `App/app/templates/apartment_form.html`
- `App/app/static/app2.css`
- `App/app/templates/_property_calendars.html` (only if a class must be added; prefer CSS only)
- `App/app/templates/base.html` (cache key), `App/tests/static_versions.json` (generated)
- `docs/design/catalog.json` (any new class), `docs/context/decisions.md` (one line), `docs/tasks/0986-report.md`, `docs/tasks/screenshots-0986/`
- Tests listed in step 7 (pins only).

## 4. Steps
1. `git fetch origin main codex/ux-remediation-handoff 2>&1 | tail -3; git checkout -B codex/ux-remediation-handoff origin/codex/ux-remediation-handoff 2>&1 | tail -3`.
2. Header, template. Print main's header: `git show origin/main:App/app/templates/apartment_form.html | sed -n 5,12p` and `| sed -n 24,32p`. In `apartment_form.html` make the editing page use main's header again:
   - `{% block page_title %}{% endblock %}` and `{% block meta %}{% endblock %}` as on main (empty, so `.ui-ph` is hidden); remove the branch's `block secondary_actions` and `block ph_back`; `back_url` and `back_label` blocks exactly as main (`{% if not editing %}/apartments{% endif %}`).
   - In the editing branch (`{% else %}`) restore main's lines: `{% set base_url ... %}`, the `header_actions` set (keeps `_copy_settings_dialog.html`), `{% with href='/apartments', title=apartment.internal_name, help=page_help('property'), actions=header_actions %}{% include "partials/settings_back_header.html" %}{% endwith %}`, the `prop_addr` set and `<div class="sub prop-phone-sub">`. Move `property_prefill`, `draft`, `copy_property_peers` sets back below `{% block body %}` as on main. Do not edit `partials/settings_back_header.html` (shared by other pages).
   - Check: `grep -nF "ph_back\|ui-ph" App/app/templates/apartment_form.html | tail -5` prints nothing.
3. Header, CSS ("?" inline). The partial emits the help as a sibling after the `<h1>` when it contains `page-help`. Main placed it inline with these rules (`git show origin/main:App/app/static/app2.css | sed -n 2257,2259p`). In `app2.css` replace the branch rules at ~1845-1849 (`.airbnb-header:has(>.page-help-wrap)` grid block, including its 1023 px media line) with main's three rules, selectors widened to both classes: `.airbnb-header>.page-help,.airbnb-header>.page-help-wrap{margin:0}`; `.airbnb-header:has(>.page-help,>.page-help-wrap)>.airbnb-back{margin-right:calc(100% - 44px)}`; `.airbnb-header:has(>.page-help,>.page-help-wrap)>.airbnb-title{width:auto;flex:0 1 auto;min-width:0}`. If another page's geometry test then fails, scope the widened selectors to `.ui-page[data-body-kind="detail"]:has(#property-settings-form)` and say so in the report. Leave the `.ui-ph*` rules (~1855-1863, ~2609-2625) alone: other pages use them.
4. Tiles, CSS. Print main's rules: `git show origin/main:App/app/static/app2.css | sed -n 2455,2472p` and `sed -n 2480p`. In the branch `app2.css`, replace the `.prop-strip` rules at ~2578-2581, 2587-2594 and 2602 with main's: grid `repeat(2,minmax(0,1fr))`, `grid-auto-rows:1fr`, `gap:10px`; `.sc` (min-height 64px, padding 12px, radius 14px, column-gap 10px, row-gap 2px); `div.sc.sc-link{display:block;padding:12px}`; `b`/`small` with `line-height:1.3;overflow-wrap:anywhere`; `.sc-main`; `.sc-actions{margin-top:8px;padding-left:20px}`; `.sc-actions .btn{min-height:44px}`; `@media (max-width:359px)` one column. Take main's 640 px rule `@media (min-width:640px){... repeat(3,...)}` too (main shows three columns from 640 px). Keep branch lines ~2582-2586 (focus and state colours). Delete nothing else.
5. Setup card below the grid. The markup already sits in `.prop-after-strip` after the tiles. Make its look the tile style in `app2.css` next to the `.prop-after-strip` rules, no new class: `body.v2 .prop-after-strip .setup-continue-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;margin:0}` and make sure the card spans the same width as the grid (max-width 980px, already set). Keep its buttons as on the branch.
6. SETTINGS label and feed URL box. For item 4, open the 390 shot after step 8, fix by CSS. For item 5, in the "0984 connection states" block first read the rule that draws the box (`grep -n "feed-url" App/app/static/app2.css | cut -c1-200`); put `padding-left:16px;padding-right:16px` on the element that has the border/background, and `body.v2 .feed-url-details summary{gap:8px}` (summary is already `inline-flex`; if the caret is a `::marker` or `::before`, give it `margin-right:8px` instead). The URL text and caret must both sit 16 px from the box edge; gap URL-caret exactly 8 px.
7. Cache key and pins. `sed -i -E 's#(/static/app2\.css\?v=)[^"]*#\120261106-0986#' App/app/templates/base.html 2>&1 | tail -30`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` (never edit the json by hand). Find pins: `grep -rln "props-title-row\|page-help-wrap\|property-detail\|readiness" App/tests | head` and `grep -n "property" App/tests/v2_mockup.py | head`. Expected: tests that assert `.ui-ph` on the property page (test_0830, `partC-property-detail`, test_0534_property_page_v2) and `v2_mockup.py` widths/heights of `.prop-strip .sc` revert toward main values. Update a pin ONLY to the measured value, ONLY where this brief restored main's layout, with the comment `# 0986: main property layout restored`. Never weaken a geometry or lint assertion; never delete one.
8. Run the section 6 commands, look once at the four screenshots.
9. New CSS class: none expected. If one is added, put it in `docs/design/catalog.json` (`classes` list and `class_notes`). Append to `docs/context/decisions.md` in its existing format: `- [ui] 2026-11-06 [owner]: property page keeps main's header and tile grid; the setup progress card sits full width below the grid (0986).`
10. Copy `property-detail-configured-390.png`, `-768.png`, `-1280.png` and `property-detail-configured+open-390.png` from `/tmp/shots-0986/layout-lint/` into `docs/tasks/screenshots-0986/`. Write `docs/tasks/0986-report.md` (Status: review; one line per screenshot saying what you saw at 390: back button, "?" position, tiles even, card below, SETTINGS label, URL box padding). Set this brief to `Status: review`. Commit `0986: property page main header and tiles, setup card below, feed URL padding`, `git push -u origin codex/ux-remediation-handoff 2>&1 | tail -3` (no force, never main).

## 5. Do not touch
`partials/settings_back_header.html`, `host_page.html`, other pages' templates, `_property_editor.html` markup (except the SETTINGS label if CSS cannot fix it), any `App/app/*.py`, i18n files, any test assertion other than pins named in step 7.

## 6. Commands
From `App/`, each ending `2>&1 | tail -30`:
```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-0986 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x -rs
.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k propert -q --tb=short -rs
.venv/bin/python -m pytest tests/test_property_readiness.py tests/test_0534_property_page_v2.py tests/test_static_versions.py -q --tb=short
.venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_0541_property_page_phone_browser.py tests/test_property_navigation_browser.py -q --tb=short -rs
```
From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v ^WARN | tail -3` (OK) and `python3 scripts/design_lint.py | tail -3`.

## 7. Acceptance
- [ ] 390 px: round back button; "?" right after the name; tiles an even 2-column grid with equal rows; setup card full width below the tiles in tile style; "SETTINGS" label visible above the accordion
- [ ] Feed URL box: 16 px inner padding, 8 px gap between "URL" and caret
- [ ] all section 6 test commands: 0 failed, 0 skipped
- [ ] `context_lint` OK, `design_lint` OK, cache key `20261106-0986`, static_versions regenerated
- [ ] screenshots in `docs/tasks/screenshots-0986/`, report written

## 8. Stop and ask
- An anchor or main range does not match what this brief prints.
- A geometry or lint test fails twice, or only passes if an assertion is weakened.
- Restoring main's header breaks a non-property page.
- The tiles cannot be made even without changing markup.
At 25 tool calls: commit, write the report with `Status: blocked`, `Done: steps 1 to k. Left: steps k+1 to 10.`

## 9. Report
`docs/tasks/0986-report.md`, 600 tokens at most: files changed, last 5 lines of each command, section 7 ticked, per-screenshot sentence, pins changed (old, new), deviations, questions.
