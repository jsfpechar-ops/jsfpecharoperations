# 0441 report

Status: review
Branch: task/0441-connect-new-tab

## Files changed

- `App/app/templates/payments.html` — the connect form posts with `target="_blank" rel="noopener"`.

## Commands (last lines)

- `pytest tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payments.py tests/test_payments_dashboard.py` -> 26+11+21 passed, 0 skipped.

## Deviations

None.

## Owner steps left

Merge + deploy; "Open Stripe" opens the onboarding in a new tab (no skeleton hang).
