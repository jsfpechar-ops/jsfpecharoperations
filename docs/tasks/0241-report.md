# 0241 report

Status: review

## Files changed

- App/app/routes/stay_fees.py: `filing_id` and `databox_send` added to overview rows; new helper `_list_filing_id` (placed above `_send_panel_context`).
- App/app/templates/stay_fees.html: step 2 wrapped in `div.action-group`, with the "Send by data box" form (hidden unless `period.databox_send`) before the Download link.
- App/app/templates/stay_fee_detail.html: `#fee-send` shows the button, the databox lede and "Or send it by hand" when `send_panel.databox_send`; else the old lede.
- App/app/mail_notify.py: `build_stay_fee_report(databox_send=False)`; with `databox and databox_send` uses `mail.stay_fee.step_send_databox` and appends `#fee-send` to the report URL. `queue_stay_fee_report` passes `isds_gateway.configured()`.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: the 4 keys per language (EN, CS, VI), mail key included for VI.

## Tests

- Step 6 done: App/tests/test_databox_send_ui.py (4 tests: gateway off, gateway on with form on list and report plus email step, gateway on without council data box, not frozen). Fixtures copied from test_databox_send.py with a distinct username; `isds_gateway.configured` monkeypatched.
- `cd App && .venv/bin/python -m pytest tests/test_databox_send_ui.py tests/test_databox_send.py tests/test_stay_fee_pay_steps.py tests/test_stay_fee_send_panel.py tests/test_stay_fee_auto*.py tests/test_design_fees*.py tests/test_host_i18n.py -q --tb=short -x`: 56 passed, 1 deselected (`test_send_panel_geometry_and_screenshots`, Playwright Chromium not installed in this container; orchestrator runs browser tests).
- `python3 scripts/context_lint.py`: OK (only pre-existing WARN lines).
- No screenshots (orchestrator).

## Acceptance (§7)

- [x] Gateway off: no form, no new email line (test_gateway_off_no_databox_form_and_no_email_step). Byte-identical not checked.
- [ ] Gateway on: code in place, not verified in a browser.
- [ ] Tests and lint: not run.
- [ ] Screenshots: orchestrator.

## Deviations

- Done: steps 1 to 5. Left: step 6 (App/app/tests/test_databox_send_ui.py, not created) and the §6 test run and lint.
- Step 1: `filing_id` is computed in a line before `rows.append` so `databox_send` can be False when there is no filing. This is the only change from the brief's literal text.
- Step 1 import: `isds_gateway` is already imported in `stay_fees.py`, so no import added there.
- The brief's "gateway off" check for `queue_stay_fee_report` is not covered by a test yet.
- The user said do not commit, so steps were not committed (executor.md's per-step commit overridden). No PR opened.
- The first `queue_stay_fee_report` import edit matched two identical lines in `mail_notify.py`; the second match was the wrong one, and it was fixed to `queue_stay_fee_report` only (line ~1022). Nothing else changed.

## Questions

- Should the test file (step 6) be written by the next session, or is it fine to run §6 after it?

## Owner steps left

- None until the orchestrator runs the browser tests and screenshots.

## Orchestrator review (2026-10-22)

Diff read. Scoped set incl. browser tests passes, 0 skipped. Gateway-on screenshots (council data box set): list step 2 and report #fee-send at 390/820/1280/2000 in EN/CS/VI, no sideways scroll, in project files databox-return/send-button/.
