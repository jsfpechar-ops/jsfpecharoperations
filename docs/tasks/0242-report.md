# 0242 report

Status: review

## Commits

- 94bb8c2 0242 step 1: test_host_wide_geometry_browser.py
- 2d41cd0 0242 step 2: test_dashboard_calendar_browser.py
- 50d9c05 0242 step 3: test_dashboard_phone_browser.py
- 08e13b7 0242 step 4: test_host_geometry.py
- 2166972 0242 step 5: test_dashboard_rows_browser.py, test_host_list_layouts_browser.py, test_host_list_page_layout_browser.py, test_onboarding_followup_browser.py

No app code, CSS or template changed.

## Tests (run from App/, PLAYWRIGHT_BROWSERS_PATH and UBYHOST_REQUIRE_BROWSER=1, -rs added)

1. tests/test_alert_stack.py + calendar, phone, host_geometry, rows: `28 passed, 1 warning in 56.73s`
2. tests/test_alert_stack.py + list_layouts, list_page_layout, onboarding_followup: `36 passed, 1 warning in 109.99s (0:01:49)`
3. tests/test_alert_stack.py + host_wide_geometry: `19 passed, 1 warning in 187.03s (0:03:07)`

No skipped tests in any command.

Lint: `ruff check --select E9,F63,F7,F82,F401,F841` on the 8 touched files: All checks passed.

## 7. Acceptance

- [x] The three §6 commands pass with 0 skipped.

## Deviations

- Added `-rs` to the three pytest commands to show skips. Results are the same as the brief's commands.
- No screenshots: the change is test-only, no template or CSS changed.
- Done: steps 1 to 5. Left: none.

## Questions

- Repo-wide `ruff check tests --select F401` reports 1 existing error: unused `import re` in `App/tests/test_design_dashboard.py`. That file is not in §3, so it was left alone.
- Step 2d keeps the banner check using `[data-dashboard-refresh="work"]`, as the brief says. It passed, but the work region no longer exists on the dashboard. The reviewer may want that selector moved to the card.

## Owner steps left

None.
