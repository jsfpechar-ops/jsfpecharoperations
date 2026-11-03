# 0901 report: credit note on partial refund (executor run 2)

Status: review

## Files changed
- App/tests/test_booking_cancel.py
- App/app/booking_manage.py
- App/app/templates/booking_manage.html
- App/tests/test_booking_manage_browser.py (teardown fix: invoice_purge_unlock set at cleanup start, removed before stripe_account delete)
- docs/context/known-issues.md (K-BS01 row deleted)
- docs/context/decisions.md (0901 line added; older lines shortened, meaning kept)
- docs/tasks/0901-report.md
- docs/tasks/screenshots-0901/guest-correction-390.png (new)

Not committed: docs/tasks/screenshots-0821/guest-390.png (modified by the browser run, unrelated).

## Commands
- Browser: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_manage_browser.py -q -rs --tb=short` gave `5 passed in 5.87s`, 0 skipped, no teardown error.
- Step 4 pytest (tests/test_booking_credit_note.py, test_booking_cancel.py, test_booking_invoice.py, test_booking_site.py, test_host_i18n.py, test_flash_literals.py): `73 passed, 1 warning in 3.70s`.
- `python3 scripts/context_lint.py`: `context lint: OK` (only WARN lines about open briefs).

## Deviations
- Payer gross split formula, description from translate inside correct_partial, caller catches Exception, test_partial_refund_moderate_late changed by owner decision (as recorded in the previous run).
- decisions.md was over the 2200-token cap; shortened older lines by trimming filler words only.

## Questions / owner steps left
- Owner: merge via scripts/merge-pr-on-green.sh after CI is green.
