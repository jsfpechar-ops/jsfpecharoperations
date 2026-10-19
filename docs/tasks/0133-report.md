# 0133 report

Status: blocked

## Commits (branch claude/project-thread-td6fpc, not pushed)

- 9074aac step 0: host2.css row-menu min-height moved into a 767px block (appended at end)
- ec927cc step 1: dashboard.html rewritten on host_page.html (detail kind); compiles
- 9398a67 step 2: catalog.json enforces dashboard.html, hooks added; design_lint OK
- f73b44c step 3: test_host_geometry.py uses .ui-ph-acts / .ui-btn / .ui-stats / .ui-ph; passes (2 passed)
- 1c49480 step 4: App/tests/test_design_dashboard.py created; its 3 tests pass

## Files changed

App/app/static/host2.css, App/app/templates/dashboard.html, docs/design/catalog.json, App/tests/test_host_geometry.py, App/tests/test_design_dashboard.py

## Commands

- design_lint: "design lint: OK"
- ruff (E9,F63,F7,F82,F401,F841): "All checks passed!"
- test_host_geometry.py: "2 passed, 1 warning"
- test_design_dashboard.py + test_signed_in_chrome.py (-x): stopped at test_dashboard_status_counts_use_distinct_colours, 15 passed before it
- test_signed_in_chrome + quiet dashboard + dashboard calendar browser (no -x): "7 failed, 22 passed"

## Failing (not fixed, outside the brief's scope)

- test_signed_in_chrome.py:216 and :~260 (status counts): assert 0 == 3. Old markup `<a class="dashboard-stat action|waiting|ready|overdue">` is gone; new markup is `ui-stat` with no colour kind or is-positive class.
- test_host_quiet_dashboard_browser.py:199 and :287: same stat-selector cause (assert 0 == 3).
- test_host_quiet_dashboard_browser.py:328 (header button count, step 0 item): not updated yet; the count and heights depend on the v2 header (.ui-btn, 44/40 px).
- test_host_quiet_dashboard_browser.py test_dashboard_rich_queue_colors...: Locator inner_text timeout 30 s.
- test_dashboard_calendar_browser.py: a `Cannot read properties of null (getBoundingClientRect)` in geometry test; a 30 s inner_text timeout in creation test; assert False at line 699 in the retry test. Likely selectors in the refresh/calendar hooks.

## Deviations

- Step 1: `t('dashboard.table.task')` was not in any app file, so I used `t('dashboard.stat.action')` (as the brief allows).
- Step 3: geometry height assertion 42 changed to 40 (v2 control height at 1280); aligned-block selectors `.dashboard-stats` and `.host-today-head` mapped to `.ui-stats` and `.ui-ph`.
- Step 4: dropped the `data-skeleton-kind` assertion (the attribute is not in host_page.html or base.html).

## Questions

1. The stat-count tests (test_signed_in_chrome.py, quiet dashboard) assert colour kinds (action/ready/overdue, is-positive) that the brief's markup no longer has. Should the stat tiles keep a semantic class (e.g. is-positive / kind) and the tests be updated, or should those tests be rewritten?
2. Should the dashboard calendar test failures be fixed in this brief, or handed to a follow-up?

## Owner steps left

None. Steps 5 and 6 (browser run, 0 skipped, 390/360/1280 screenshots, acceptance section 7) are not done.
