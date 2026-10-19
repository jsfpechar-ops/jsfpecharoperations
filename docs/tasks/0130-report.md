# 0130 report

Status: blocked

## Files changed
- App/app/host_i18n.py (step 1). Commit bf6a829.
- App/app/templates/_shell_sidebar.html (step 2). Commit 3244a48.
- App/app/templates/_shell_topbar.html (step 3). Commit 9fd6201.
- App/app/templates/_shell_tabbar.html (step 4). Commit 529aeaa.
- App/app/templates/base.html (step 5). Commit 2e5fb8e.
- App/app/static/shell.js (step 6). Commit 41f3a3c.
- App/app/static/host2.css (step 7). Commit 01c9c2f.
- App/tests/test_design_shell.py (step 8). Commit f33bc70.
- App/tests/test_design_shell_browser.py (step 9). Commit 745197b.
- App/tests/test_design_page_template.py (0129 lint fix). Commit 0c1c67b.

## Commands
- `cd App && .venv/bin/python -m pytest tests/test_design_shell.py tests/test_signed_in_chrome.py tests/test_skeleton_loaders.py -q --tb=short -x`
  Last line: `29 passed, 1 warning in 1.76s`.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_shell_browser.py -q -rs --tb=short -x`
  Last line: `2 passed, 1 warning in 2.75s`.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_host_geometry.py tests/test_cleaning_browser.py tests/test_property_navigation_browser.py tests/test_download_skeleton_browser.py -q -rfs --tb=no`
  Last line: `2 failed, 36 passed, 1 warning in 99.54s`. Failed: `test_property_navigation_browser.py::test_three_views_four_groups_one_editor_and_unique_ids`, `test_property_navigation_browser.py::test_create_offers_the_calendar_first_and_works_without_js`. Both also fail at the pre-brief commit 5348afb.
- `python3 scripts/design_lint.py` Last line: `design lint: OK`.
- `cd App && .venv/bin/ruff check tests/ app/ --select E9,F63,F7,F82,F401,F841` Last line: `All checks passed!`.
- Screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=<scratchpad>/shots/0130 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q --tb=line` Last line: `11 passed`.

## Section 7
- [x] No nav-toggle, appbar or nav-backdrop in a signed-in page (test_design_shell.py).
- [x] Sidebar 240 px at 1280 and 64 px collapsed; 5 tabs at 390, 44 px or more; More opens the sheet.
- [x] test_signed_in_chrome.py unchanged and passing.
- [ ] One 390 px screenshot in the report (see Screenshots).

## Screenshots
- 390 px: scratchpad shots/0130 folder, file name contains `-390` (dashboard calendar page, cs).

## Known pre-existing failures
- test_property_navigation_browser.py (two tests above): fail at 5348afb, before 0130. Not in the brief's known list. Not fixed: outside section 3.
- test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects: fails when run alone (known).

## Deviations
- Done: steps 1 to 9. Left: step 10 (acceptance). Step 10 has no file change, and its acceptance run has the two pre-existing property navigation failures above, so no step-10 commit was made.

## Questions
- Should test_property_navigation_browser.py be fixed in a separate brief, or added to the known list?

## Owner steps left
- None.
