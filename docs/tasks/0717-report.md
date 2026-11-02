# 0717 report: v2 Overview feature parity

Status: review
Done: steps 1 to 4 and the deadline tests (brief 0717b, orchestrator decisions 1 to 3). Left: nothing for the executor. Owner: review and merge.

## Commits (branch task/0717b-v2-parity-fixes, not pushed)
- 0717 step 1 to 3: help block, onboarding banner, finish card, v2_status_pill, alerts on the v2 Overview, calendar scroll wrapper, banner test split marker.
- 0717 step 4: calendar wrapper, help CSS, key 20261101-0717b, manifest; report (blocked).
- 0717b: refresh hooks restored on dashboard.html (`data-dashboard-refresh="stats"` on #needs-action, `="work"` on the Dnes card); test_design_dashboard asserts they are present; test_deadline_after_reporting drops "dashboard" from the helper pages (the v2 Overview lists only today's stays); report.

## Counts (brief section 6, one run, from App/)
- `test_p1_review ... test_static_versions` (14 files): 92 passed, 0 failed, 0 skipped.
- `tests/test_dashboard_calendar_browser.py`: 14 passed, 0 failed, 0 skipped.
- `python3 scripts/design_lint.py`: OK. `python3 scripts/context_lint.py`: OK.

## Still failing
- None.

## Deviations
- app2.css rule `body.v2 .card[data-dashboard-refresh="work"] > table` matches again now that the Dnes card has the attribute (no CSS change).
- test_deadline_after_reporting: the Overview red-line check (0241) moved out of the loop into a direct `client.get("/")` call, so that coverage is kept.
- Alerts: `alerts_expanded` flag in _host_alerts.html shows every uncovered alert on the Overview (step 2).
- Other v2 pages still hide the alert stack (base.html guard unchanged).
- Not run: test_endtoend, test_demo_seed, test_reporting_help_0097 (not in section 6).

## Questions
- None open. Refresh hooks restored per orchestrator decision 1.
