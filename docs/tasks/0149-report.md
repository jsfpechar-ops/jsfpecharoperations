# 0149-fix-1 report

Status: blocked

## Files changed
- App/tests/test_dashboard_queue_copy.py, test_deadline_after_reporting.py, test_host_language.py, test_overhaul.py (step 1)
- App/app/static/host2.css (step 2)
- App/app/static/host-design0123.css (step 3)
- App/tests/test_host_stay_actions_browser.py, test_host_quiet_dashboard_browser.py (step 4)

## Commands (last lines)
- Step 1: `.venv/bin/python -m pytest tests/test_dashboard_queue_copy.py tests/test_deadline_after_reporting.py tests/test_host_language.py tests/test_overhaul.py -q --tb=line` gives `57 passed, 1 warning in 4.01s`
- Step 2: `python3 scripts/design_lint.py` gives `design lint: OK`; brace count `0`
- Step 3: `grep -c dashboard-row-actions` gives `1`; brace count `0`
- Step 4: `ruff check --select E9,F63,F7,F82,F401,F841 tests/` gives `All checks passed!`
- Step 5 (browser run, 5 files, -rs): `2 failed, 9 passed, 1 warning in 91.92s`

## Failures
1. `tests/test_host_list_layouts_browser.py:105` (test_stays_pills_and_deadlines_stay_on_one_line), fails on rerun:
   `E   AssertionError: ('cs', 1280, {'pill': True, 'deadline': True, 'height': 89, 'name': 12, ...})`
   `E   assert 89 <= 72`
   Width 1280, locale cs. Stop rule (brief section 8) applies.
2. `tests/test_host_list_page_layout_browser.py:155` (properties [40,42]): the listed known local failure, ignored.

## Not done
- Screenshot capture (`UBYHOST_CAPTURE_0079=1` run), copy to shots/0149, md5 check: not run, because the browser run stopped at the 72 px failure.
- By-eye list (step 6): not done.
- PR not opened: this run may not push.

## Deviations
Done: steps 1 to 4. Left: step 5 (capture, copy, reset), step 6 (report by eye, PR).

## Questions for orchestrator
- The stay row at cs/1280 with pill and deadline is 89 px high after step 2 (padding 0 on the table cell and the new 1024 to 1279 cell padding). Decide whether the 72 px limit or the row layout needs a change before rerunning.
- Known follow-ups from the brief (section 8): phone badge squeeze, `d. m.` date format.

## Owner steps left
- None until the orchestrator decides on the 72 px failure.
