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

## Run 2
Status: blocked

- Step 4 (cache key): `app2.css?v=20261106-0988` in base.html; static_versions.json regenerated (51 files); test_static_versions.py: 3 passed. Commit c82789c0.
- Part A (entity card buttons): not fixed. Measured at 390 px on /entities (wide_host fixture), main and branch give identical boxes: first `td.row-actions` at y 592 to 644, previous `td.num` at y 565 to 592, tr fixed height 230px (content 228), no overflow, no overlap. Cause not reproduced, so no CSS change was made. Scratch test and worktree removed.
- Coordinator item: `test_direct_fee_backlinks_align_with_page_lane` locator restored to main's line 767 (`.page-header, .ui-ph, .head, .crumb, main h1`). The timeout is gone, but the assertion at line 771 now fails: `section.x + width` 971 > header right edge 804 + 2. Cause not analysed: the header matched is main's element, and the fee section is wider. Owner or the UX thread must decide whether the layout or the pin is wrong. Assertion not weakened.
- Section 6:
  - ruff (E9,F63,F7,F82,F401,F841): All checks passed.
  - non-browser `pytest tests --ignore-glob=*browser*` -x: 1 failed, 398 passed, stopped at `tests/test_ares.py::test_entities_fill_does_not_save` (not a file this brief touches; stopped per brief §8).
  - browser trio (layout_lint, 0786, host_property_controls): 62 passed, 0 failed, 0 skipped.
  - test_0710 subset (`propert or overview or stays or settings or operator`): 13 failed, 51 passed. Failures: `page-help-more` tap target 31x96 (min 44) and "main content ends under the tab bar" on stays at 390 and 768 px, among others. Likely from part B (page help beside the H1). Not fixed; list pending the rerun below.
  - design_lint: OK. context_lint: OK.
- Screenshots: not copied yet (the 0710 rerun was still in progress when the cap was reached); docs/tasks/screenshots-0988/ does not exist.

## Owner / coordinator steps left
- Decide the fee backlinks alignment (line 771) and the 0710 `page-help-more` / stays failures.
- Test ares failure: check whether it fails on main.
- Part A still open.
- Status stays blocked; no PR opened.

## CI after 0989 (orchestrator, head f22f287e, browser shards; shard 4 pending)

Shard 1: 9 failed / 360. Shard 2: 9 failed / 430. Shard 3: 1 failed / 230. Failing tests (likely from 0986-0988: alert "Open the stay" on compact pages, lock off row, property header and save bar):
- test_many_alerts_keep_every_deadline_and_fold_only_non_filing; test_one_alert_is_large_on_stays_and_compact_elsewhere (0987 D: `compact_page` dropped)
- test_status_block_fits_and_shows_its_state[off-390/768/1280] (0987 lock: connected+off now shows Turn on)
- test_0833_property_editor_help_headings_and_width; test_property_rail_and_back_links_ask_and_cards_into_settings_do_not; test_property_settings_save_discard_stay[en/cs, 360/1280] (0986 header)
- test_speed_pages_geometry[invoice-form-320/390/768]
- test_keyboard_focus_is_visible_and_not_covered; test_without_javascript_nothing_changes; test_every_page_passes_the_page_checks; test_keyboard_only_flow
- test_direct_fee_backlinks_align_with_page_lane (section wider than header)
Plus the 0710 stays page-help tap target from run 2. Next chat: one brief, fix markup/CSS to the owner's decisions, update only pins that encode the rejected PR design.
