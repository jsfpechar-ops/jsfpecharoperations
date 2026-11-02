# 0862: v2 shell: env badge and neighbours keep a 12 px gap, with a test

Status: todo
Depends on: 0705 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Josef (14:38): the MOCK / production tag (`.env-badge.ui-env` in `App/app/templates/_shell_v2.html`) is too close to the search pill and the account card. Screenshot `/mnt/project-files/records-pages/stay_fees-1280.png`: the badge touches the account card (`.side .org`), which sits right above `.search`. Fix it once in the shared v2 shell so every v2 page gets it: at least 12 px between every two vertically neighbouring blocks at the top of the sidebar (`.ui-brand`, `.env-badge`, `.org`, `button.search`, `nav.side-nav`), and the same 12 px rule between neighbouring elements wherever the badge, search or account appear in the tablet rail (768-1023) and phone top bar (< 768), if they appear there. Add a geometry test so this cannot come back.

Also (Josef 14:38, "decide either help mail or help button"): the sidebar bottom shows both the Help link (`/guide`) and a "Help & support" mailto block (`a.nav.support-link`, `_shell_v2.html` line ~34). Keep the Help button; delete the `support-link` line from `_shell_v2.html` only (the address stays reachable in the Havel support panel `_havel_support.html` and in Settings). Remove its now-unused CSS rules in app2.css and update any test that asserts `.support-link` in the v2 shell (comment "v2, 0862: one help entry"); keep the 12 px gap rule for the bottom blocks (Help, account `.me`, Log out) too.

## 2. Context

CSS: `App/app/static/app2.css` line ~223 `.side .env-badge{...margin:0 8px...}`; `.side .org`, `.side .search` rules nearby. `_shell_v2.html` has inline `style="...margin-bottom:14px..."` on the search button; move spacing to CSS only if needed. Tests: `App/tests/test_0705_v2_shell_browser.py` (fixtures and page opening already there). Josef's geometry rules (brief 0775): >= 12 px between text and buttons and between buttons.

## 3. Files

`App/app/static/app2.css` (new block `/* 0862 shell top gaps (start/end) */`), `App/app/templates/_shell_v2.html` (only to remove an inline margin you replace), `App/tests/test_0705_v2_shell_browser.py` (new test), tests asserting `.support-link` in the v2 shell (update only). Do NOT edit `base.html` or `static_versions.json`: another run changes the cache key; the orchestrator bumps it.

## 4. Steps

1. New test `test_shell_top_blocks_keep_12px_gaps`: on `/` and `/stay-fees` at 320, 390, 768, 1024, 1280, 1440, for each visible pair of neighbouring elements among brand, env badge, account card, search, nav (in the sidebar, rail or top bar, whichever is visible), assert vertical gap >= 12 px when stacked, horizontal gap >= 12 px when side by side, and no overlap. The test must fail before the fix (run it first).
2. Fix the CSS, rerun.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0705_v2_shell_browser.py tests/test_shell_lane_browser.py tests/test_design_shell_browser.py -q -rs --tb=short`

## 7. Acceptance

- [ ] New test fails before, passes after.
- [ ] The command: 0 failed, 0 skipped (the static-versions test may fail only because the cache key is not bumped; say so).

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 25 tool calls.

## 9. Report

`docs/tasks/0862-report.md`, 150 tokens at most. Do not commit or push.
