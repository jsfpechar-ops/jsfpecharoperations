# 0333 report

Status: review

## Files
- App/app/routes/havel.py: `_forward` helper above `havel_send`; forwards on week, month, conversation cap and `AIBudgetError` (`budget_<reason>`).
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `havel.forwarded` (en, cs, vi).
- App/tests/test_havel_limit_forward.py (new): 8 tests.

## Commands (last lines)
- `tests/test_havel_limit_forward.py`: 8 passed.
- `tests/test_havel*.py test_claim_mail test_ai* test_static_versions test_host_i18n test_no_em_dashes`: 152 passed, 2 warnings.
- `scripts/design_lint.py`: design lint: OK.
- `scripts/context_lint.py`: context lint: OK (2 WARN lines, not blocking).

## Section 7
- [x] Week, month, conversation and budget limits send one `havel_support` mail, no model call.
- [x] Burst, pause, greetings never forward.
- [x] With 3 support sends this week: normal limit text, no mail.
- [x] `havel.forwarded` in en, cs, vi.

## Deviations
- Base commit: origin/main is 1de57a7, not 4057916 (brief not updated).
- Helper uses `host_i18n.lang_from_request(request)` instead of `request.state.lang` (repo pitfall).
- Test fixture imports `USERNAME` from test_submission_retry_cap (the brief's `hostuser` does not exist).
- Tests use `?lang=en` and `html.unescape`.

## Questions
- None.
