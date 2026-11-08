# 1030 report

Status: review

## Steps
- Steps 1 to 4: done. Step 4 test file green: `tests/test_property_*.py tests/test_*_i18n.py tests/test_no_em_dashes.py` gives `229 passed, 1 warning` (earlier run `230 passed` in step 5 run), 0 skipped.
- Step 5: PARTIAL. Committed: at >=768 the per-section missing lists are hidden (`.prop-sec-missing .readiness-list`); the fix line replaces them. Tests `tests/test_property_*.py tests/test_*_i18n.py tests/test_flash_literals.py` give `230 passed, 1 warning`, 0 skipped. NOT done: "?" pruning. Current help icons in `App/app/templates/_property_editor.html`: `help_tip(` at lines 226, 251, 257 (messages, 3), 344 (police, 1), 478 (lock, 1); `field_label(... help ...)` calls add more icons per section (basics, fee, police) and need a rendered count. Also no `.field-error` hiding (class name not confirmed).
- Steps 6 to 8: not started as separate steps. Step 6 pins already changed inline (see Deviations). Step 7 (cache keys in base.html and static_versions.json) not done. Step 8 (layout lint, screenshots) not done.

## Deviations (all pins dated 2026-11-08 in comments)
- `test_design_guardrails_browser.py`: wait for section dots instead of the hidden strip.
- `test_property_navigation_browser.py`: sections chosen via `.prop-nav` before hidden fields are used; strip clicks moved to `.prop-nav`; URL check accepts the hash; sidebar rail check accepts `.prop-nav`; keyboard pill test runs at 390 px.
- `test_property_preview_sticky_browser.py`: strip checks only below 768 px; at >=768 the section list is checked.
- JS: nav ignores modified clicks; apply() prefers the server-open section over the first one when no hash.

## Questions
1. Step 5: approve removing the "?" from basics, fee and police field labels where the text duplicates the label (owner's "less is more"), or list which help texts to keep.
2. Step 5: which class holds the per-field "X is required." text? Not found yet.

## Owner steps left
Continue at step 5 (help pruning), then step 7 (cache keys), then step 8 (layout lint, 390/768/1280 screenshots to /mnt/project-files/ux-shots/editor-redesign/). The PR is not opened by the executor; open it from `claude/editor-redesign`.

## Finish pass (orchestrator subagent, 2026-11-08)
- Two-column nav + card only at >=1280; 768 to 1279 shows the section list as left-aligned chips above one column (bookings 1024 overflow gone).
- Stray "." under the card title: not reproducible after 58fe6d52 (probe of all ::before/::after/::marker under #sec-basics shows only empty content).
- 768 layout lint: green (4 passed), no allowlist entry added.
- Fix line: names come from the readiness item (data-fix-label), so no help text or star. Real save with blank House number and Postcode gives "Fix 2 fields: House number, Stays arriving (calendar or manual)"; Postcode has no readiness item of its own.
- Also: empty grey missing box and 32 px gap above the card removed; editor aligned with the page title at >=1280; a load without a hash no longer scrolls past the title; keys app2.css 1030g, app.js 1030e.
- Tests: 303 passed, 1 failed (`test_property_page_buttons_browser.py:112` "the help bubble covers Save"); layout lint 4 passed. 0 skipped.
- Open: fix that test; the "SETTINGS" eyebrow above the card at 768 is still visible (not `.prop-phone-only`).
- Shots: /mnt/project-files/ux-shots/editor-redesign/editor-{390,768,1280,1280-fixline,1280-stayfee}-v2.png

## Finish pass 2 (2026-11-08)
- Help bubble covered Save at 1280: caused by the wider 1280 editor (right edge under the fixed bubble). Fix: editor max-width min(1000px, 100% - 64px). Test unchanged, green.
- "SETTINGS" eyebrow at >=768 was `h2.sec.prop-phone-only` inside the form, kept visible by a more specific rule; hidden at >=768.
- Fix line after a failed save names every invalid or blank required field by its clean label, then any server missing item not covered by those fields. Example: "Fix 5 fields: House number (č. popisné), Postcode, Variable symbol (from the council), Council account, Stays arriving (calendar or manual)". New test `tests/test_property_fixline_browser.py`.
- Keys: app2.css 1030h, app.js 1030f.
- Tests: required set 305 passed, 0 skipped; layout lint 4 passed. context_lint OK.
- Shots: /mnt/project-files/ux-shots/editor-redesign/editor-{390,768,1280,1280-fixline,1280-stayfee}-v3.png

## Finish pass 3: 6 pills as switcher (owner decision 2026-11-08)
- At >=768 the six status pills (nav.prop-strip) are back and are the section switcher: a pill click or Enter/Space shows that one section, writes the hash, sets aria-current and highlights the pill. Guest link's main area opens Automatic messages; its Copy link button keeps its own action. All six sections are covered, so there is no 7th link.
- The left section list (.prop-nav) never shows; the Continue setup box stays hidden at >=768.
- Layout at >=768: title, pills (3 per row at 768, 1024 and 1280), fix line, one card in a single 16 px-gap column. At >=1024 pills and editor start under the title, max width min(1000px, 100% - 64px).
- The older keyboard handler on `a[href^="#sec-"]` prevented the click at wide widths; it now clicks the pill there.
- Test pins updated to "6 pills as switcher": navigation (pill clicks, strip checks at 390/768/1280/1440, keyboard test at 390 and 1280), preview_sticky (strip visible at every width, .prop-nav hidden), guardrails (waits for the strip again).
- Keys: app2.css 1030k, app.js 1030h.
- Tests: required set 305 passed, 0 skipped; layout lint 4 passed. No overflow at 768/1024/1280.
- Shots: /mnt/project-files/ux-shots/editor-redesign/editor-{768,1280,1280-fixline,1280-stayfee}-v4.png (390 unchanged: editor-390-v3.png)

## Merge with main and Stay fee wide fix (2026-11-08)
- Merged origin/main (merge commit, no rebase). Kept both sides: 1030 layout plus #817's "Applies from" field and its CSS. main has its own docs/tasks/1030-report.md (walg task), so this report moved to docs/tasks/1030-editor-redesign-report.md and the brief points here.
- Pins (owner decision 2026-11-08, 6 pills as switcher): test_stay_fee_rate_field_1029.py selects Stay fee by its pill at >=768; test_0710 mockup match accepts the wide card header (light divider; no h2.sec, .sec-state, .dot at >=768) via WIDE_OVERRIDES and WIDE_MISSING_OK in tests/v2_mockup.py.
- Stay fee at 1280 to 1800: reproduced (a long council name and a wide saved signature pushed inputs, the signature and "2. Pay the council" past the card; More details sat 16 px in from the fields). Not fixed by main. Fixed at >=1024 only: shrinkable grid tracks, min-width:0 on the signature fieldset, the image capped at 100%, More details and Signature as plain blocks on the field left edge. New test tests/test_stay_fee_section_wide_1032_browser.py (1280/1440/1600/1800). 390/768 unchanged.
- Keys: app2.css 1032b, app.js 1030i.
- Shots: /mnt/project-files/ux-shots/editor-redesign/stay-fee-{1440,1800}-v5.png
- Saved signature: shown whole at every width (max-height 160 px, max-width 100%, aspect kept, object-fit contain); the Edit pad draws a saved signature scaled to fit instead of stretched (host.js). Stored format unchanged. Test `test_saved_signature_fits_whole_and_edit_redraws_it` (1440/1800, device scale 2, corner strokes, save, reload, Edit, redraw). Keys: app2.css 1032c, host.js 1032a.
- Shots: /mnt/project-files/ux-shots/editor-redesign/stay-fee-signature-{1440,1800}-v5.png
