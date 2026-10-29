# 0438: Stripe SDK 16 params-dict call convention fix

Status: review
Depends on: 0437 (deployed) | Branch: task/0438-stripe-v2-kwargs-fix

## 1. Objective

Fix the live onboarding failure: SDK 16's client services take a single `params={...}` dict, not top-level kwargs. The 0437 calls passed kwargs (`TypeError: AccountService.create() got an unexpected keyword argument 'contact_email'` — from the production traceback). All StripeClient call sites move to `params=`; test fakes become strict so the wrong convention fails in tests, not in production.

## 2. Context

- Production traceback: `stripe_connect.py:179 create_or_get_account -> _api().v2.core.accounts.create(...) TypeError`.
- Verified against the installed SDK 16.0.1: `v2.core.accounts.create(params, options)`, `account_links.create(params, options)`, `payment_links.create(params, options)`, `accounts.retrieve(account, params, options)` — all signatures checked via `inspect.signature`.
- The 0437 tests passed because the fakes accepted `**kwargs` — the fakes now assert `params is not None`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stripe_connect.py` | edit | account create + account_links create via `params={}` |
| `App/app/payment_links.py` | edit | payment_links.create via `params={}` |
| `App/tests/test_stripe_connect.py`, `App/tests/test_payment_rails.py` | edit | strict fakes (assert the convention) |

## 4. Steps

1. `v2.core.accounts.create(params={...})` with the same 0437 payload (identity/configuration/defaults unchanged).
2. `account_links.create(params={...})`.
3. `payment_links.create(params={...})`.
4. Strict fakes; existing assertions read `created[0]` (already the params dict).

## 5. Do not touch

Payload contents (the v2 shape from 0437 is correct — only the calling convention was wrong). Rails behavior, routes, migration.

## 6. Commands

- `pytest tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payment_request_model.py tests/test_migrations.py tests/test_retention.py tests/test_scheduler.py -q --tb=short` → all passed, 0 skipped.

## 7. Acceptance

- [x] No StripeClient call uses kwargs.
- [x] Fakes reject the kwargs convention (assert params).
- [x] Full payments scope green.

## 8. Stop and ask

None.

## 9. Report

`docs/tasks/0438-report.md` — Status: review.
