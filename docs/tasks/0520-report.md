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

## Final (run 3, steps 4c, 5, 6)

Status: done (not pushed, no PR opened)

Commits: `0520 step 4b` (8476389), `0520 step 4c` (4f34789), `0520 step 5` (751dea1), `0520 step 6` (this commit), report commit.

Test edits beyond step 4b (coordinator decision):
- `App/tests/test_host_quiet_dashboard_browser.py` ~line 351-355: header test now asserts `.ui-ph-menu` count is 0 (no overflow menu), comment changed to "Header: one primary action, no overflow menu (0520)." Commit 4f34789.
- No other existing assertion needed changing.

Unit set (brief section 6, first command):
```
69 passed in 4.33s
```

Browser set (brief section 6, second command, -rs, no skips):
```
...............                                                          [100%]
15 passed in 119.61s (0:01:59)
```

Context lint (`python3 scripts/context_lint.py`):
```
next free: task 0622 | migration 0034
context lint: OK
```
(Warnings only: open briefs named by files, and 11 App/ commits since the last status.md update.)

Step 6:
- `App/app/templates/base.html` line 28: `workflow.css?v=20261025-0375` changed to `?v=20261101-0520` (the brief's "plus its ?v= key" was in scope; the write script refused until this changed).
- `App/tests/static_versions.json` regenerated with `tests/test_static_versions.py --write` ("wrote ... (40 files)").

Screenshots (`/?lang=cs`, from the existing single-stay browser test with `UBYHOST_SHOTS_DIR` set; full page):
- `docs/tasks/screenshots-0520/overview-cs-1280.png`
- `docs/tasks/screenshots-0520/overview-cs-390.png`

Diff stat (`git diff --stat origin/main`, before the final report commit):
```
 App/app/host_i18n.py                             | 24 +++
 App/app/host_vi_i18n.py                          | 12 +
 App/app/reporting.py                             | 40 +++
 App/app/routes/admin.py                          |  6 +
 App/app/static/workflow.css                      |  3 +
 App/app/templates/base.html                      |  2 +-
 App/app/templates/dashboard.html                 | 14 ++---
 App/tests/static_versions.json                   |  4 +-
 App/tests/test_0520_overview_today.py            | (new file, 5 tests)
 App/tests/test_design_dashboard.py               |  4 +-
 App/tests/test_host_quiet_dashboard_browser.py   |  4 +-
 docs/tasks/0520-overview-month-line-and-today.md |  44 +++
 docs/tasks/0520-report.md                        |  ...
 docs/tasks/0521-overview-14-day-calendar.md      | 44 +++
```

Deviations:
- Step 6 screenshots come from the existing `test_dashboard_single_stay_needs_you_card` fixture (one property, one stay), not a multi-stay seed. Re-taken only with that test; not retaken.
- Step 5 test file: `_guest` uses `submit_state=reporting.PENDING` (column is NOT NULL). The "Add cleaning" check looks for `>Add cleaning<` because the string also appears in the embedded i18n JSON.
- Step 4 (earlier run) caveat stands: the Today table is `dashboard-today` section; `test_host_quiet_dashboard_browser.py` selector per the coordinator decision.
- Tool-call budget: this run used about 14 calls.

Owner steps left: review and open the PR (`scripts/merge-pr-on-green.sh` for merge; production deploy is manual).
