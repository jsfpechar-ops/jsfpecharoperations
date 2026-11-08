# 1030 report

Status: blocked (one test red, see Finish pass)

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
