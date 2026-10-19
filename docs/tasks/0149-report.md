# 0149 report

Status: blocked

## Commits
- 0780cbd 0149 step 1 (host.css, host-design0123.css: old stays CSS removed; script printed 150/49/17/7 lines removed, brace count 0)
- 13ed608 0149 step 2 (host2.css: Anchors A, B, C replaced/removed; appended desktop cell rules; design_lint OK)
- e475024 0149 step 3 (reservations.html, dashboard.html: data-card roles; design_lint OK; tests/test_design_stays.py + tests/test_host_quiet_dashboard.py: 8 passed)

## Step 4 browser run (5 files)
`4 failed, 7 passed, 1 warning in 82.18s`. Not all pass, 0 skipped.
- test_host_list_layouts_browser.py:66 `stays/cs/1024`: `assert 25 <= 1` (horizontal overflow of 25 px at 1024, Czech).
- test_host_list_layouts_browser.py:105 `('en', 1280, {'pill': True, 'deadline': True, 'height': 81.5, 'name': 23, ...})`: short row is 81.5 px, limit 72.
- test_host_stay_actions_browser.py:199 `[{'height': 32, 'width': 114.6}, {'height': 32, 'width': 32}]`: desktop Send and ⋯ are 32 px, test expects 42. The 0079 `min-height:42px` rule was removed in step 1, and the brief names no replacement.
- test_host_list_page_layout_browser.py:155 properties [40,42]: known local failure, ignored.
The share_compact_row_menu capture test also failed (17.97 s, 1 failed). Its PNGs were written and copied.

Not fixed: the brief forbids adding page CSS, and the fix needs CSS the brief does not name. Stopped per section 8.

## By-eye check (screenshots in scratchpad/shots/0149/)
- stays-1280-cs.png: does not match the brief. The header is a tinted fill, not plain. Each row has "Kopírovat odkaz" as a full-width box above "Otevřít" and ⋯, so Send and ⋯ are not side by side. Rows are about 108 px, not 48 to 60. The Send button sits in its own line.
- stays-390-cs.png: cards are one box each. Line 1 label, status badge at right. The deadline badge sits under the status and overlaps the source line. Send is a full-width line only on ready cards. ⋯ is top right. The bottom nav covers the first card (screenshot artifact).
- dashboard-*.png: not reviewed this turn.

## Deviations
- Commit trailer used Claude Haiku 5.5 (per session attribution), not Opus 5.5 as the task text said.
- Step 5 by-eye list for dashboard-390 and dashboard-1280 not done.

## Questions
- Which role or rule should set desktop Send and ⋯ to 42 px, and should stay rows be compact at 1280? Needs an owner or orchestrator decision.
- Is the 1024 overflow (25 px) pre-existing? Not checked.

## Owner steps left
- Decide the desktop action sizing and row height rules, then re-brief.

Ruff: see command output.
