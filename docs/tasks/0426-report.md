# 0426 report

Status: review
Branch: task/0426-stripe-connect

## Files changed

- `App/requirements.txt` + `requirements.lock`: `stripe==16.0.1` pinned, hashed (wheel+sdist), installs with `--require-hashes`.
- `App/app/config.py`: STRIPE_MODE/SECRET_KEY/WEBHOOK_SECRET/MONTHLY_API_CALLS + `stripe_enabled()`.
- `App/app/stripe_connect.py`: client factory, monthly API budget (reuses `lock_api_usage` with provider='stripe', no migration), `ensure_account` (controller API, prefill name/email/url only), `onboarding_link`, `sync_account`, `_apply_account_state` (handles SDK object + webhook dict), `verify_and_parse` (raw-body signature), `handle_event` (event-id dedupe via settings keys; account.updated / checkout.session.completed / payment_intent.succeeded / charge.dispute.created with host alert / payout events; unknown types logged, never 5xx).
- `App/app/routes/stripe.py`: `POST /stripe/webhook` (public, signature is the auth; 404 when off; 400 on bad signature), host-guarded `POST /stripe/onboarding/start` + `GET /stripe/onboarding/return` (syncs state; return != verified).
- `App/app/main.py`: router include.
- `App/tests/test_stripe_connect.py`: 9 tests, mocked SDK, real HMAC signature roundtrip.
- `docs/plans/ubyhost-complete-stripe.md`: API-update note (controller params, immutable dashboard type).

## Commands (last lines)

- `pytest tests/test_stripe_connect.py tests/test_payment_request_model.py` -> `22 passed in 1.38s`
- `pytest tests/test_migrations.py tests/test_retention.py` -> `25 passed in 4.98s`
- `context_lint.py` -> `OK`

## Section 7

- [x] stripe pinned+hashed; import with no network.
- [x] Inert when mode=off (route 404s, client raises StripeDisabledError; tested).
- [x] ensure_account/onboarding_link/sync_account/handle_event with audit rows.
- [x] Webhook: raw-body verification (tested with real HMAC), 400 on bad signature, event-id dedupe (tested), fast 2xx.
- [x] Prefill name/email/url only (asserted in test).
- [x] Only brief files changed.

## Deviations

- None material. Webhook `data.object` arrives as dict, sync handles both shapes.

## Owner steps left

- After staging deploy: register the webhook destination (Connected accounts, snapshot) pointing at `https://<staging>/stripe/webhook`; set `UBYHOST_STRIPE_MODE=test`, `UBYHOST_STRIPE_SECRET_KEY`, `UBYHOST_STRIPE_WEBHOOK_SECRET` in the staging env.
- Sandbox validations per the go-live checklist (onboarding triggers, dispute sim, test clocks).
