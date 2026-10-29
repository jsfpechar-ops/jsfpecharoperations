# 0437: Stripe Accounts v2 port + company hosts + webhook-event sweep

Status: review
Depends on: 0428, 0435, 0436 (merged; deployed) | Branch: task/0437-stripe-v2-port

## 1. Objective

Fix three defects in the deployed Stripe integration: (1) Accounts v1 creation is disabled on new platforms — the deployed `Account.create(controller=...)` 400s on every onboarding (proved live); (2) company hosts (s.r.o.) had no path to representative/beneficial-ownership KYC; (3) the webhook dedupe table grows forever.

## 2. Context

- The live proof: the owner's CLI trigger failed with "Create connected accounts with POST /v2/core/accounts instead." Accounts v2 request shape verified against docs.stripe.com (29 Oct) and the installed SDK 16.0.1 (`client.v2.core.accounts.create`).
- v1 controller → v2 responsibilities map (1:1, from Stripe's own property map): `fees.payer=account` → `fees_collector=stripe`; `losses.payments=stripe` → `losses_collector=stripe`; Express dashboard → `dashboard="express"`; requirement collection follows automatically. Responsibilities are immutable after creation.
- Entity type cannot be inferred from IČO (OSVč individuals have one), so it is an explicit host choice.
- Stripe retries webhook delivery at most 3 days; 30-day pruning is a generous margin.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stripe_connect.py` | edit | `_client()` StripeClient; account create via v2; account_links/accounts call-sites; `sweep_webhook_events` |
| `App/app/payment_links.py` | edit | `payment_links.create` call-site |
| `App/app/migrations/0032_legal_entity_business_type.sql` | create | `legal_entity.business_type` |
| `App/app/scheduler.py` | edit | `stripe_sweep` job (daily 04:15) |
| `App/tests/test_stripe_connect.py`, `App/tests/test_payment_rails.py` | edit | client-shaped fakes; new tests |

## 4. Steps

1. Migration 0032: business_type column, default individual, CHECK constraint.
2. `stripe_connect`: `_client()` returns StripeClient; `_api()` keeps the 0428 contract (rails unchanged) and returns the client; account creation via `client.v2.core.accounts.create` with `identity` (business_details: registered_name/url/product_description; entity_type from business_type), `dashboard="express"`, `configuration.merchant` (card_payments + stripe_balance.payouts), `defaults.responsibilities` (fees=stripe, losses=stripe); Account Links and account retrieve on the client's v1-style services (v2-id compatible); `sweep_webhook_events(today)` prunes rows older than 30 days.
3. `payment_links.send`: `.PaymentLink.create` → `.payment_links.create`.
4. Scheduler: `stripe_sweep` daily 04:15 — request expiry + webhook-event pruning.
5. Tests: fakes reshaped to the client (v2 accounts + v1-style services); new: v2 create params, company/individual entity_type, sweep aging.

## 5. Do not touch

Rails behavior (0435/0436 request flows), invoices, stay fees, retention, db.py SCHEMA (migration only). No new dependency (stripe 16.0.1 already pinned+hashed).

## 6. Commands

- `python -m pytest tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payment_request_model.py tests/test_migrations.py tests/test_retention.py tests/test_scheduler.py -q --tb=short` → `90 passed`
- `python3 scripts/context_lint.py` → OK

## 7. Acceptance

- [x] Account creation uses v2 with responsibilities (fees=stripe, losses=stripe), dashboard=express, merchant capabilities; no v1 controller params.
- [x] Company/individual entity_type flows from `legal_entity.business_type` (default individual).
- [x] `sweep_webhook_events` prunes rows older than 30 days; scheduler job registered.
- [x] All call sites use StripeClient services; rails unchanged in behavior.
- [x] 90 tests passed; lint OK.

## 8. Stop and ask

None — none triggered.

## 9. Report

`docs/tasks/0437-report.md` — Status: review.
