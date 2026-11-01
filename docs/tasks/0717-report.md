# 0717 report: v2 Overview feature parity

Status: blocked
Done: steps 1 to 3 (all sections 2 items except the deadline tests). Left: test_deadline_after_reporting.py (2 tests), and a final single run of the section 6 command.

## Commits (branch task/0717-v2-overview-parity, not pushed)
- 0717 step 1: help block, onboarding banner and finish card, v2_status_pill macro, icon tone attribute, CSS key 20261101-0717, manifest.
- 0717 step 2: alerts without a todo card are shown on the v2 Overview (also on the zero-state page).
- 0717 step 3: calendar scroll wrapper; banner test split marker.
- Last edits (calendar wrapper, help CSS, key 20261101-0717b, manifest) are committed with this report.

## Counts
- Baseline section 6: 14 failed, 78 passed.
- Full section 6 run before the last 3 fixes: 9 failed, 83 passed, 0 skipped.
- After the last fixes, the files that had failed were rerun: test_0520, test_0252, test_0710, test_design_dashboard, test_p1_review: 30 passed. test_page_help, test_static_versions, test_onboarding, test_0375, test_host_language, test_needs_you_dashboard_0241: passed.
- Expected final: 2 failed (deadline), 90 passed, 0 skipped. Not verified by one full run.

## Still failing
- tests/test_deadline_after_reporting.py::test_a_reported_stay_past_its_deadline_shows_no_overdue: `dashboard: []`. The helper reads badges from pages that show today's stays only; the v2 Overview lists no such row.
- tests/test_deadline_after_reporting.py::test_a_stay_filed_after_its_deadline_reads_late: same cause (`dashboard: []`).

## Deviations
- test_dashboard_missing_banner: split marker changed to `class="needs-you-more` (the v2 details has `ov-section` too). Count 4 unchanged.
- Calendar card wrapped in `<div class="scroll-x">` (not the card class) for the touch sweep.
- `data-dashboard-refresh` attributes removed from the Overview because test_design_dashboard asserts they are absent. dashboard-calendar.js still references this hook, so the calendar/stats refresh may no longer run. Owner to decide.
- _host_alerts.html: new `alerts_expanded` flag shows every uncovered alert, not the "N more" summary, on the Overview.
- Other v2 pages still hide the alert stack (base.html guard unchanged); only the Overview shows uncovered alerts.
- Not run: test_endtoend, test_demo_seed, test_reporting_help_0097 (not in section 6).

## Questions
- Refresh hook removal (above): keep or restore and move the test?
