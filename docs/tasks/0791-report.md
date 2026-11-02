# 0791 report: Odeslání (/submissions) on the v2 look

Status: blocked (steps done; test cleanup left, see Left)

## Files changed
- `App/app/templates/submissions.html`: v2 shell (`set v2`, empty blocks), `.head.stays-head` with how-to (`how.reports.1-3`), `p.sub` lede, hint `p.sub ph-hide`, head ghost buttons (housebook, receipts download), phone `.card.stay` list, desktop `.card.stays-desk` table, empty state wrapped in `.submissions-page`. Outcome pill mapped inline to `span.pill` (macro left unchanged, other callers untouched).
- `App/app/static/app2.css`: one rule inside the 0791 markers (`body.v2 .submissions-page .ui-empty .ui-btn`, 44 px tap target).
- `App/tests/v2_mockup.py`: `submissions` entry in PAGES; 4 `missing_ok` reasons (no police submission on the rich host); 2 BOX_OVERRIDES for the text-dependent h1 width at 320/390.
- `App/tests/test_design_reports.py`: two assertions made page-aware for /submissions (tab strip gone; `btn`/`pill` classes allowed on this template only). Housebook assertions unchanged.
- `docs/tasks/screenshots-0790/submissions-390.png`, `submissions-1440.png` (390 viewed, looks right).

## Commands (last lines)
- `pytest tests/test_0710_v2_mockup_match_browser.py -k submissions`: 12 passed, 0 skipped.
- `pytest tests/test_design_reports.py`: see Left.
- Old tests for /submissions (27 files): 29 failed, 304 passed. Failures not on this page: `test_0252` and `test_wp25`/`test_host_list`/`test_design_reports` housebook cases (other executor's page); `test_endtoend` (14+ tests, mock UbyPort at 127.0.0.1 refused, environment, not checked against main).

## Deviations
- Did not commit (task instruction overrides executor.md commit step).
- Teal `running` state has no v2 pill colour; mapped to `p-n` (neutral). Owner to confirm.
- Head/pills: `btn ghost` / `pill` classes, as the common brief asks.

## Left
- `App/tests/test_host_list_page_layout_browser.py:170` still expects the old tab strip for `/submissions` (`tabs.stays.reports`); update to the new head, then rerun that file.
- `test_host_list_page_layout_browser` rhythm/row tests and `test_host_wide_geometry_browser::test_host_wide_lanes_align` not yet inspected for /submissions.
- `test_design_reports::test_reports_and_housebook...` and `test_no_raw_style...` pass for submissions; the housebook half belongs to the housebook executor.

## Questions
- Teal `running` pill: neutral grey (`p-n`) or amber?

## Owner steps
- None for this page. Review the diff before merge; nothing pushed.
