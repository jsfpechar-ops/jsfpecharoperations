# 0825: Records pages: empty state sits in the middle of the page

Status: todo
Depends on: 0820 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Josef (14:37): when there are no reports (or nothing in the list), the empty-state text should sit in the middle of the page, not right under the head. On `/submissions`, `/invoices`, `/housebook`, `/stay-fees` (v2), the empty block (`.ui-empty` / `[data-empty-state]`, or housebook's own "no entries" block if it has no `.ui-empty`) is centred vertically in the space between the bottom of the head/filter row and the bottom of the viewport (above the phone bottom bar at < 768), and stays horizontally centred. When the list has rows nothing changes.

## 2. Context

Empty states come from the macros in `App/app/templates/_ui.html` / `_components.html`; v2 rules `body.v2 .ui-empty` at the end of `App/app/static/app2.css` (0820 block). Prefer CSS only, scoped to the four page wrappers (`.submissions-page`, `.invoices-page`, `.housebook-page`, the stay-fees wrapper): e.g. make the page wrapper a column flex with `min-height` filling the lane (`calc(100dvh - <shell offsets>)`) and the empty block `margin:auto 0` / `flex:1` with centred content. Do not change the macros' markup for other pages. Keep 0775 geometry (16 px card edge, 12 px text to button, 24 px after a block-ending button).

## 3. Files

`App/app/static/app2.css` (new block `/* 0825 empty state centred (start/end) */`), the four page templates only if a wrapper class is missing, `App/app/templates/base.html` (`app2.css?v=20261102-0825`), then `.venv/bin/python tests/test_static_versions.py --write` from `App/`; `docs/design/catalog.json` if a new class is added.

## 4. Steps

1. Measure with a temporary test (fixtures: the `acc`/`none` user pattern from `tests/test_host_list_page_layout_browser.py`, a host with no rows): empty block centre vs the centre of (head bottom .. viewport bottom, minus bottom bar) at 390 and 1280. Delete the temp file afterwards.
2. Fix, measure again: centre within 24 px at 390 and 1280 on all four pages.
3. Save one screenshot per page at 390 and 1280 with the empty user to `/mnt/project-files/records-pages/empty-<page>-<width>.png`.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_host_list_page_layout_browser.py tests/test_design_guardrails_browser.py tests/test_host_button_contrast_browser.py tests/test_host_wide_geometry_browser.py -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=short`

## 7. Acceptance

- [ ] Empty block centred (within 24 px) in the free area at 390 and 1280 on all four pages; no page scrolls when empty.
- [ ] Pages with rows unchanged.
- [ ] Commands: 0 failed, 0 skipped. Eight screenshots saved.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 25 tool calls.

## 9. Report

`docs/tasks/0825-report.md`, 150 tokens at most. Do not commit or push.
