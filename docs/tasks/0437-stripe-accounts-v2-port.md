# 0437: Stripe Accounts v2 port + company hosts + webhook-event sweep

Status: review
Depends on: 0428, 0435, 0436 (merged; deployed) | Branch: task/0437-stripe-v2-port

## Why

Three defects in the deployed Stripe integration, found live:
1. **Accounts v1 creation is disabled on new platforms** (proved on the owner's account: the CLI trigger failed with "Create connected accounts with POST /v2/core/accounts instead") — the deployed `Account.create(controller=...)` call would 400 on every onboarding.
2. **Company hosts (s.r.o.) had no path** — entity_type was hardcoded individual; representatives/beneficial ownership would never be collected.
3. **`stripe_webhook_event` grows forever** — one dedupe row per delivered event, no pruning.

## Changes

- `App/app/stripe_connect.py`: `_client()` returns a real `StripeClient`; `_api()` keeps its 0428 contract (rails unchanged) but returns the client. Account creation via `client.v2.core.accounts.create` with `identity` (business_details = registered_name/url/product_description, entity_type from the host's choice), `dashboard="express"`, `configuration.merchant` (card_payments + stripe_balance.payouts), `defaults.responsibilities` (fees_collector=stripe, losses_collector=stripe — the 1:1 map of the v1 controller design; immutable after creation). Account Links + account retrieve on the client's v1-style services (v2-account-id compatible). `sweep_webhook_events(today)` prunes dedupe rows older than 30 days.
- `App/app/payment_links.py`: call-site `.PaymentLink.create` → `.payment_links.create` (client service).
- Migration **0032**: `legal_entity.business_type` (individual/company, default individual) — explicit host choice, never inferred from IČO.
- `App/app/scheduler.py`: `stripe_sweep` daily 04:15 — request expiry + webhook-event pruning.
- Tests: `fake_stripe` fixture reshaped to the client (v2 accounts + v1-style services); new tests: v2 create params, company/individual entity_type, sweep aging. `test_payment_rails` fake likewise.

## Verification

- 90 passed across stripe/rails/model/migrations/retention/scheduler suites; app imports; context lint OK.
