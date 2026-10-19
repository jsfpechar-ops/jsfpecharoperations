# 0159 report

Status: done

Files: App/tests/design_guard.js, App/app/static/host2.css, App/app/templates/base.html (key 20261019-0159), App/tests/static_versions.json, docs/design/MASTER.md.

- Guard before fix: 8 findings `cell-not-under-header` `td.ui-sub` vs `th "Who"` on settings and settings-account, 1280 and 2000, open and collapsed. No other routes.
- Guard after fix: 1 passed.
- static_versions test: 2 passed. design_lint: OK.
- test_host_controls_browser, test_shell_lane_browser, test_host_wide_geometry_browser: 11 passed, 0 skipped.

Acceptance: [x] new check exists, first failed on settings, now passes everywhere.
Deviations: none. Owner steps: push and open PR.
