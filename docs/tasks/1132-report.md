# 1132 report (executor: Haiku 5.5)

Status: blocked
Branch: claude/confident-cerf-0zow3i (no push, no PR)
Commits: 9af5dfda (step 1), 43d590f0 (step 2), 5fa3bbc1 (step 3), 580b532a (step 4), 6ffee98b (report), then this commit.

## Done
- Steps 1 to 4 as before. Decision A: env badge in the tablet rail shows the short "MOCK" (`.env-short`); full text from 1024 px. Decision B: test_0895 clicks `#app-sidebar .side-bottom a[href="/guide"]`. Decision C: app2.css bumped to `20261112-1132b` (tokens.css left at 1132a).

## Test commands (last line, App/)
- test_0895_sidebar_inert_heal_browser.py: `2 passed in 2.68s`. Skips 0.
- test_0705_v2_shell_browser.py: `9 passed in 4.67s`. Skips 0.
- test_layout_lint_browser.py: `4 passed in 235.91s (0:03:55)`. Skips 0.
- test_design_guardrails_browser.py + test_0710 (run separately, no -x for 0710): guardrails stopped at `1 failed in 30.63s`: `tap-target-small` guest-new 390 "Cancel" 43 px (needs 44). Not in the 1132 diff; not fixed (guest page is out of brief scope). 0710: `98 failed, 85 passed in 202.43s`; mostly `.side is 240 px wide, expected 220` (1024 to 1920 px).
- test_static_versions, test_wp07, test_design_*, test_host_i18n: `6 failed, 169 passed in 71.76s`. Seen: test_design_shell (`.tabs a.tab[href="/menu"]` at 820 px, tab bar now hidden 768 to 1023 as the brief asks, so the test is out of date); test_design_tokens (`--danger` defined twice in ROOT_BLOCK, tokens.css lines 42 and 155). Other failures not inspected.
- test_host_*.py + test_host_geometry.py: background run, last line: 

## UX gate (390 / 768 / 1280; full-page captures in App/data/shots/1132/gate/, not committed)
- `/`: 390 one column, bottom tab bar, no overflow. 768 88 px rail, "MOCK" short badge on one line, labels fit. 1280 240 px sidebar, full "MOCK · Nothing sent" badge, no wrap.
- `/reservations`: 390 chips wrap in two rows, cards readable. 768 rail as above, list cards fit. 1280 table fits, no horizontal scroll.
- Capture artifacts: fixed tab bar and rail background appear mid-page or stop at 900 px in full-page shots; not a layout defect.

## Deviations
- Done: steps 1 to 5 (decisions A to C), gate screenshots. Left: guest-new tap target (390), 0710 sidebar width (220 vs 240), test_design_shell tab-bar expectation, test_design_tokens --danger duplicate, host rows if still red.
- Gate screenshot script is in the scratchpad, not in the repo.

## Questions
1. Sidebar width: 240 px (current) or 220 px (0710 test)?
2. test_design_shell: update the expectation to "no tab bar 768 to 1023"?

## Owner steps left
None until the questions above are answered.
