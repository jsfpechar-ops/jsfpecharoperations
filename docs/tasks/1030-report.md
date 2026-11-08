# 1030 report

Status: blocked

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
