# 0439 report

Status: review
Branch: task/0439-full-dashboard-stripe-collectors

## Files changed

- `App/app/stripe_connect.py` — dashboard "full"; business_details registered_name only; merchant capabilities card_payments only.
- `App/tests/test_stripe_connect.py` — assertions match.
- Plan doc + decisions line.

## Commands (last lines)

- payments scope: `90 passed in 11.37s`
- live probe: `LIVE CREATE OK: acct_1UVwnLB9XCg26V91` (exact code payload, real API)

## Deviations

None. Express remains available for a future switch only with application collectors (owner rejected: platform liability).

## Owner steps left

Merge + deploy; the "connect payments" button should now create the account and redirect to Stripe's hosted onboarding.
