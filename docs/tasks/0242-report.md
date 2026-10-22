# 0242 report

Status: review

## Files changed (uncommitted)

- App/app/templates/stay_fees.html: list step 2 databox button is `ui-btn ui-btn-primary fee-databox-send`
- App/app/templates/stay_fee_detail.html: `#fee-send` databox button primary with `fee-databox-send`; header Download PDF secondary when `send_panel.databox_send`
- App/tests/test_databox_send_ui.py: gateway-on asserts primary on list and report, report has 2 `ui-btn-primary` (databox + list filter `filter-apply`); gateway-off asserts no `fee-databox-send`
- App/tests/test_stay_fee_pay_steps_browser.py: `_CHECK_JS` primaries excludes `.fee-databox-send`
- docs/context/decisions.md: one line replaced (wording shortened to pass the 2200-token cap)

## Commands

- `App/.venv/bin/python -m pytest tests/test_databox_send_ui.py tests/test_design_fees*.py tests/test_stay_fee_send_panel.py tests/test_stay_fee_pay_steps.py -q --tb=short -x -k "not browser and not geometry" -rs` : `14 passed, 1 deselected, 1 warning`, 0 skipped
- `python3 scripts/context_lint.py`: decisions.md OK. FAIL only on `docs/tasks/0242-databox-send-primary.md: missing section '## 8. Stop and ask'` (the brief has no §8; not edited)

## Section 7

- [x] Gateway on: databox primary on list and report; report has one primary outside the list filter (test asserts the filter-apply is the other)
- [x] Gateway off: pages unchanged (test asserts no `fee-databox-send`)
- [x] Scoped tests pass; lint passes except the brief §8 issue

## Deviations

- Brief §9 says "Do not commit"; executor guide says commit per step. Followed the brief: nothing committed, no PR opened.
- Browser tests (`test_stay_fee_pay_steps_browser.py`) not run (orchestrator per brief §6). Hard rule 7 screenshots not taken.
- Report page has a second `ui-btn-primary` from `_list_filter.html` (`filter-apply`), as the brief anticipated; test assertion adjusted to count 2 and check the filter is the other one.
- decisions.md line shortened ("POST draft; email links; primary button, list exception (owner, 0242)") to fit the cap.
- Step 2 `send_panel` scope confirmed (passed from routes/stay_fees.py:387).

## Owner steps left

- Fix the brief: add `## 8. Stop and ask` (lint error), or the orchestrator does.
- Run browser tests and take 390 px screenshots, then commit and open the PR.

## Orchestrator review (2026-10-22)

Added §8 to the brief (lint). Browser run with gateway on: list and report at 390/820/1280/2000 in EN/CS/VI, no sideways scroll, no extra primary on the report. Scoped set 202 passed, 0 skipped. Shots: project files databox-return/send-button/.
