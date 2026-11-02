# 0762 report: saved services with one-tap payment requests

Status: review

## Files changed
- App/app/payment_services.py (new): list / get / add / remove, JSON in settings key payment_services:<owner>, max 20.
- App/app/routes/payments.py: POST /payments/services and POST /payments/services/{id}/delete; prefill from ?service=.
- App/app/payment_links.py: product_name uses guest_note for Custom requests.
- App/app/templates/payments.html: services section, id="new-request", prefilled amount, Custom and description, list shows description.
- App/app/host_i18n.py: en + cs keys.
- App/tests/test_payment_services.py (new), App/tests/test_payment_rails.py (one test).
- docs/design/pages/payments.md: one line.
- docs/tasks/screenshots-0762/services-390.png (new).

## Commands (§6)
1. `pytest tests/test_payment_services.py tests/test_payment_rails.py tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payments_consent.py -k "not fits_a_phone"` : 84 passed, 1 deselected.
2. Browser run (UBYHOST_REQUIRE_BROWSER=1): 13 passed, 4 deselected, 0 skipped.
3. `scripts/design_lint.py`: design lint: OK.
4. `scripts/context_lint.py`: context lint: OK.

## §7
- [x] Save, see, remove services on /payments; max 20.
- [x] Request payment opens the form with amount, Custom, description.
- [x] Custom request product_name uses the description.
- [x] §6 passes; services-390.png shows the Czech section, no overflow.

## Deviations
- None to code. Restored docs/tasks/screenshots-0729/payments-setup-390.png (rewritten by the browser run) with git checkout; not committed.
- ui-btn-quiet passed design lint; kept.
- A py_compile check was skipped (venv path); the test run covers imports.

## Questions
- None.

## Owner steps left
- Review and merge via scripts/merge-pr-on-green.sh; deploy manually.
