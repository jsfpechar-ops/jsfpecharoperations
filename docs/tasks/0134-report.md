# 0134 report

Status: blocked

Files changed: App/app/templates/reservations.html, App/app/static/host2.css, docs/design/catalog.json, App/tests/test_stays_empty_workspace.py, App/tests/test_host_filter_panels_browser.py, App/tests/test_design_stays.py (new).
Commits: b01a9cf (step 1), 5963102 (step 2), ebd7ff4 (step 3), e1a23b1 (step 4), 1dbd37b (step 5), 10c33f9 (step 5 fix: selector quoting).

Done: steps 1 to 5. Left: step 6 (browser tests fail), screenshots, report acceptance.

Commands:
- design_lint: OK. ruff E9,F63,F7,F82,F401,F841: All checks passed.
- test_design_stays + stays tests (step 5): 36 passed.
- Browser (step 6): 3 failed, 12 passed, 0 skipped. Failures:
  - test_host_filter_panels_browser.py:424 test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_czech: assert 40 >= 42 (triggerHeight).
  - test_host_list_page_layout_browser.py:155 test_list_pages_share_order_edges_and_rhythm: 'DOM order is not notices, title, tabs, toolbar, panel' for stays at 760, 1024, 1440; plus a height [40, 42] mismatch at 1024.
  - test_host_geometry.py:119 test_dashboard_actions_share_height_and_gap: assert 2 == 1 (heights {0, 40}). Not verified as pre-existing.
- Non-browser (grep /reservations, -x): 483 passed, 1 failed:
E   AssertionError: [

Screenshots: none. No test writes UBYHOST_SHOTS_DIR, and I had no calls left for a Playwright script.

Deviations: step 2 put ui_toolbar in the body block, but host_page renders the toolbar block before body. Likely cause of the DOM-order failure. Not fixed.

Questions: (1) Should the toolbar call move into a {% block toolbar %} in reservations.html? (2) Is the 42 px trigger minimum for the Filters button still wanted under v2 (40 px now)? (3) Is test_dashboard_actions_share_height_and_gap failing on the base commit too?

Owner steps left: none.
