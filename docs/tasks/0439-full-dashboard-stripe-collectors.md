# 0439: Accounts v2 final configuration — full dashboard + Stripe collectors

Status: review
Depends on: 0438 (merged; deployed) | Branch: task/0439-full-dashboard-stripe-collectors

## 1. Objective

Make account creation actually succeed on the platform: the Express+Stripe-collectors pairing is preview-only and rejected by the live API. Adopt the live-verified working configuration (owner decision): full dashboard + Stripe collectors, with the v2 payload corrections found by live probing.

## 2. Context

Live probes against the platform account (29 Oct, real API calls):
- Express + stripe collectors -> "This account configuration is not supported" (even with the preview API version).
- Full + stripe collectors -> account created.
- Express + application collectors -> works but = platform liability; rejected on design grounds.
- Field corrections: business_details has no product_description and no url ("Unknown field"); payouts is not a capability (merchant config carries it); merchant.mcc is the explicit MCC lever.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stripe_connect.py` | edit | dashboard "full"; business_details = registered_name only; merchant capabilities = card_payments only |
| `App/tests/test_stripe_connect.py` | edit | assertions match the adopted configuration |
| `docs/plans/ubyhost-complete-stripe.md` | edit | live-probed configuration record |
| `docs/context/decisions.md` | edit | 0439 decision line |

## 4. Steps

1. `dashboard: "full"` in the v2 create (Express+Stripe is preview-only).
2. business_details: registered_name only.
3. Merchant capabilities: card_payments only (payouts come with the merchant configuration).
4. Tests updated; full payments scope green.

## 5. Do not touch

Responsibilities (unchanged: stripe/stripe), rails, routes, migrations.

## 6. Commands

- `pytest tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payment_request_model.py tests/test_migrations.py tests/test_retention.py tests/test_scheduler.py -q --tb=short` -> `90 passed`
- Live probe with the final code's exact payload -> `LIVE CREATE OK: acct_1UVwnLB9XCg26V91`

## 7. Acceptance

- [x] dashboard="full", collectors stripe/stripe, business_details registered_name only.
- [x] Live API accepts the exact payload the code sends (account created).
- [x] 90 tests passed.

## 8. Stop and ask

None.

## 9. Report

`docs/tasks/0439-report.md` — Status: review.
