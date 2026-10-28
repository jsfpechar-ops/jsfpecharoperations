# 0428: Stripe Connect module — connected accounts, onboarding, webhook (P1.2)

Status: todo
Depends on: 0425 | Base commit: 79dc27e | Branch: task/0428-stripe-connect
Executor: implemented directly by the orchestrator (owner: "you implement it", chat 27 Oct 2026) | Fits one session

Renumbered from the plan's "brief 0426": 0425–0427 are taken by the observability
workstream (0425-monitoring-pipeline, 0426-per-user-attribution, 0427-observability-runbook).

## 1. Objective

Add the `stripe` Python SDK (pinned+hashed, owner decision below) and `App/app/stripe_connect.py`: per-host Connect account creation using the current controller API, one-time Account Links onboarding shown only inside the authenticated dashboard, and a FastAPI webhook endpoint (raw-body signature verification, dedupe by event id, fast 2xx) that mirrors `account.updated` into `stripe_account`. ubyhost never receives or holds funds; hosts are merchant of record with application fee 0; ubyhost never stores Stripe secrets or documents. No UI templates in this brief — the request UX is P1.5.

## 2. Context

- Owner decision (27 Oct 2026): `stripe` official Python SDK is the only new package; pinned+hashed through `requirements.lock`. Direct payments fold into the FastAPI app; payment links are the primary money path (plan [direct-payments-build-plan](../plans/direct-payments-build-plan.md) §2, decision line 67 in [decisions](../context/decisions.md)).
- Stripe's current Account API uses **controller parameters**, not the deprecated `type=express` (verified against Stripe's Account docs): `controller[fees][payer]=account`, `controller[losses][payments]=stripe`, `controller[stripe_dashboard][type]=express`, `controller[requirement_collection]=stripe`. The platform is never fees or losses payer; Stripe is the losses collector (Managed Risk, plan [ubyhost-complete-stripe](../plans/ubyhost-complete-stripe.md) §12 "Confirmed").
- Connect webhook truth: events for direct charges on connected accounts (e.g. `checkout.session.completed`) arrive **only** at an endpoint registered as a connected-accounts destination. `account.updated` is the event for requirement changes. Classic webhook endpoints verify with the `whsec_` signing secret over the raw request body.
- Env contract (already documented, [ENVIRONMENT](../ENVIRONMENT.md) "Connect payments"): `UBYHOST_STRIPE_MODE` off/test/live, `UBYHOST_STRIPE_SECRET_KEY`, `UBYHOST_STRIPE_WEBHOOK_SECRET` (unset = logged-and-ignored; in test/live mode an unset value fails loudly), `UBYHOST_STRIPE_MONTHLY_API_CALLS` cap. `off` hides all payment endpoints.
- Tables from migration 0026 (already merged, do not rebuild):

```sql
CREATE TABLE IF NOT EXISTS stripe_account (
    owner_user_id         INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    stripe_account_id     TEXT NOT NULL UNIQUE,
    mode                  TEXT NOT NULL CHECK (mode IN ('test', 'live')),
    onboarding_state      TEXT NOT NULL DEFAULT 'pending'
                          CHECK (onboarding_state IN ('pending', 'action_required', 'complete', 'rejected', 'disabled')),
    charges_enabled       INTEGER NOT NULL DEFAULT 0,
    payouts_enabled       INTEGER NOT NULL DEFAULT 0,
    requirements_json     TEXT,
    ...
    UNIQUE (owner_user_id, mode)
);
```

- Shared API-call cap table (reuse, do not rebuild): `lock_api_usage (month, provider, calls)` — TTLock counts with provider `'ttlock'`; Stripe counts with provider `'stripe'` (see `App/app/ttlock.py` `calls_this_month`/`_count_call`).
- Route conventions: host router = `APIRouter(dependencies=[Depends(security.protect_host_post)])`, `auth.require_login(request)` guard, `access.owner_id(request)`; public POST outside the host CSRF dependency (see `routes/mail_unsubscribe.py` docstring); public POSTs are rate-limited (`rate_limit.client_key(request, scope)`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/requirements.txt` | edit | add `stripe==16.0.1` |
| `App/requirements.lock` | edit | regenerate (pip-compile --generate-hashes); only `stripe` is new |
| `App/app/config.py` | edit | `STRIPE_MODE`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_MONTHLY_API_CALLS` |
| `App/app/stripe_connect.py` | create | provisioning module per §4 |
| `App/app/migrations/0027_stripe_webhook_events.sql` | create | webhook event dedupe table |
| `App/app/routes/stripe_connect.py` | create | onboarding start/return + public `POST /webhooks/stripe` |
| `App/app/main.py` | edit | include the router (after `mail_unsubscribe`, public row) |
| `App/tests/test_stripe_connect.py` | create | tests per §6, mocked Stripe client, no network |
| `docs/context/decisions.md` | edit | `[deps] stripe` decision line |
| `docs/context/test-map.md` | edit | payments row (model + connect tests) |
| `docs/context/status.md` | edit | Now line |
| `docs/plans/ubyhost-complete-stripe.md` | edit | §12 note: controller params, dashboard type immutable |
| `docs/tasks/0428-stripe-connect.md` | create | this brief |
| `docs/tasks/0428-report.md` | create | report per §9 |

No other file may change. `db.py` SCHEMA is not touched (numbered migrations only). No template, CSS or guest-page file is touched (rule 7 does not apply).

## 4. Steps

1. **requirements**: `stripe==16.0.1` in `requirements.txt`; regenerate `requirements.lock` with the documented command (`pip-compile --allow-unsafe --generate-hashes --output-file=requirements.lock requirements.txt`). Verify the diff adds only `stripe` (+ `# via -r requirements.txt`).
2. **config.py**: four accessors next to the TTLOCK block, same env pattern, names/defaults exactly as ENVIRONMENT.md documents.
3. **migration 0027**: `stripe_webhook_event (id, event_id TEXT UNIQUE, event_type TEXT, mode CHECK test/live, created_at)`. Header comment: dedupe for at-least-once delivery; Stripe identifiers are not personal data, so no retention.py line; rows are tiny and pruned with old audit rows in a later sweep brief.
4. **`app/stripe_connect.py`**:
   - `enabled()` — mode in (test, live) and secret key set.
   - Call budget mirroring ttlock: `calls_this_month()`, `_count_call()`, `_budget_allows()` against `config.STRIPE_MONTHLY_API_CALLS` (provider `'stripe'`).
   - `create_or_get_account(owner_user_id)` — legal_entity → Stripe `Account.create` with controller params (`fees.payer=account`, `losses.payments=stripe`, `requirement_collection=stripe`, `stripe_dashboard.type=express`), `country="CZ"`, `business_profile` (`name` from legal_entity, `url`, accommodation `product_description`); insert the `stripe_account` mirror (state only, never secrets/documents); idempotent per `(owner, mode)`.
   - `onboarding_link(owner_user_id, base_url)` — `AccountLink.create(type="account_onboarding", refresh_url=<base>/payments/connect/start, return_url=<base>/payments/connect/return)`; Stripe makes links single-use; the refresh URL regenerates by calling this again.
   - `handle_return(owner_user_id)` — re-retrieve the account, mirror it, return the state (return ≠ verified).
   - `_onboarding_state(account)` — complete / action_required / rejected / disabled / pending from `charges_enabled`, `payouts_enabled`, `requirements` (currently_due, past_due, disabled_reason, error codes); `mirror_account` upserts state + `requirements_json` (field names only) and audits.
   - Webhook: `verify_event(raw, sig_header)` via the SDK's signature verification; `process_event(event)` — dedupe INSERT on event id (IntegrityError = already seen → skip), dispatch `account.updated` to `mirror_account` by `stripe_account_id`+mode, everything else is recorded and acknowledged (handlers arrive with 0429+ card/QR rails).
5. **`routes/stripe_connect.py`**:
   - `POST /payments/connect/start` (host, CSRF) and `GET` of the same path (refresh target) — require login, 404 when mode off, generate the link, 303 to Stripe. The link is shown/redirected only here, never emailed.
   - `GET /payments/connect/return` — require login, 404 when off, `handle_return`, flash a plain-Czech state message, redirect to the dashboard.
   - `POST /webhooks/stripe` — public (no host CSRF), rate-limited, raw body + `Stripe-Signature`; mode off or secret unset → log and 200; mode on + secret unset → 500 loudly; bad signature → 400; valid → process, always 2xx fast.
6. **main.py**: `app.include_router(stripe_connect_routes.router)` after `mail_unsubscribe.router` (public row, outside the host CSRF dependency).

## 5. Do not touch

`App/app/db.py` SCHEMA, `App/app/payments.py`, `App/app/payment_request.py`, templates/CSS/guest pages, `.env` or any secret, deploy scripts. Hard rules that apply: 3 (no secrets in the repo — the owner's `sk_test` key is env-only), 4 (dependency decision line lands in decisions.md in the same PR), 5 (SQL only via db.py helpers, new migration file), 8 (never push to `main`).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stripe_connect.py tests/test_payment_request_model.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30` → all pass, 0 skipped.
From the repo root: `python3 scripts/context_lint.py` → OK.

## 7. Acceptance

- [ ] `requirements.lock` diff adds only `stripe==16.0.1` with hashes; `pip-compile` header unchanged.
- [ ] Account create params carry exactly the four controller settings + CZ + accommodation business_profile; no deprecated `type=` top-level param.
- [ ] `stripe_account` rows never contain keys, documents or bank details; `requirements_json` holds requirement field names only.
- [ ] Onboarding link only reachable signed-in (anonymous → login redirect); no mail is queued carrying it.
- [ ] Webhook: valid signature + new event id → processed once; replayed id → 2xx, no second handler run; bad signature → 400; secret unset in test/live → 500; mode off → 200 logged.
- [ ] `account.updated` mirrors state transitions with an audit row per transition.
- [ ] Monthly cap counts every Stripe call in `lock_api_usage` and blocks when exceeded.
- [ ] Scoped tests green, 0 skipped; context_lint OK; nothing outside §3 changed (`git diff --stat`).

## 8. Stop and ask

Stop, and write the report, if: the SDK's controller params are rejected by the pinned version; a test fails twice; a file outside §3 needs a change; §5 would be touched; push/merge/secrets are needed (hand exact commands to the owner).

## 9. Report

Write `docs/tasks/0428-report.md` (≤1,500 tokens per lint cap) and set `Status: review`: files changed (`git diff --stat`), each command's last lines, §7 ticked, deviations, questions, owner steps left (register the platform in Dashboard → Connect settings (Express); create the test webhook endpoint pointing at `/webhooks/stripe` as a connected-accounts destination with `account.updated` (+ later `checkout.session.completed`, `charge.dispute.created`); set the env vars; send the MCC Q1–Q7 set to Stripe Support).

## Risk list (for the reviewer)

`App/app/stripe_connect.py`, `App/app/routes/stripe_connect.py`, `App/app/migrations/0027_stripe_webhook_events.sql`, `App/tests/test_stripe_connect.py`, the `main.py` router include.

## Owner steps

1. In the Stripe Dashboard (test mode): Settings → Connect → activate Express; register the platform (business description: short-term accommodation marketplace, hosts are merchants of record).
2. When this branch is deployed to staging: Developers → Webhooks → Add endpoint `https://<staging>/webhooks/stripe`, select "All connected accounts" (needed for direct-charge events), events: `account.updated` (add `checkout.session.completed`, `charge.dispute.created` when 0429 lands); copy the `whsec_` secret.
3. Set env: `UBYHOST_STRIPE_MODE=test`, `UBYHOST_STRIPE_SECRET_KEY=<sk_test from the owner's chat — re-supply it directly, never commit it>`, `UBYHOST_STRIPE_WEBHOOK_SECRET=<whsec>`.
4. Send the MCC Q1–Q7 question set (plan §12 "Still open"/message) to Stripe Support, asking for written routing to a Connect onboarding/risk specialist.
