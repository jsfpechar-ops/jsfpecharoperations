# 0795 brief: update older tests for the v2 Odeslání, Faktury, Domovní kniha pages

Status: in-progress

Executor: Haiku 5.5. Read `AGENTS.md`, `docs/context/executor.md`, then `docs/tasks/0790-records-pages-v2-common.md` (standing rule for assertions, test env, report). Another executor (0794) works on `/stay-fees` at the same time: never touch stay fee files or the `/* 0794` CSS block.

## Situation

Briefs 0791-0793 moved `submissions.html`, `invoices.html`, `housebook.html` to the v2 shell (no tab strip, `.head.stays-head`, `.card.stays-desk` table, `.stays-phone` cards, pills instead of `ui-badge`). Their 0710 tests pass. These older tests failed in a run on this branch (some may also fail on main):

test_design_reports.py::test_no_raw_style_or_legacy_control_in_the_three_templates; test_design_shell_browser.py (3 tests); test_endtoend.py (test_04 … test_28); test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls; test_host_copy_corrections.py::test_copy_correction_pages_browser_evidence; test_host_filter_panels_browser.py (2 tests); test_host_geometry.py::test_the_month_filter_shares_its_page_edges; test_host_list_page_layout_browser.py (3 tests); test_host_wide_geometry_browser.py::test_host_wide_lanes_align; test_shell_lane_browser.py::test_main_starts_right_of_the_rail_and_header_buttons_keep_v2_styles (4 params); test_wp25_reported_bugs.py::test_housebook_truncates_the_property_with_a_tooltip. (test_static_versions is the orchestrator's job: skip it.)

## Steps

1. Pre-existing check: `git worktree add /tmp/wt0795 origin/main` (fetch first: `git fetch -q origin main`), make `/tmp/wt0795/App/.venv` a symlink to `/home/claude/jsfpecharoperations/App/.venv`, and run the failing files there (`--tb=no -q`). Failures that also happen on main are NOT yours: list them in the report and leave them (for test_endtoend, run it alone on both trees; a first failure can cascade).
2. For each failure caused by this branch: read the assertion. If it checks only old markup of these three pages (tab strip, ui-table, ui-badge, panel, filter-toolbar wrappers, old geometry selectors), update it to the new markup or remove these three pages from a list of old-look pages, per the standing rule. If it checks behaviour (a link, an action, a filter that works without JS, a tooltip, no horizontal scroll, tap targets), fix the template or the page's own CSS block (`/* 0791`, `/* 0792`, `/* 0793` in app2.css) instead.
3. Re-run each fixed file. Then remove the worktree (`git worktree remove /tmp/wt0795 --force`).

## Report

`docs/tasks/0795-report.md`: per failing test: pre-existing / fixed assertion (file:line, old -> new) / fixed template. Stop at 30 tool calls with what is left.

## 1. Objective

Restyle the page(s) named above onto the v2 look; no behaviour change.

## 2. Context

See the sections above and docs/tasks/0790-records-pages-v2-common.md.

## 3. Files

Only the files named above, plus this brief's report.

## 4. Steps

Follow the sections above in order.

## 5. Do not touch

base.html, catalog.json, static_versions.json, docs/design/mockup/, other briefs' CSS blocks and templates.

## 6. Commands

From App/: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <files> -q --tb=short 2>&1 | tail -30

## 7. Acceptance

The named tests pass with 0 skipped; screenshots at 390 and 1440 px exist.

## 8. Stop and ask

A test outside the standing rule fails, or the tool-call cap comes near: write the report with what is left.

## 9. Report

docs/tasks/<number>-report.md as described in 0790.
