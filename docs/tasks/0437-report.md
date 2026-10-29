# 0437 report

Status: review
Branch: task/0437-stripe-v2-port — PR to follow.

## Files changed

- `App/app/stripe_connect.py` — v2 client + account creation, responsibilities map, company/individual entity_type, account_links/accounts call-sites, sweep_webhook_events.
- `App/app/payment_links.py` — payment_links.create call-site.
- `App/app/migrations/0032_legal_entity_business_type.sql`.
- `App/app/scheduler.py` — stripe_sweep job (04:15 daily).
- `App/tests/test_stripe_connect.py` — client-shaped fakes; 3 new tests (v2 params, company, sweep).
- `App/tests/test_payment_rails.py` — client-shaped fake.

## Commands (last lines)

- full payments scope: `90 passed in 11.57s`
- `from app.main import app` — ok
- `context_lint.py` — OK

## Deviations

None. The 0428 naming (enabled(), StripeOff, _api()) kept so the merged rails (0435/0436) work unchanged.

## Owner steps left

Merge + deploy; then dashboard onboarding via /payments/connect/start works against Accounts v2. Register the webhook destination at https://ubyhost.com/webhooks/stripe if not yet done.
