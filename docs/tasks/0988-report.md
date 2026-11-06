# 0988 report

Status: blocked

## Done
- Step 1: local branch reset to origin/codex/ux-remediation-handoff (1da9c244).
- Step 2 (part B), commit aed726d7: partial `settings_back_header.html` renders `.airbnb-title-row` with the H1 and the page help beside it when help is a page help; CSS (3 rules in app2.css); test selector `.airbnb-title-row > .page-help-wrap .page-help > summary` added; catalog.json classes and class_notes.
- Deviation: the first run of test_0786 gave 6 failed, 42 passed. All 6 were "page help body not found open". Cause: the body locator `.page-help-wrap:has(details.page-help[open]) > .page-help-body` cannot match, because `.page-help-body` sits inside `details`. Fixed by `>` to a descendant combinator in that one locator. No assertion changed. Owner should confirm.
- test_0786_settings_geometry_browser.py: 48 passed, 0 failed, 0 skipped.

## Left
- Part A (entity card buttons): cause not found. `entities.html` row markup and the entity td/row-actions CSS rules are identical to main. The app2/admin2/host2 diff shows no td/row-actions change. Next: computed-style comparison of `td.row-actions` and its previous sibling at 390 px, main vs branch (brief §2).
- Step 4: cache key `20261106-0988` in base.html and static_versions.json (app2.css changed in part B).
- Step 5: section 6 commands, not run. Screenshots not copied.
- Section 7 not ticked.

## Owner steps
- Confirm the test_0972 locator change above.
