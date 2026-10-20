# 0194: Dashboard and stay rows, one clean box per row

Status: blocked
Depends on: none | Base commit: 6a19d1a | Branch: claude/project-thread-3xqb0b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner reports the dashboard "/" needs-action table (Czech, `?lang=cs`) still looks broken after many updates: cells as separate bordered boxes, red accent on single cells, a header row that does not line up with the rows, a 590 px card, and a badge sticking out past the card edge. Goal: one clean row per stay at every width, sidebar open or collapsed, Czech and English, with a browser guardrail that fails on any of these symptoms.

## 2. Context

- Mobile (max-width 1023 px): `App/app/static/host2.css:224-245`. `.host-workspace .ui-table tr { display: grid }` at line 227 is the grid that DevTools shows. `thead` is hidden here (line 225).
- Desktop (min-width 1024 px): `App/app/static/host2.css:570-576` (block "0181"). Borders and background sit on each `td`: every cell gets top and bottom borders, the first cell gets the left border and radius, the last cell gets the right border. `border-spacing: 0 var(--space-2)` at line 570 gives the gap between rows.
- Red accent: `App/app/static/host2.css:342` and `:347-348`, `tr.is-overdue td:first-child { box-shadow: inset 3px 0 0 ... }`.
- Dashboard markup: `App/app/templates/dashboard.html` lines 17-50 (`dashboard_rows` macro, `ui_table_begin`, row `tr.ui-row.dashboard-row.clickable-row`, cells with `data-card` primary, secondary, meta, badge, actions).
- Desktop row rules also in `App/app/static/host.css:1448-1450` (`.dashboard-row.clickable-row`) and `host-design0123.css:50-57`.
- Reproduction (this session, scratch test database, `App/tests/test_dashboard_rows_browser.py`):
  - Seeded 2 overdue stays and 1 scheduled stay on top of the calendar fixture. The needs-action section shows 10 rows, of which 5 are rendered.
  - Widths 390, 700, 900, 1023, 1024, 1100, 1200, 1280, 1366, 1440, 1536, 2000; sidebar open and collapsed (`localStorage ubyhost-sidebar-collapsed`); Czech.
  - At 390 to 1023 `tr` is `grid` (the phone card). At 1024 and up `tr` is `table-row` and each `td` carries its own border.
  - Measured on every width: no cell or badge overflows its row, no middle cell has a side border or radius, and the number of row boxes equals the row count.
  - Screenshots of the needs-action section: 1280 open shows clean rows with cells under the header; 390 open shows clean phone cards.
  - The per-cell boxes, the misaligned header and the 590 px card described by the owner were NOT reproduced at these widths. The owner's exact viewport, zoom and sidebar state are unknown.
- Pre-0181 state (origin/main) not checked: the worktree step was not reached.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_dashboard_rows_browser.py | new | guardrail for `/` needs-action and `/reservations` rows at 12 widths, sidebar open and collapsed; screenshots when `DASH_ROWS_SHOTS=1` |
| docs/tasks/0194-dashboard-rows-fix.md | new | this brief |

No CSS, template or `?v=` change in this step.

## 4. Steps

1. Done: reproduction and guardrail. `App/tests/test_dashboard_rows_browser.py` passes (2 passed, 0 skipped) at the current HEAD in Czech. English run is in the report.
2. Blocked: get the owner's exact repro. Ask the owner for: the browser window width in CSS pixels (or the DevTools "Dimensions" badge), any zoom level, whether the sidebar is open or collapsed, and a full-page screenshot of the `Vyžaduje akci` section. Until then no CSS change is made.
3. After step 2 is answered: fix the root cause in the shared row CSS in `host2.css` (lines 158-171, 224-245, 342-348, 570-576). Aim: one bordered card per row on phone and tablet (≤1023), one clean table row on desktop (cells under the header, one row border, red accent on the row's left edge only, the three-dot menu in the last column without its own box). Apply to every page that uses the same row markup (Stays, fees, invoices, properties, submissions, users, housebook).
4. After step 3: bump `?v=` for every changed CSS in `App/app/templates/base.html` and `App/tests/static_versions.json`. Add any new classes to `docs/design/catalog.json`.
5. Run §6 and add screenshots of changed pages at 390 px to the report.

## 5. Do not touch

`App/data/ubyhost.db`, host mail logic, the calendar widget (`dashboard-calendar.css`), dashboard data logic in `reporting.py`, and any other file not in §3 or named in step 3.

## 6. Commands

- `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell .venv/bin/python -m pytest tests/test_dashboard_rows_browser.py -q --tb=short -rs 2>&1 | tail -30`
- `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell DASH_ROWS_LANG=en .venv/bin/python -m pytest tests/test_dashboard_rows_browser.py -q --tb=short -rs 2>&1 | tail -30`
- After step 3 also: `cd App && UBYHOST_BROWSER_EXECUTABLE=... .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_static_versions.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_host_list_page_layout_browser.py tests/test_dashboard*.py -q --tb=short -x -rs 2>&1 | tail -30`
- `python3 scripts/context_lint.py 2>&1 | tail -30` (from the repo root)

## 7. Acceptance

- [x] Reproduction at 12 widths, sidebar open and collapsed, Czech (step 1).
- [x] Guardrail test present and passing with 0 skipped.
- [ ] English run recorded in the report.
- [ ] Owner repro (step 2).
- [ ] Root cause fixed and verified at 390, 700, 900, 1023, 1024, 1100, 1200, 1280, 1366, 1440, 1536, 2000.
- [ ] Other row pages checked at the same widths.
- [ ] `?v=` bumped and catalog updated.
- [ ] Context lint passes.

## 8. Stop and ask

- The owner's repro is needed before any CSS change (step 2). Question for the owner: "At what browser width (CSS px, or the DevTools size badge) and zoom does the table show the header row and the separate boxes? Is the sidebar open or collapsed? Please send a full-page screenshot of the 'Vyžaduje akci' section."
- A test fails twice, or the 25-tool-call cap is reached.

## 9. Report

`docs/tasks/0194-report.md` (600 tokens max), then `Status: review` (or `blocked`). Commit on the current branch with explicit paths; push after `git pull --rebase --autostash origin claude/project-thread-3xqb0b`.
