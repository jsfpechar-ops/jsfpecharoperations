# 0222 report

Status: review

## Files changed

- App/app/stay_fee_auto.py: `period_label`, `check`, `confirm` (imports added)
- App/app/routes/stay_fees.py: `stay_fee_finalize` calls `stay_fee_auto.check` (the four inline lines replaced, nothing else)
- App/app/mail.py: `stay_fee_report`, `stay_fee_blocked` in `KINDS` and `HOST_KINDS`
- App/app/mail_notify.py: `build_stay_fee_report`, `queue_stay_fee_report`, `build_stay_fee_blocked`, `queue_stay_fee_blocked`
- App/app/host_i18n.py, App/app/host_vi_i18n.py: the `mail.stay_fee*` keys (en, cs, vi) from the brief table; Addendum 8: `notification.mail_kind.stay_fee_report` and `stay_fee_blocked` (en, cs, vi)
- App/tests/test_stay_fee_auto.py (new): 9 tests
- App/tests/test_claim_mail.py: Addendum 7, the two kinds added to the pinned set (nothing else)

Not committed (per orchestrator instruction).

## Commands (last lines)

1. `pytest tests/test_stay_fee_auto.py tests/test_stay_fee_finalize.py tests/test_mail_attachments.py tests/test_notification_copy.py tests/test_claim_mail.py`
   `75 passed, 5 warnings in 5.45s`
2. Mail row: `pytest tests/test_ses_mail.py $(ls tests/test_mail_*.py tests/test_*_mail.py)`
   `240 passed, 6 warnings in 6.75s`
3. i18n: `pytest tests/test_stay_fee_auto.py tests/test_host_i18n.py tests/test_public_copy_i18n.py tests/test_validation_i18n.py`
   `34 passed, 2 warnings in 2.54s`
4. `python3 scripts/context_lint.py`
   `context lint: OK`

## Checklist (section 7)

- [x] All above pass.
- [x] `test_stay_fee_finalize.py` unchanged and green.
- [x] Report pastes the EN text part of one built report mail (in the handback of the first run).

## Deviations

1. The first run's deviations 1 and 2 are resolved by Addendum 7 and 8. The pinned-kinds test and the `mail_kind` copy now pass.
2. `tests/test_host_i18n.py` (and the other i18n files) fail when run alone with "no such table: apartment". The schema is created by an earlier test file, so the file passes after `test_stay_fee_auto.py`. This is order dependence, not caused by 0222. Not changed.
3. `period_label` added to `stay_fee_auto.py` as the brief states; the mail builders use `_block_button` (the wrapped row) rather than `_button`, as `build_workspace_deletion` does.

## Questions

None. The Addendum copy was used as given.

## Owner steps left

None.

## Review hints

Risk list: the `stay_fee_finalize` diff (behaviour-neutral, test_stay_fee_finalize green), `confirm`, the idempotency keys.
