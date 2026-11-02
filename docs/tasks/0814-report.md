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

## Round 4

Status: blocked (7 help-tip size cases still red in the 0800 file; host-help and endtoend red outside the §13 test list; see Deviations)

Changed:
- `App/app/static/app2.css`: phone `.help-tip-btn` margin `-13px -26px -13px 0`; phone `.help-tip-btn::after` `left:0;top:13px;transform:none`.
- `App/app/templates/_components.html`: `field_label` puts the help tip inside the `<label>`, after the text.
- `App/app/templates/guide.html`, `App/app/templates/apartment_form.html`: title tip moved inside the h1, after the text.
- `App/tests/test_0800_v2_remaining_pages_browser.py`: `_HELP_TIP_SIZE_JS` measures the visible circle from the `::after` offset and transform; `test_help_tip_sits_beside_its_label` helper measures the label's own text node and finds the label when the tip is inside it.

Commands (last lines):
- four-file run: `7 failed, 222 passed in 380.79s`. All 7 are `test_help_tip_is_small_and_inline`: property-new, setup-property, setup-calendar, setup-police, setup-guest-link, setup-stay-fee, guest-guide.
- `-k "label or help_tip or field"`: `11 failed, 277 passed, 2 skipped`. The 7 above, plus `test_endtoend.py::test_26`, plus `test_host_help_browser.py` at 360/390/1280.
- `-k sits_beside`: `8 passed`.
- 0800 file with shots: FAILED tests/test_0800_v2_remaining_pages_browser.py::test_help_tip_is_small_and_inline[setup-stay-fee]
FAILED tests/test_0800_v2_remaining_pages_browser.py::test_help_tip_is_small_and_inline[guest-guide]
7 failed, 114 passed in 215.18s (0:03:35)
- design_lint: design lint: OK

Deviations:
- `transform:none` added to the phone `::after` rule. Without it the translate(-50%,-50%) shifts the circle.
- Two test helpers edited (not named in §13) because the tip now sits inside the label.
- Not fixed, small-inline reds: property-new list tips (other executor's area). setup-calendar, setup-police, setup-guest-link, setup-stay-fee: the 18 px gap comes from `.field-label-row` h2 rows that do not use `field_label` (e.g. `_property_editor.html`, `setup_wizard/*.html`). Not verified in the DOM. guest-guide: the "Import from Booking or Airbnb" row in `guest_guide.html` (vertical 34.7 px, gap -237 px), not via the macro.
- host-help regression, not investigated: the title tip inside the h1 makes its popover overflow at 360/390 px (x 259/289 + 320). `addr_house_no-help` at 1280 px sits at x 1530. Likely caused by the macro or h1 move. Baseline not checked.
- endtoend test_26: `KeyError: 'id'` on the guest query. Not investigated; baseline not checked.

Questions / owner steps:
- Keep the h1 title-tip move if host-help overflow must be fixed first?
- For the h2 `.field-label-row` rows, is an 18 px gap acceptable, or should the gap check be widened?
- Nothing committed (per instructions). Owner steps: none.

## Round 5B

Status: review (one browser case still failing, see below). Not committed.

- Files changed: `App/app/static/app2.css` (0812 help-tip block: `@media (max-width:1023px)` narrow fixed popover, `@media (min-width:1024px)` `.help-tip-end` right alignment), `App/app/static/app.js` (help-tip `open()` toggles `help-tip-end` when the tip is right of the middle; `place()` skips inline width/left below 1024 px and right-aligns to the button when `help-tip-end`).
- Deviation: the spec's `right:0` alone cannot position a fixed popover, so `place()` computes `left = r.right - w` for end tips (the CSS rule is kept as specified).
- `tests/test_host_help_browser.py`: 5 passed, 1 failed (`[1280]`, property-create, `addr_house_no-help`: popover box x=1234.8, overflows 1280). HEAD JS/CSS run: 3 failed (360, 390, 1280), so the 360/390 failures are fixed by this round. The 1280 case may also depend on the in-progress template edits (5A); not investigated further.
- `tests/test_endtoend.py -k test_26`: failed in setup at `host_adds_guest(host, MANUAL_STAY["id"])`, `KeyError: 'id'` (MANUAL_STAY has no `id` key). Not a CSS/JS failure; not fixed.
- Owner/orchestrator: decide on the 1280 popover case and the test_26 fixture.

## Round 5A

Status: partial (templates done; 15A tests red until the app2.css step lands)

Files changed (templates only): `App/app/templates/_property_editor.html` (5 h2 rows: help_tip moved before `</h2>`), `App/app/templates/setup_wizard/police.html`, `App/app/templates/setup_wizard/guest_link.html`, `App/app/templates/_ui_layout.html` (`ui_section` gets `tip=''`, rendered after title inside h2), `App/app/templates/guest_guide.html` (import tip passed as `tip=import_tip`; two standalone help_tip lines removed), `App/app/templates/_property_create.html` ("After you create it" items: help_tip moved inside `<strong>`).

Tests (from App/, env PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1):
- `tests/test_0800_v2_remaining_pages_browser.py -k small_and_inline`: `7 failed, 8 passed, 106 deselected in 75.15s`. Failing: property-new, setup-property, setup-calendar, setup-police, setup-guest-link, setup-stay-fee, guest-guide. Cause: the "?" still sits below the label (e.g. guest-guide at 320 px: vertical offset 24.9 px, gap after label -237.7 px). The heading row is not yet a nowrap flex row and the 44 px circle rules are still in app2.css, which is the CSS step owned by the other executor.
- `tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py`: `98 passed in 163.48s`, 0 failed.

Left red: the 7 small_and_inline cases above. Re-run after the app2.css commit lands.

## Round 6

Status: blocked (guest-guide at 320 px still red; no commit made)

Files changed: App/app/templates/setup_wizard/_layout.html (a), App/app/templates/_components.html (b, macro trims), App/app/static/app2.css (b, 0812 block), App/app/templates/_property_create.html (c), App/app/static/app.js (d), App/app/templates/guest_guide.html (e).

- a: wizard_help block moved inside the h2. setup-* tests now pass.
- b: help_tip macro uses whitespace trim. `white-space:nowrap` was tried and removed because it caused the wizard_polish overflow (javascript off, 6 cases). Added `body.v2 :is(h1,h2,label):has(>.help-tip)` flex rule and `margin-left:0`.
- c: brief said one tip; three tips (create-next calendar, guests, reporting in _property_create.html) had no label element before them. Wrapped each label text in a span. Lock tip already passed.
- d: app.js place(): on desktop the body is absolute inside .help-tip, so left/top are now relative to the offset parent (was viewport coords). addr_house_no-help at 1280 passes.
- e: guest_guide.html import section now `{% if import_on %}`.

Test tails:
- Full section 16 set (before flex rule): `1 failed, 341 passed in 407.74s`. The only failure was guest-guide at 320 px, gap -237.7 px.
- After flex rule, `-k "guest-guide or property-new"`: `1 failed, 24 passed`. guest-guide at 320 px: gap after label 174.0 px. Still red.
- Not re-run after the flex rule: the full set. Other pages are unverified after the flex rule.

Deviations: nowrap removed (see b). Three tips in c, not one. Test runs rewrote about 239 screenshot PNGs under docs/tasks/ (screenshots-0410 and others), which show in git status. Not restored (restore is forbidden to me). Check before committing.
Left: guest-guide 320 px tip gap (label flex/tip placement); full set re-run; screenshots cleanup.

## Round 7

Status: review (no commit, no PR: the caller said not to commit or push)

Files changed (working tree only, not committed):
- App/app/static/app2.css: deleted the two `body.v2 :is(h1,h2,label):has(>.help-tip)` lines (17a). Added in the 0812 block `body.v2 .tip-nowrap{white-space:nowrap}`, `body.v2 .tip-nowrap .help-tip-body{white-space:normal}` and `body.v2 .ui-section-h>h2:has(>.help-tip){display:flex;align-items:last baseline}`.
- App/app/templates/_ui_layout.html: `ui_section` renders the title split on its last space when `tip` is set (17b). The last word is in `<span class="tip-nowrap">`, and the tip follows it directly inside the h2. Without a tip the markup is unchanged.

Test tails:
- §16 set (`test_0800_v2_remaining_pages_browser.py test_onboarding_wizard_browser.py test_property_create_browser.py test_host_help_browser.py test_guest_guide*.py`), first run after 17a+b with the tip inside the nowrap span: `1 failed, 284 passed, 57 skipped in 263.83s`. Failure: `test_help_tip_is_small_and_inline[guest-guide]`, "no label before it" at all widths.
- §16 set after the fix: `285 passed, 57 skipped in 255.28s (0:04:15)`. 0 failed.
- §17c `pytest tests -q -k "wizard_polish or label or help_tip or field"`: `1 failed, 287 passed, 14 skipped, 5331 deselected in 161.48s (0:02:41)`. Failure: `tests/test_endtoend.py::test_26_a_field_error_is_reported_back_as_correctable` (KeyError: 'id'), the known pre-existing red on main. Not touched.

Deviations:
- 17b markup changed: the tip is outside the `tip-nowrap` span, not inside it. The test's label check needs the tip's previous element sibling, or an H1/H2/LABEL parent, and a span wrapper defeats both. The glue is now the flex rule above, scoped to `.ui-section-h>h2` (not the broad rule round 6 removed).
- The 17b CSS for `.tip-nowrap .help-tip-body` is kept as written, though it no longer matches any element.
- No commit, no PR, no push (caller instruction). 17d and the static-version bump were not done.
- Skips: all 57 skips in the §16 set (and 14 in the §17c run) are reported by pytest as "browser not required" in test_onboarding_wizard_browser.py. I did not check the skip reasons for every file, so the executor's "0 skipped" rule is not confirmed for the whole set.
- Screenshots were not taken (no UI screenshot step in this brief).

Owner steps left: none for the executor. Orchestrator: decide on the test_26 red (pre-existing on main) and on the skip count before the 17d commit.
