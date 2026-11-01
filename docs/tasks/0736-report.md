# 0736 report (executor, Haiku 5.5)

Status: blocked
Done: step 1, item 2 only (test_property_navigation_browser.py). Left: items 1, 6 (step 1), steps 2, 3, 4.

## Files changed
- App/tests/test_property_navigation_browser.py: item 2. Save from section=automation now asserts section=reporting.

## Item 1 (unsaved changes): not fixed
- Brief fix applied (read loaded_status after the #sec-lock summary click). Still fails: `assert 'Enabled' == ''` at tests/test_host_unsaved_changes_browser.py:283 (en/cs, 360 and 1280). Reverted, so the file is unchanged.
- Brief's diagnosis does not match: the status text reads '' even with the section open. Needs owner or orchestrator review.

## Item 6 (controls): not fixed
- tests/test_host_property_controls_browser.py:448 fails before the `select_option("other")` step: `#label_other` is visible by default, so the brief's "section closed" cause does not hold. Reverted, so the file is unchanged.
- test_property_and_operator_controls_render_and_work_in_browser also fails. Not named in the brief; not investigated.

## Test results (chromium, -k "not webkit")
- tests/test_property_navigation_browser.py: `12 passed in 15.25s`
- tests/test_host_unsaved_changes_browser.py: `4 failed` (save_bar_discard, the 4 parametrized cases), line 283 as above
- tests/test_host_property_controls_browser.py: `2 failed` (see item 6)

## Not run
- Items 3, 4, 5, 7, 8, section 6 commands, screenshots. Stopped at the step-1 failures per executor rules.
- webkit not installed (not run).

## Questions
1. Item 1: the status element may only fill on toggle. Should the test click the door-code switch first, then assert the loaded text, or compare against a known string?
2. Item 6: why is #label_other visible at line 448 when the platform is the default? Is the expected state wrong, or was the brief's failure from another test?
3. Report path: the executor doc says docs/tasks/NNNN-report.md; the brief says section "0736" in docs/tasks/0536-report.md. This report uses docs/tasks/0736-report.md.

## Owner steps left
- None yet. No push, no PR (status blocked).
