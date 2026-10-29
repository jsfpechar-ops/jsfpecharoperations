# 0438 report

Status: review
Branch: task/0438-stripe-v2-kwargs-fix

## Files changed

- `App/app/stripe_connect.py` — account + account_links create via `params={}`.
- `App/app/payment_links.py` — payment_links.create via `params={}`.
- `App/tests/test_stripe_connect.py`, `App/tests/test_payment_rails.py` — strict fakes.

## Commands (last lines)

- full payments scope: all passed (50 in the three core suites; 90 total incl. migrations/retention/scheduler), 0 skipped.
- `from app.main import app` — ok.

## Deviations

None. Payloads unchanged from 0437; calling convention only.

## Root cause note

The 0437 fakes accepted `**kwargs`, hiding the convention mismatch. Fakes now assert `params` — the same mistake cannot pass tests again.

## Owner steps left

Merge + deploy, then retry the dashboard "connect payments" button — the onboarding link should generate and redirect to Stripe's hosted form.
