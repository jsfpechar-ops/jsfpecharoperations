# 0205 report: on/off switch for the stay-fee email

Status: review

## Files changed

- New: `App/app/migrations/0011_stay_fee_emails.sql`, `App/app/stay_fee_auto.py`, `App/tests/test_stay_fee_email_switch.py`
- Edited: `App/app/routes/admin_accounts.py` (POST `/account/stay-fee-emails`), `App/app/routes/admin.py` (`_stay_fee_emails`, context key), `App/app/routes/stay_fees.py` (context key only), `App/app/templates/settings.html`, `App/app/templates/stay_fees.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`
- Not touched: `App/app/mail.py`, `App/tests/test_mail_attachments.py`, `App/app/retention.py`, CSS

## Commands

- `.venv/bin/python -m pytest tests/test_stay_fee_email_switch.py tests/test_stay_fee_list.py tests/test_lifecycle_mail.py tests/test_privacy_first.py -q --tb=short -x`: `37 passed, 1 warning in 11.10s`
- `pytest tests/test_host_i18n.py tests/test_public_copy_i18n.py tests/test_validation_i18n.py`: public copy and validation `12 passed`. `test_host_i18n.py` alone gives `3 failed, 11 passed` with `no such table: apartment`. Run after a DB-initialising test it gives `23 passed`. This is test-order dependence in the existing file, not this change.
- `python3 scripts/context_lint.py`: `context lint: OK`

## Section 7

- [x] Tests pass (see above); lint OK.
- [x] Screenshots at 390/1280/2000 (sidebar open and collapsed) in EN, CS, VI. `report.json` shows 0 problems in each folder.
- [ ] Stay-fee row checked visually only at 390 as a host (EN). The default seed is an admin, where the row is hidden.

## Screenshots

- `/mnt/project-files/design-reset/stay-fee-email/` (EN, admin seed), `cs/`, `vi/`
- `/mnt/project-files/design-reset/stay-fee-email/host/settings-390.png` (host seed, shows the new row, checked, wraps cleanly)
- `/mnt/project-files/design-reset/stay-fee-email/stay-fees-390.png` (line under the summary wraps cleanly)
- CS and VI shots were not opened by eye, only checked by the tool.

## Deviations

- No git commit (the launcher said the orchestrator commits). Executor.md's per-step commits were skipped.
- EN nav label is "Stay fee", not "Stay fees". EN copy says "Stay fee page" in two places. CS and VI names match the nav labels.
- `retention.py` not edited: `onboarding_emails_opt_out` is not listed there, so the brief's condition does not hold. Reviewer to confirm that the new boolean needs no line (rule 2).
- Added `stay_fee_auto` to the `from .. import` blocks of the three route files. The brief did not list this, but it is needed.
- Migration 0011 is used. Next free is now 0012.

## Questions

- Should `retention.py` get a line for `stay_fee_emails_opt_out`?

## Owner steps

None (the migration runs on start).
