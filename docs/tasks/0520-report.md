# 0520 report

Status: blocked

Done: steps 1 to 4 (committed as `0520 step 1` to `0520 step 4`).
Left: steps 5 and 6 (test file `App/tests/test_0520_overview_today.py`, `workflow.css?v=` bump, screenshots), and the full test sets in brief section 6.

## Commands run

1. Unit set (brief section 6, first command), stopped at first failure with `-x`:
```
FAILED tests/test_design_dashboard.py::test_dashboard_with_a_property_has_the_v2_header_one_primary_and_refresh_hooks
  assert page.count('class="ui-btn ui-btn-quiet ui-btn-icon ui-ph-menu"') == 1   ->  0 == 1
1 failed, 38 passed in 5.05s
```
2. Browser set, stopped at first failure with `-x`:
```
FAILED tests/test_host_quiet_dashboard_browser.py::test_dashboard_single_stay_needs_you_card
  AssertionError: single/en/360
  assert page.locator(".dashboard-stats, .dashboard-row, .ui-banner-attention").count() == 0  ->  1 == 0
1 failed, 2 passed in 22.74s
```
3. `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, about open briefs and status.md).

## Diff stat

```
 App/app/host_i18n.py                             | 24 +++++++++++++
 App/app/host_vi_i18n.py                          | 12 +++++++
 App/app/reporting.py                             | 40 +++++++++++++++++++++
 App/app/routes/admin.py                          |  6 ++++
 App/app/static/workflow.css                      |  3 ++
 App/app/templates/dashboard.html                 | 14 ++++----
 docs/tasks/0520-overview-month-line-and-today.md | 44 ++++++++++++++++++++++++
 docs/tasks/0521-overview-14-day-calendar.md      | 44 ++++++++++++++++++++++++
 8 files changed, 180 insertions(+), 7 deletions(-)
```
(The two `docs/tasks/05xx` files were already on the branch before this run.)

## Deviations

- Step 4 caption: the macro gained `caption_key` and `mark_today` parameters. `today_rows` is computed in the `dashboard()` route (not in the template), comparing ISO date strings.
- Step 3 keys: month copy uses word-only keys with `.one`/`.few` forms, and the number is printed in `<b>` by the template (the brief allowed this).
- Step 2: `month_summary` also excludes archived properties (`a.archived_at IS NULL`), as the brief text asks.

## Questions for the owner or orchestrator

1. `test_design_dashboard.py` asserts the removed "more actions" icon button (`ui-ph-menu`) appears once. Brief section 8 allows updating only that assertion. Not done in this run because the run stopped at the tool-call cap.
2. `test_dashboard_single_stay_needs_you_card` (browser) expects no `.dashboard-row` on a single-stay dashboard. The new Today table renders `.dashboard-row` for stays arriving or leaving today, so this existing test now fails. Brief section 8 says to stop when another existing test changes result. Decide whether the Today rows should use a different class, or whether the test fixture should be treated as expected.

## Owner steps left

None yet. Steps 5 and 6 and the full section 6 test sets must run in a new session after the questions above are answered.

## Run 2 (executor, after step 4b)

Status: blocked

Done: step 4b committed as `0520 step 4b` (commit 8476389): `test_design_dashboard.py` now asserts `ui-ph-menu` and `dashboard-more` are absent; `test_host_quiet_dashboard_browser.py` Today-table selector changed as ordered. `test_design_dashboard.py` passes.
Left: steps 5 and 6, and the full section 6 test sets.

Blocker (new, not in the orchestrator decisions): `App/tests/test_host_quiet_dashboard_browser.py` line 351-355 (`test_dashboard_rich_needs_you_order_cap_and_geometry`, `rich/en/360/open`) asserts `page.locator(".ui-ph-menu").is_visible()` when the header overflows at 360 px. Step 1 removed that button, so the assertion fails:
```
E   AssertionError: rich/en/360/open
E   assert False  (.ui-ph-menu is_visible)
1 failed, 1 passed in 12.14s
```
Brief section 8 says stop when another existing test changes result. Not changed. Decision needed: remove or rewrite lines 351-355 (for example, assert the header has no `.ui-ph-menu`), or keep them.
