# 0316 report: Finding your way and Words we use

Status: review
Done: steps 1 to 10. Steps 1 to 7 as before; step 7 fixed by the orchestrator decisions below.

## Files changed
- App/app/guide_i18n.py (steps 2, 3; step 7 fix: 2 copy lines)
- App/app/templates/guide.html (steps 4, 5, 6: sections list, finding and glossary sections)
- App/tests/test_guide.py (step 7: section list)
- App/tests/test_design_guardrails_browser.py (step 8 added the /guide route; step 10 removed it again)
- App/tests/test_guide_browser.py (step 9, new)
- docs/tasks/screenshots-guide/guide-finding-390.png, guide-glossary-390.png (step 9)

## Commands (last lines)
- Step 7 fix, `pytest tests/test_guide.py -q --tb=short -x` -> `3 passed in 1.40s`
- Step 9, `pytest tests/test_guide_browser.py -q -rs` -> `2 passed in 5.66s` (0 skipped)
- Step 10, `pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs` -> `14 passed in 107.80s` (with the step 8 route; first run: `1 failed, 13 passed`, see Questions)
- Section 6 cmd 1, `pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x` -> `30 passed, 1 warning in 1.86s`
- Section 6 cmd 2, `pytest tests/test_guide_browser.py -q -rs` -> `2 passed in 4.68s`
- Section 6 cmd 4, `pytest tests/test_host_geometry.py -q -rs` -> `2 passed in 4.81s` (0 skipped)
- Section 6 cmd 5, `python3 scripts/context_lint.py` -> `context lint: OK` (warning only: 10 commits touched App/ after the last status.md update)

## Section 7
- [x] "Finding your way" and "Words we use" present in `/guide` (en, cs)
- [x] Both in the side navigation; `test_guide.py` lists both anchors
- [x] `GUIDE_STRINGS` en and cs have the same keys (test passes)
- [x] Screenshots saved (below); browser tests 0 skipped

## Deviations
- Orchestrator decision 1: English `guide.finding.how` now says "and a link back here." (was "and a link to this guide.", which trips the raw-key test).
- Orchestrator decision 2: Czech `guide.finding.computer3` now says "nahoře v menu ho skryje." (was "menu menu skryje.").
- Step 10: the step 8 guard route `"guide": "/guide"` was removed again (the a11y guard reported nav-no-current on the /guide bottom nav), as the brief says.
- Chromium: the brief path `/opt/pw-browsers/chromium-1194/...` does not exist here. Ran with `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`. No install was run.
- The browser test also writes screenshots for the existing sections (invoices, overview, settings, setup, stay_fee, stays). They are left untracked and not committed; only the two named in section 7 are committed.

## Questions
1. The a11y guard reports `nav-no-current` on the /guide bottom nav (`nav.ui-nav-bottom "Help"` / `"Nápověda"`, both languages, 1280 px). It is outside #finding and #glossary, so per step 10 I removed the guard route. Owner or next brief should decide whether to fix the nav current state.
2. The element screenshots show the fixed bottom nav covering the bottom line of the section (cut-off text at the bottom edge). It is a capture artifact of the fixed bar, not a layout bug in the section. Reviewer to confirm.

## Screenshots
- docs/tasks/screenshots-guide/guide-finding-390.png: "Finding your way" section at 390 px; headings and short lines read well; the bottom bar overlaps the last lines.
- docs/tasks/screenshots-guide/guide-glossary-390.png: "Words we use" at 390 px; eight-term table reads cleanly; the bottom bar overlaps the last term.

## Owner steps left
- Open `/guide` on your phone and on your computer. Read "Finding your way" and check each place it names.
- Read "Words we use". Say if a word is missing.
- Decide Question 1 (nav current state on /guide).
