# 0833 report

Status: review
Branch: claude/project-thread-wkaqmz (not committed, per owner instruction)

Files changed: App/app/static/app2.css (block "0833 property editor (v2)" appended), App/app/templates/_property_editor.html (Basic details h2 removed; "<small>" subtitle removed from the 9 prop-sec summaries, .sec-state kept), App/tests/test_0833_property_editor_browser.py (new). Diff stat:  2 files changed, 25 insertions(+), 10 deletions(-)

Tests: cd App && .venv/bin/python -m pytest tests/test_0833_property_editor_browser.py tests/test_0830_airbnb_pages_browser.py -q --tb=short -rs
Last lines:
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 114.96s (0:01:54)

Also run: tests/test_property_navigation_browser.py: 1 failed, 11 passed. test_tabs_hashes_drafts_history_and_validation_in_browser fails on the base branch too (checked with app2.css and _property_editor.html stashed), so it is not caused by 0833.

Deviations:
- Brief §6, §7, §8 do not exist in the brief; read the "Tests" and "Do" sections instead.
- Help "?" is 24 px (0830 audit needs 24 px tap target and 12 px min font); still inside the 16-26 px range.
- At 1024+ the name field (#internal_name) spans both columns. Two columns alone gave 307 px at 1280, below the 400 px target.
- Kept "Stay fee (poplatek z pobytu)" h2 (not identical to summary "Stay fee"). Kept "Police reporting", "Digital door lock", "Guest links" (different titles).
- Test excludes .sec-state from the subtitle check (it is a direct child small of summary, so the brief selector would have matched it).
- i18n keys not deleted (still used by the sec-state text and elsewhere).

Questions: Should "Stay fee (poplatek z pobytu)" h2 be removed as a repeat? Should .sec-state repeat the subtitle text on Archive and Messages?
Owner steps left: review, then commit and open PR. Screenshots (390, 768, 1280) are in the scratchpad at /tmp/claude-0/-home-claude-jsfpecharoperations/d977c0e2-51d8-58fe-b258-6dc66c596307/scratchpad/shots-0833/
