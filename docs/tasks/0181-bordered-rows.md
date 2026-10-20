# 0181: every table row has its own border

Status: todo
Depends on: 0180 (run after it) | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner: "the rows, for everything, dont have borders, it feels weird and ugly". On desktop, `.ui-table` rows are separated only by a hairline and read as borderless. Give every desktop row its own 1 px border and rounded corners, as the phone cards already have, with a small gap between rows. Default chosen by the orchestrator (the owner did not specify): separated bordered rows, not a darker divider.

## 2. Context

`App/app/static/host2.css` line ~148: `.host-workspace .ui-table { border-collapse: separate; border-spacing: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); overflow: hidden }`, `td` has `border-bottom: 1px solid var(--line)`, `tr:last-child td { border-bottom: 0 }`. Below 1024 px a media block (line ~215) already turns rows into bordered cards; do not change it. Row hover rule is line 156.

## 3. Files

`host2.css` (append a `/* 0181 */` block, only for min-width 1024 px; tokens only: S1 no raw colours, S2 no bare px in margin, padding, gap, font-size), `base.html` (host2.css key ending `-0181`), `App/tests/static_versions.json`, `App/tests/test_design_guardrails_browser.py` (one new test), `docs/tasks/0181-*`.

## 4. Steps

1. In the appended block inside `@media (min-width: 1024px)`: `.host-workspace .ui-table { border: 0; background: transparent; border-spacing: 0 var(--space-2); overflow: visible }`; header `th` keeps its bottom border off (`border-bottom: 0`); `td` gets `background: var(--surface); border: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line)`; `td:first-child` gets `border-left: 1px solid var(--line)` and left radius `var(--card-radius)`; `td:last-child` gets `border-right: 1px solid var(--line)` and right radius; reset `tr:last-child td { border-bottom: 1px solid var(--line) }`. Hover: `.ui-row:hover td { background: var(--surface-2) }`. Adapt if the screenshot shows clipping, shifted columns or a row wider than its neighbours. Rows with `is-overdue` or other row-state styling must keep working; check `grep -n "is-overdue\|ui-row" App/app/static/host2.css`.
2. `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
3. Bump the key (`-0181`), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. Add `test_table_rows_have_their_own_border_on_desktop` to `test_design_guardrails_browser.py` (use `wide_host` / `wide_base`): at 1280 px open `/reservations?lang=en`, take the first `tbody tr td` and assert its `border-top-width` is `1px` and its first cell has `border-left-width` `1px`, and that the second row's top is at least 4 px below the first row's bottom.
5. Screenshots with `/mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out docs/tasks/0181-screenshots --pages "/,/reservations,/invoices,/properties" --widths 390,1280,2000` (pages need a leading slash). Look at them: no clipping, columns aligned, header still readable.
6. From `App/`, foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_host_wide_geometry_browser.py -q -rs 2>&1 | tail -6`. Then `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: 0 skipped; known failures that also fail on main: `test_list_pages_share_order_edges_and_rhythm`, name them in the report if they appear.
7. Commit "0181: table rows have their own border" with the trailers given by the orchestrator. Do not push.

## 5. Do not touch

Phone card block, templates, copy, guard scripts; hard rules 1, 3, 8.
