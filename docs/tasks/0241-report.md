# 0241 report

Status: blocked

## Commits (on claude/project-thread-0io75h, not pushed)

- 0241 step 1: routes/admin.py, two context keys. Import check: no output.
- 0241 step 2: base.html, stack hidden when `hide_alert_stack`. No test in brief.
- 0241 step 3: dashboard.html replaced. `23 passed, 1 warning in 2.69s`
- 0241 step 4: needs_you.py, started/not started wording. `19 passed, 1 warning in 2.14s`
- 0241 step 5: test_alert_stack.py sed. grep count `7`.
- 0241 step 6: test_dashboard_queue_copy.py. `27 passed, 1 warning in 2.77s`
- 0241 step 7: test_host_language.py. `18 passed, 1 warning in 2.25s`
- 0241 step 8: test_dashboard_missing_banner.py replaced. `18 passed, 1 warning in 2.50s`
- This report commit.

## Step 9 (not committed)

Edits applied to test_design_dashboard.py and test_deadline_after_reporting.py (uncommitted in the working tree). Command result:

`FAILED tests/test_deadline_after_reporting.py::test_a_stay_not_reported_past_its_deadline_is_still_critical`
`AssertionError: dashboard: []` at line 276 (`assert any(level == "overdue" and "overdue by" in text ...)`). `1 failed, 27 passed, 1 warning in 2.95s`

The dashboard card shows overdue stays as red lines (needs_you.py line 79-80, copy `needs_you.stay.overdue`), but the test expects the `overdue by` badge text on the dashboard. This is caused by the step 3 template change, not by the step 9 lines. Not fixed: the fix needs a decision on the copy or the test expectation.

## Deviations

Done: steps 1 to 8. Step 9: edits applied, test red, not committed. Left: step 9 commit (after the question below is answered), steps 10 and 11, §6 commands 1 to 3, §9 report status.

## Questions

1. Should overdue stays on the dashboard keep the text "overdue by" (test expectation) or may the card's wording `needs_you.stay.overdue` stand, with the test changed?

## Owner steps left

None.
