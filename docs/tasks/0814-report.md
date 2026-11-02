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
