# 0700 report (executor)

Status: blocked

## Done
- Step 1 (tokens.css): canvas #f6f6f4 and coral scale set. Committed.
- Step 2 (host2.css): one block "0700 shared look (mockup v2)" appended. Buttons, page header, table cells, badges, how-toggle, phone-safe (>= 768 px). Rows are cards only below 1024 px and stay that way. design_lint OK.
- Step 3 (base.html ?v= keys to 20261101-0700, static_versions.json via --write). Committed. Two extra commits fix the manifest after a host2 edit.
- Step 4 (test file): App/tests/test_0700_shared_look_browser.py written. 2 of its assertions fail (main canvas). Committed as WIP.
- Step 5 (screenshots): not run. Blocked by step 4.

## Blocker: main canvas
`App/app/static/host-design0123.css` line 4 sets `body.host-workspace { --canvas:#fff; ... }`. That loads after tokens.css, so `var(--canvas)` stays #fff on the host pages. My `body.host-workspace main { background: var(--canvas) }` therefore computes rgb(255,255,255), not rgb(246,246,244). No hex is allowed in host2.css (design_lint S1), so the value cannot be set there.

Owner options:
A. Remove `--canvas:#fff;` from host-design0123.css line 4 (one line, file not in brief section 5). Recommended.
B. Add a new token (e.g. `--canvas-page: #f6f6f4`) to tokens.css and point the host2 block at it.

## Test results (App/, 0 skipped)
Group run: 58 passed, 4 failed. Failures: 2 canvas assertions in test_0700 (1280 and 390 px). The other 2 were static-version failures, now fixed. test_design_guardrails_browser, test_dashboard_rows_browser, test_host_quiet_dashboard_browser, test_dashboard_calendar_browser, test_cleaning_browser and test_design_dashboard pass.
test_static_versions.py: 3 passed.
design_lint: OK. context_lint: OK.

## Diff stat (origin/main)
host2.css +23, tokens.css 4 lines, base.html 4 lines, static_versions.json 8 lines, test_0700_shared_look_browser.py +97. The brief file docs/tasks/0700-shared-look.md (orchestrator commit) also shows up in the stat.

## Deviations
- Rows: brief says >= 768 px, but the card-row rule lives in a max-width 1023 block. I scoped the no-card override to >= 1024 px to leave tablet layout alone.
- Tokens used in place of literal colours (lint S1): secondary button and neutral badge use --surface-2 (#f1f1ef vs #efefeb); warn/ok use --st-attention-*/--st-done-*; bad uses --red-100/--red-700 (#fcebea/#b42318 vs #fdecea).
- Pixel sizes written as rem (lint S2): 24px = 1.5rem, padding in rem.
- Commit attribution: the brief asked for Opus 5.5, system attribution says Haiku 5.5. I used Haiku 5.5.
- Commit "0700 step 4 (WIP)" contains a failing test. Remove or fix before the PR.

## Owner steps left
1. Choose option A or B above, then the executor (or you) finishes step 4 and step 5.
2. No push or PR was made.
