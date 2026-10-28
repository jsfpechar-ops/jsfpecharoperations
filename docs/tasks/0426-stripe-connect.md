# 0426: Stripe Connect module — provisioning, onboarding links, webhooks (P1.2)

Status: in-progress
Depends on: 0425 (merged) | Base commit: 05a69e24+ | Branch: task/0426-stripe-connect
Executor: owner-authorized chat AI ("you implement it") | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the `stripe` SDK (pinned+hashed) and `App/app/stripe_connect.py`: create Express connected accounts prefilled from `legal_entity` (current `controller` API, NOT deprecated `type=express`), create Account Links (single-use onboarding URLs), and a webhook route `/stripe/webhook` with raw-body signature verification. All of it inert unless `UBYHOST_STRIPE_MODE` is `test`/`live`. No host UI yet (0427+).

## 2. Context

- Config (docs/ENVIRONMENT.md, "Connect payments" section): `UBYHOST_STRIPE_MODE` (`off`/`test`/`live`, default `off`), `UBYHOST_STRIPE_SECRET_KEY` (`sk_test_...`; env-only, never git), `UBYHOST_STRIPE_WEBHOOK_SECRET` (`whsec_...`).
- Current API shapes (verified against docs.stripe.com 2026-10-28):
  - Accounts create: `controller[fees][payer]=account`, `controller[losses][payments]=stripe`, `controller[stripe_dashboard][type]=express`, `controller[requirement_collection]=stripe`; prefill `business_profile.url` + `business_profile.product_description`, `country=CZ`, `email`, `business_type`; dashboard type is immutable.
  - Account Links: params `account`, `type=account_onboarding`, `refresh_url`, `return_url`, `collection_options[fields]=eventually_due`; single-use, minutes-long expiry; `return_url` ≠ verified — re-retrieve the account and check `requirements`.
  - Webhooks: verify signature over the RAW body with `stripe.Webhook.construct_event`; return 2xx fast; dedupe by event id; Connect charge events arrive on the connected-accounts destination.
- Model (0425): `stripe_account` table mirrors status only (`onboarding_state`, `charges_enabled`, `payouts_enabled`, `requirements_json`); never secrets or documents. `payment_request.py` is the requests model.
- Access pattern: routes use `security.protect_host_post` (host-scoped POST); the webhook route is the one public POST route — CSRF-exempt like other webhook/public routes (check `guest.py` for how public POST routes skip the host guard).
- API-call cap pattern: follow `UBYHOST_TTLOCK_MONTHLY_CALLS` in `App/app/ttlock.py` (or wherever the shared budget guard lives) for `UBYHOST_STRIPE_MONTHLY_API_CALLS`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/requirements.txt` + `requirements.lock` | edit | add `stripe` (pin; hashed lock entries) |
| `App/app/config.py` | edit | stripe mode/secret/webhook-secret env reads + `stripe_enabled()` helper |
| `App/app/stripe_connect.py` | create | client factory, ensure_account, onboarding_link, verify_webhook, handle_event |
| `App/app/routes/stripe.py` | create | `POST /stripe/webhook` (public) + `POST /stripe/onboarding/start` (host) |
| `App/app/main.py` | edit | include the router |
| `App/tests/test_stripe_connect.py` | create | mocked-SDK tests |
| `docs/plans/ubyhost-complete-stripe.md` | edit | §12 note: `type=express` deprecated → controller; dashboard immutable |
| `docs/context/decisions.md` | edit | stripe SDK decision line exists already; add 0426 line if needed |

## 4. Steps

1. `pip-compile` or hand-pin the newest `stripe` SDK into `requirements.txt`; regenerate `requirements.lock` with hashes (use the repo's existing pip-compile command if documented; otherwise `pip install stripe==<ver>` + `pip-compile`). Verify import works.
2. `config.py`: `STRIPE_MODE = os.environ.get("UBYHOST_STRIPE_MODE", "off")`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (all `.strip()`); `def stripe_enabled() -> bool` = mode in (test, live) and secret key set. Module-level like the Meta/Turnstile vars.
3. `stripe_connect.py`:
   - `_client()` → lazy `stripe.StripeClient(config.STRIPE_SECRET_KEY)` (or module `stripe.api_key` pattern — match how the app handles other SDKs, e.g. anthropic in `ai.py`); raise a clear error if `stripe_enabled()` is false.
   - `ensure_account(owner_user_id) -> dict` — find `stripe_account` row for (owner, mode); if none, create the Express account via API prefilled from `legal_entity` (name, email=contact_email, country CZ, business_type individual default, `business_profile.url` from app_base_url, product_description "Short-term accommodation rental by the host (ubyhost page)"), insert the mirror row `onboarding_state='pending'`, `db.audit("stripe_account_created", ...)`. NEVER send ID numbers, DOB, address — Stripe's onboarding collects those; prefill is name/email/url only.
   - `onboarding_link(owner_user_id, return_url, refresh_url) -> str` — `ensure_account`, then Account Link create; store nothing secret; audit; return the single-use URL.
   - `sync_account(owner_user_id) -> dict` — retrieve the account, update the mirror row: charges_enabled, payouts_enabled, onboarding_state (complete if charges_enabled and payouts_enabled and no past_due; action_required if requirements.currently_due/past_due; rejected if `disabled_reason` mentions rejected), requirements_json = compact JSON of `requirements`.
   - `verify_and_parse(payload: bytes, sig_header: str)` → `stripe.Webhook.construct_event(payload, sig, config.STRIPE_WEBHOOK_SECRET)`; raise on failure.
   - `handle_event(event) -> None` — dedupe by event id (a `stripe_event_seen` check — settings key or audit row check; pick the lightest existing pattern), then: `account.updated` → find mirror row by stripe_account_id → update status fields; `checkout.session.completed` / `payment_intent.succeeded` → find payment_request by stripe ids → `payment_request.mark_paid(via="card")`; `charge.dispute.created` → audit + alert row (existing `alerts` module) for the owner; `payout.paid`/`payout.failed` → audit. Unknown types: log, 200.
   - API-call budget: wrap client calls with the monthly-cap guard like TTLock's.
4. `routes/stripe.py`:
   - `POST /stripe/webhook` — public (no host guard): `await request.body()` → verify → handle → return `{"ok": True}`; signature failure → 400; parse failure → 400. No CSRF token (Stripe can't send one) — document why in the route docstring; route only active when `stripe_enabled()`.
   - `POST /stripe/onboarding/start` — host guard; calls `onboarding_link` with return/refresh URLs built from `config.app_base_url()`; redirects to the link.
5. `main.py`: `app.include_router(stripe_router)` next to the other routers.
6. Tests (mock the SDK — no network): config gating (off = inert), ensure_account creates prefilled account + mirror row, sync_account maps states, webhook route: valid signature → handled, bad signature → 400, duplicate event id → handled once, account.updated updates the mirror. Use `stripe.Webhook.construct_event`-compatible fakes with a test `whsec`.
7. Doc note in `ubyhost-complete-stripe.md` §12: deprecation + immutability facts (§2 above).

## 5. Do not touch

- `payment_request.py` model logic (only call it), invoices, stay fees, retention, db.py SCHEMA (no migration needed this brief — `stripe_account` table exists).
- No secrets in repo/tests: tests use fake `whsec_`/`sk_test_` strings only. Never print config values.
- No host UI templates (0427+). No new tables.

## 6. Commands

From `App/`:
```
python -m pytest tests/test_stripe_connect.py tests/test_payment_request_model.py -q --tb=short -x 2>&1 | tail -30
```
Expected: all pass, 0 skipped. From root: `python3 scripts/context_lint.py 2>&1 | tail -30` → OK.

## 7. Acceptance

- [ ] `stripe` pinned+hashed; import works with no network.
- [ ] Feature fully inert when `UBYHOST_STRIPE_MODE=off` (routes 404 / no-op, no client init).
- [ ] ensure_account/onboarding_link/sync_account/handle_event per §4 with audit rows.
- [ ] Webhook: raw-body verification, 400 on bad signature, event-id dedupe, 2xx fast path.
- [ ] Prefill sends name/email/url only — no DOB, no address, no ID numbers.
- [ ] Tests green; lint OK; only §3 files changed.

## 8. Stop and ask

- If the repo's pip-compile setup can't regenerate the lock (missing tool) — hand-pin with hashes from pypi and show the command.
- If a public POST route without CSRF contradicts an existing repo rule — check how `guest.py` public routes work first.

## 9. Report

`docs/tasks/0426-report.md` per executor.md. Status `review`, one PR (new branch; #545 is merged).
