# 0428 report

Status: review
Branch: task/0428-stripe-connect (new PR; #545 was merged, so this brief ships on its own branch).

## Files changed

- `App/requirements.txt` + `App/requirements.lock`: `stripe==16.0.1` pinned; lock entry added with both hashes (+4 lines, only stripe).
- `App/app/config.py`: four `STRIPE_*` accessors (env contract from ENVIRONMENT.md).
- `App/app/stripe_connect.py`: connected-account creation via the current controller API, state mirror, Account Links onboarding, webhook verify/dedupe/dispatch, monthly call cap on `lock_api_usage`.
- `App/app/migrations/0027_stripe_webhook_events.sql`: `stripe_webhook_event` dedupe table (event ids are Stripe identifiers, not personal data — no retention line).
- `App/app/routes/stripe_connect.py`: `/payments/connect/start` (GET refresh + POST), `/payments/connect/return`, public `POST /webhooks/stripe`.
- `App/app/main.py`: router include (public row, outside the host CSRF dependency).
- `App/tests/test_stripe_connect.py`: 23 tests, mocked Stripe client, real SDK only for the local HMAC webhook signature check.
- Docs: [deps] decision line, test-map payments row, status Now line, plan §12 controller note, brief 0428.

## Commands (last lines)

- `pytest tests/test_stripe_connect.py tests/test_payment_request_model.py tests/test_migrations.py` → `49 passed in 1.18s`, 0 skipped.
- `pytest tests/test_db_update_if.py tests/test_db_upgrade.py tests/test_env_guard.py` → `35 passed` (config + main.py smoke).
- `pytest tests/test_settings_technical.py tests/test_retention.py` → `18 passed` (route/retention smoke).
- `ruff check <changed files> --select E9,F63,F7,F82,F401,F841` → `All checks passed!` (CI's ruff selection).
- `python3 scripts/context_lint.py` → `context lint: OK` (one pre-existing WARN about RETENTION.md named by two open briefs).

## Section 7

- [x] Lock diff adds only stripe with hashes; pip-compile header unchanged.
- [x] Account create params: four controller settings + CZ + accommodation business_profile; no deprecated `type=`.
- [x] Mirror rows hold state only; `requirements_json` stores field names only (tested).
- [x] Link reachable only signed-in (anonymous → login redirect); no outbox row carries it (tested).
- [x] Webhook: valid sig + new id → processed once; replay → 2xx, no second run (tested); bad sig → 400; secret unset in test mode → 500; mode off → 200 logged (all tested).
- [x] `account.updated` mirrors state transitions with an audit row each (tested).
- [x] Monthly cap counts calls and blocks at the limit (tested).
- [x] Scoped tests green 0 skipped; lint OK; nothing outside §3 changed.

## Deviations

- Brief renumbered 0426 → 0428: 0425–0427 were taken by the observability workstream (same pattern as 0421→0425 before).
- pip-compile would also bump fastapi/starlette/cryptography/boto3, whose locked versions lag requirements.txt (pre-existing gap; CI installs from the lock). Kept the diff minimal: only the stripe entry was added; recommend a separate dependency-sync brief.
- No subagent configs existed in this session, so the orchestrator implemented directly (owner's standing "you implement it").
- Local `git push` was blocked by the machine's enterprise gh credential helper; the branch was pushed through the authorized GitHub App connector instead (remote commit verified byte-identical on a spot check).
- Return route redirects to the dashboard without copy; the "return ≠ verified" popover copy lands with the P1.5 payments dashboard.

## Questions

- Should the lock's four stale pins (fastapi 0.142.2 vs requirements.txt 0.159.1 etc.) get their own sync brief, or ride along with a later dependency change?

## Owner steps left

1. Stripe Dashboard (test mode): Connect settings → Express; register the platform (short-term accommodation marketplace, hosts are merchants of record).
2. When staged: Webhooks → add endpoint `https://<staging>/webhooks/stripe`, choose **all connected accounts** (direct-charge events like `checkout.session.completed` need a connected-accounts destination), subscribe `account.updated`; copy the `whsec_` secret.
3. Set env on staging: `UBYHOST_STRIPE_MODE=test`, `UBYHOST_STRIPE_SECRET_KEY=<sk_test — re-supply in chat or Lightsail console, never in git>`, `UBYHOST_STRIPE_WEBHOOK_SECRET=<whsec>`.
4. Send the MCC Q1–Q7 set (plan §12 message) to Stripe Support, asking for written routing to a Connect onboarding/risk specialist.
5. Merge the PR when green (`scripts/merge-pr-on-green.sh`).
