# 0183: sidebar search has a visible border; no borderless controls

Status: todo
Depends on: 0182 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner: "search lost its borders, dont do this borderless design, i dont like it". The sidebar search row (`.ui-search-row`, host2.css line 255, `background: var(--surface-2)`, no border) must look like the other inputs: white surface, 1 px `var(--input-border)` border, `var(--input-radius)`. Then find any other control that is borderless on a grey fill (selects, toolbar search, filter chips, buttons) with `grep -n "background: var(--surface-2)" App/app/static/host2.css | cut -c1-200` and give each a 1 px border in the same style if it is an interactive control; leave cards, hover states and table headers alone.

## 2. Files

`App/app/static/host2.css` (append `/* 0183 */` block, tokens only; S1 no raw colours, S2 no bare px in margin, padding, gap, font-size), `base.html` key ending `-0183`, `App/tests/static_versions.json`, `App/tests/test_design_guardrails_browser.py` (one new test), `docs/tasks/0183-*`.

## 3. Steps

1. Append the block. Collapsed sidebar (`.sidebar-collapsed`, lines 268-269) must still show a square bordered icon button with no clipping.
2. Lint, bump key, `--write` as in brief 0181 steps 2-3.
3. Add `test_sidebar_search_has_a_border` (1280 px, `/?lang=en`): computed `border-top-width` of `.ui-search-row` is `1px` and `border-top-color` is not transparent.
4. Screenshots of `/` and `/reservations` at 390,1280,2000, sidebar open and collapsed at 1280 (look at them). Use `--new-app $PWD/App`.
5. Browser tests as in 0181 step 6, 0 skipped.
6. Commit "0183: sidebar search and other controls get a visible border" with the trailers given by the orchestrator. Do not push.

## 4. Do not touch

Templates, copy, guard scripts; hard rules 1, 3, 8.
