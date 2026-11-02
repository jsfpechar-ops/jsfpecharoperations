# 0814 report (executor, Haiku 5.5)

Status: blocked (sections 1-9 partly done; section 10 not done)

## Changed
- `App/app/static/app2.css`: 0812 block rewritten (`.help-tip` inline-flex, flex none, margin-left 6px; `.help-tip-btn` 24x24 desktop / 44x44 below 1024 px with -3px / -13px margins, transparent, no border, visible 18 px circle from `::after` with z-index -1; wrappers `.heading-with-tip`, `.prop-name-tip`, `.havel-name-tip` flex nowrap gap 6px; `.head > div:has(> .havel-name-tip)` row rule). `.prop-new .heading-with-tip` gap 8px changed to 6px.
- Step b: no other size rule in app2.css beats the new one. Kept `body.v2 details .help-tip-btn` (l.385), stay-detail (l.602/606) and details hide rule (l.944). host2.css:556 (`.host-workspace .help-tip-btn` 24px) has lower specificity, so it loses.
- `App/tests/test_0800_v2_remaining_pages_browser.py`: new `test_help_tip_is_small_and_inline` (one test per ROUTES row, all WIDTHS): circle <= 20 px via `getComputedStyle(btn,'::after')`, centre within 4 px of the label line, gap after label 0 to 12 px. Test was not run against the pre-fix CSS (I edited CSS before running the test), so "fails on current state" is not confirmed.
- Step d: no existing assertion required 44 px help buttons; old checks are bounding-box inside-viewport only. No change.

## Commands (last lines)
- `pytest test_0800... test_onboarding_wizard... test_property_create... -q`: 23 failed, 196 passed (before the havel and test-label fixes). Failing: test_v2_remaining_page[property-new-1024/1280/1440, havel-*], 10 of the new test cases, test_onboarding_wizard_browser::test_choice_card_selects_from_anywhere[390-False-en/cs/vi] (clicks card edge, `input[value=immediate]` not checked; not investigated, may predate this change).
- `-k "help_tip_is_small or havel or property-new"`: 13 failed, 18 passed. Findings: 320 px labels wrap and the "?" sits on a new line (vertical offset 11-48 px) for "Where is your property?", "Import from Booking or Airbnb", "Cleaning date", "Create sharing link"; `havel` at 1024 px vertical offset 5.5 px; `property-new` gap 14 px at 320 px.
- Screenshots: `UBYHOST_SHOTS_0800=1 ... -k "property-new-390 or havel-1280"`: 3 passed. Written: `docs/tasks/screenshots-0800/property-new-390.png`, `havel-1280.png`. Not viewed.
- `python3 scripts/design_lint.py`: OK.

## Deviations
- Coordinator note changed the design to 24/44 px tap box with ::after circle; applied.
- Test for the pre-fix state not run (see above).
- Section 10 (h-k) not done: no time left under the 30-call cap.

## Questions / owner steps
- The 320 px wrapping labels need a layout decision beyond CSS (label + "?" wrap to their own line); stop per brief section 8.
- The test file `tests/test_0800_v2_remaining_pages_browser.py` changed on disk during my run (someone else edited it); I edited on top of that version.
- Not committed (per orchestrator).

## Round 2 (tip wrapping)

Status: blocked (30-call cap reached; help-tip tests still red, section 10 not touched, as scoped)

Changed:
- `App/app/static/app2.css`, `/* 0812 help tip (v2) */` block only: `.heading-with-tip`, `.prop-name-tip`, `.havel-name-tip` and `.prop-new .heading-with-tip` now `display:block` (was flex, so a long label wrapped and the "?" went to the far right or onto its own line); their text children `display:inline;vertical-align:middle`. `.help-tip` unchanged (inline-flex, middle, 6 px).
- `App/tests/test_0800_v2_remaining_pages_browser.py`, `_HELP_TIP_SIZE_JS` only: the label is now the last visible text node of the label (TreeWalker, tip body skipped), not the element's client rects (those included input boxes and the tip itself). The 0814 round-1 check is otherwise unchanged (<= 4 px vertical, 0-12 px gap).
- No template change (cleaning/havel markup not moved yet).

Result, last run: `pytest tests/test_0800_v2_remaining_pages_browser.py -k help_tip_is_small -q`: 11 failed, 4 passed. Last tail:
- `cleaning-new` ("Cleaning date", "Cleaning notes"): the "?" sits after the whole `.ui-field` block (vertical offset 26-90 px, negative gap). Needs the tip moved into the label row in `cleaning_edit.html` (template markup only, not done).
- `cleaning-shares`: "Create sharing link" is a button; the "?" follows the button, not its text (gap -178 to -378 px at 320-768). "Share schedule" at 1024+ offset 44 px. Needs a layout decision (brief 8).
- `havel` 1024-1440: vertical offset 6.6 px (the flex `.head>div` row centres the tip on the h1 box, not its glyph box).
- Other failures (`property-new`, `setup-*`, `guest-guide`, `guide`) were not re-read after the block change; not confirmed.

Not run: the whole 0800 file, screenshots, design_lint.
Not committed (per brief).

## Round 2 (add property)

Executor: Haiku 5.5, same brief, sections 10 h-k and 11 (choice_card).

### Changed
- `App/app/static/app2.css` 0800 block: `.prop-new .copy-settings-bar` is a left-aligned flex row (gap 12 px, overrides host2 `justify-content:flex-end`); on phone the copy button is `width:auto` (was 100%); `.prop-new .property-create-actions` margin-top 14 px (Cancel gap, was 6 px).
- `App/app/static/app2.css` 0801 block: `@media (max-width:1023px){.wiz-page .ui-choice-card>.help-tip .help-tip-btn{margin:0}}`. Cause of choice_card[390-False-*] failure: the 0812 phone `margin:-13px` on the tip button put its 44 px box over the card's left edge (x+6), so the tap hit the tip, not the card label. Pre-0814 commit (f1385c64, checked with a temporary worktree, removed) passed.
- `App/app/templates/_property_create.html`: removed the `required-legend` line.
- `App/app/templates/apartment_form.html`: the page-title tip now holds `lede ~ ' ' ~ common.required_legend`.
- `App/app/templates/guide.html` line 12: `<p class="sub">` removed; `help_tip('guide-lede-help', guide.lede)` next to the h1 in `.heading-with-tip`.
- Item i: "Start with the basics..." was already only inside the title tip (no visible subtitle to remove).

### Results
- `pytest tests/test_onboarding_wizard_browser.py -k choice_card`: 15 passed.
- `pytest tests/test_property_create_browser.py`: 13 passed.
- Final set (`test_property_create_browser.py tests/test_onboarding_wizard_browser.py tests/test_0800_v2_remaining_pages_browser.py -k "not help_tip_is_small" -q`): 6 failed, 198 passed, 15 deselected.
  - Failing: test_v2_remaining_page[property-new-320/390/768], [guide-320/390/768]. Message: "overlapping text ... 'Add property' and '?'" / "'Help & guide' and '?'".
  - Cause: the 0812 phone rule `body.v2 .help-tip-btn{margin:-13px}` (app2.css 0812 block) pulls the 44 px tip box left over the title text, because `.help-tip` has margin-left 6px. Not in my scope (help-tip block, other executor). Suggested fix for that executor: phone `margin:-13px -13px -13px 0` (no negative left margin).
- Screenshots: `UBYHOST_SHOTS_0800=1` run for property-new-390 and guide-390, see docs/tasks/screenshots-0800/ (not viewed).

### Deviations
- Brief said HEAD~3 for the pre-0814 worktree. Checked: HEAD~2 (f1385c64) is the parent of the first 0814 code commit (63eb8f5e), so the worktree used HEAD~2.
- Item h: the "How does this work?" pill in the yellow banner above the title is not on the copy row (it belongs to the global banner, outside this scope). Only the copy button was aligned: left, own row, natural width.
- Item j: 8 px came from the `.property-create-actions` margin 6 px (the card margin-bottom 14 px did not win). Fixed by 14 px; not re-probed with computed style, the 0813 neighbour test passes for property-new at 1024/1280/1440.

### Owner steps left
- None. Not committed (orchestrator commits).

## Round 3

Status: blocked (12 of 121 help-tip cases red in the whole 0800 file; one conflict needs an owner/orchestrator decision)

Changed:
- `App/app/templates/cleaning_edit.html`: "Cleaning date" tip moved from the timing paragraph into the `clean-date` label; "Cleaning notes" tip moved into the `clean-notes` label (after the text).
- `App/app/templates/cleaning_shares.html`: "Share schedule" tip moved inside the h1, after the text.
- `App/app/templates/havel.html`: tip moved inside the h1 (the `.havel-name-tip` span wrapper removed).
- `App/app/static/app2.css`, `/* 0812 help tip (v2) */` block only: removed the `.head>div:has(>.havel-name-tip)` flex rule; phone `.help-tip-btn` margin now `-13px -13px -13px 0` (coordinator note); new `.cl-v2-shares .cleaning-actions` phone row rule (button `width:auto`, tip beside it) and `.cl-v2-shares .cleaning-actions>.help-tip{margin-left:0}`.
- `App/tests/test_0800_v2_remaining_pages_browser.py`, `_HELP_TIP_SIZE_JS` only: a tip inside a LABEL/H1/H2 is measured against that element; a "?" after a button or `.ui-btn` is measured against the button box (centre diff <= 4 px, gap 6-12 px).
- Not touched: apartment_form.html, _property_create.html, guide.html (guide subtitle), 0800/0801 blocks, field_label macro.

Commands (last lines):
- `pytest tests/test_0800_v2_remaining_pages_browser.py -q` (whole file): `12 failed, 109 passed in 210.23s`. Red: property-new, onboarding, setup-property, setup-calendar, setup-police, setup-guest-link, setup-stay-fee, guest-guide, guide, havel, cleaning-new, cleaning-shares.

Conflict (decision needed):
- At phone width the 44 px tap box must overlap the label by about 7 px for the "?" circle to sit within 6-12 px of the label (circle = box left + 13). The coordinator's margin `-13px -13px -13px 0` keeps the box clear of the title but puts the circle 19 px after the label, so the 0-12 gap check fails on havel, cleaning-new, cleaning-shares (19-25 px) and onboarding (21.8 px). The earlier `-13px` (all sides) passed the gap check and failed the overlap check. Choose one: relax the gap check on phone to <= 20 px, or accept the tap-box overlap.

Still red, not fixed (outside this brief's files or shared code):
- property-new: Add property, other executor's files.
- guide: the tip sits after the h1 in guide.html; fixing it means editing guide.html, which is the guide subtitle the other executor owns.
- setup-property, setup-calendar, setup-police, setup-guest-link, setup-stay-fee, guest-guide: the tips come from the shared `field_label` macro (`_components.html`, wraps label + tip in `.field-label-row`) and from `guest_guide.html`'s import section. Moving the tip into the label means changing the macro for every page, so not done without an owner decision.

Not committed (per brief). No screenshots taken this round.
