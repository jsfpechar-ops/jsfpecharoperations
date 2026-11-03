# 0799 report: remove stay-fee sent/paid marks

Status: review (not committed; orchestrator commits)

## Files changed
- App/app/routes/stay_fees.py: removed STAY_FEE_STATUSES sent/paid, `_row_status` frozen returns "saved", POST `/sent` and `/paid` handlers, `_filing_for_action` (only used by them), three send_panel keys.
- App/app/templates/stay_fee_detail.html: removed the marks block (PDF button kept).
- App/app/host_i18n.py (22 lines), App/app/host_vi_i18n.py (11 lines): the 11 keys from §3 in en/cs/vi.
- App/app/static/host.css, host2.css: `.fee-send-marks*` rules deleted.
- App/tests/test_stay_fee_send_panel.py: deleted 3 mark tests (list-status, paid-without-sent, other-owner 404 on /sent).
- App/tests/test_design_alerts_phone.py: one assertion on the deleted `.fee-send-marks` CSS removed.
- Kept: DB columns, stay_fee_filing.py dict keys, retention.py, payments.status.* (not stay fee), invoices.

## Grep (step 1) after edit
Only hits: payments.status.sent/paid (other feature), stay_fee_filing.py `sent_message_id` (DB read), retention.py comment, invoice filter test. Clean.

## Commands
1. `pytest tests/test_stay_fee*.py tests/test_fee_setup_compatibility.py tests/test_host_i18n.py tests/test_privacy_first.py`: 3 failed, 175 passed. Failing: test_stay_fee_pay_steps::test_steps_are_locked_until_the_period_is_confirmed, test_fee_setup_compatibility::test_invalid_account_saves_nothing_and_keeps_what_was_typed, ::test_set_up_link_opens_visible_editor_and_save_returns_to_the_list. Cause is in 0796's area (stay_fees.html "Set up stay fee"/fee-pay, settings reporting group), not in my files. Same three as 0796's report.
2. `pytest tests/test_design_lint.py`: 1 failed (T3 class not in catalog: submissions-page, housebook-page, invoices-page, stay-fees-toolbar, stay-fees-page, fee-pay-h, small). None in stay_fee_detail.html; stay_fees.html and other pages are not mine.

## Deviations
- Did not commit (user instruction overrides executor commit step); no PR opened.
- Editing test_design_alerts_phone.py is outside the brief's test list; it is the only test that asserted the deleted CSS.

## Questions
- `.fee-send-form` CSS rules in host2.css are now unused (the mark form is gone). Left in place, not named by the brief. Delete?

## Owner steps left
None.
