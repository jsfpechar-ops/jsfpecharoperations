# 0827: Records pages: centre the empty state with the shell's own height (replaces the 0825 constants)

Status: todo
Depends on: 0825, 0826 (both uncommitted in the working tree) | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Same goal as brief 0825 (read its §1): the empty state sits in the middle of the free area on `/submissions`, `/invoices`, `/housebook`, `/stay-fees`. 0825 used hard-coded offsets (`calc(100dvh - 134px)`, `margin-bottom:-104px`) that run under the phone tab bar and miss on three pages. Replace the whole 0825 block with a flex chain that uses the shell's real height, no pixel constants.

## 2. Context

`App/app/static/app2.css`: `.app{display:flex;min-height:100vh}` (line 20), so `body.v2 main` already stretches to the viewport height; on phone `body.v2 main{padding-bottom:104px}` (line ~243) reserves the fixed tab bar, so the content box already excludes it. Approach:
- `body.v2 main:has(:is(.submissions-page,.invoices-page,.stay-fees-page,.housebook-page) [data-empty-state])` (and housebook's `.panel.empty`) gets `display:flex;flex-direction:column`.
- Every element between `main` and the page wrapper, and the page wrapper itself, gets `flex:1 0 auto;display:flex;flex-direction:column` only in that state (check the real DOM chain in the templates/base.html; the yellow env banner and head stay as normal flex items at the top).
- The empty block gets `flex:1 0 auto;display:flex;flex-direction:column;justify-content:center;align-items:center`.
Housebook: 0825 found its empty panel is text-only; measure the panel's text box instead.

## 3. Files

`App/app/static/app2.css` (replace everything between `/* 0825 empty state centred (start) */` and `(end)` with the new rules; keep those markers). Do not touch the 0826 block. `App/app/templates/base.html` cache key to `20261102-0827`, then `.venv/bin/python tests/test_static_versions.py --write` from `App/` as the very last step.

## 4. Steps

1. Temporary measuring test as in 0825 §4 (delete afterwards): empty content centre vs centre of (head bottom .. viewport bottom minus the tab bar below 1024) at 390 and 1280, plus "page scrolls?".
2. Replace the block, measure again: within 24 px, no vertical scroll, on all four pages.
3. Overwrite `/mnt/project-files/records-pages/empty-<page>-<width>.png` (8 shots, 390 and 1280, viewport-size screenshots, not full page).

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_host_list_page_layout_browser.py tests/test_design_guardrails_browser.py tests/test_host_button_contrast_browser.py tests/test_host_wide_geometry_browser.py tests/test_0705_v2_shell_browser.py -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=short`

## 7. Acceptance

- [ ] Centred within 24 px, no scroll, 4 pages x 2 widths; no pixel offsets in the block.
- [ ] Commands: 0 failed, 0 skipped. Eight screenshots overwritten.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 25 tool calls.

## 9. Report

`docs/tasks/0827-report.md`, 150 tokens at most, with the measurements. Do not commit or push.
