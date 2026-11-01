# 0674: Go Stripe Connect Onboarder (Stripe calls, call budget) and route wiring
Status: review
Depends on: 0673 (#674, 9af7ee6) | Base commit: origin/main | Branch: claude/project-thread-em2htb
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
Implement the `Onboarder` interface of `go/internal/payments/connect.go` by porting `App/app/stripe_connect.py` as-is, and register the three Connect routes in `go/cmd/ubyhost-web/main.go`. Production stays unchanged: the Go container is off and Caddy sends `/payments/connect/*` to Go only when listed in `UBYHOST_GO_PATHS` (default `/__go_off__`).
## 2. Context
Python source of truth (read only these): `App/app/stripe_connect.py` 38-100 (`enabled`, budget, `_api`), 105-219 (`_identity_params`, `_merchant_config`, `_responsibilities`, `account_for_owner`, `create_or_get_account`), 299-326 (`onboarding_link`, `handle_return`). Go to build on: `go/internal/payments/connect.go` 30-60 (sentinels, `Onboarder`), `webhook.go` (`mirrorAccount`, `audit`, `stampAt`, `dbtx`), `connect_test.go` / `webhook_test.go` (DB test setup). Schema: grep `stripe_account` and `legal_entity` in `App/app/migrations/`.

Behaviour, in Python's order:
1. **Guard (`_api`)** before every Stripe call: mode = `UBYHOST_STRIPE_MODE` trimmed, lower-cased; off unless `test`/`live` and `UBYHOST_STRIPE_SECRET_KEY` (trimmed) non-empty, giving `ErrStripeOff`. Budget: limit = `UBYHOST_STRIPE_MONTHLY_API_CALLS` (default 50000; unparsable = 50000); if limit > 0 and `SELECT calls FROM lock_api_usage WHERE month = $1 AND provider = 'stripe'` (month = first 7 chars of the stamp, `YYYY-MM`) is >= limit, `ErrStripeOff`. Then count first, before the HTTP call: `INSERT INTO lock_api_usage (month, provider, calls) VALUES ($1, 'stripe', 1) ON CONFLICT(month, provider) DO UPDATE SET calls = lock_api_usage.calls + 1`.
2. **Account (`create_or_get_account`)**: row `SELECT stripe_account_id FROM stripe_account WHERE owner_user_id = $1 AND mode = $2`; if present, use it (no Stripe call). Else `legal_entity` for the owner; none gives `ErrNoEntity` (no call, no count). Else guard, then `POST {base}/v2/core/accounts` with a JSON body: `{"contact_email": <contact_email, or null when empty/NULL>, "display_name": name, "dashboard": "full", "identity": {"country": "CZ", "entity_type": "company" if business_type == "company" else "individual", "business_details": {"registered_name": name}}, "configuration": {"merchant": {"capabilities": {"card_payments": {"requested": true}}}}, "defaults": {"currency": "czk", "responsibilities": {"fees_collector": "stripe", "losses_collector": "stripe"}}}`. Then insert `stripe_account` (owner_user_id, stripe_account_id = response `id`, mode, onboarding_state `pending`, charges_enabled 0, payouts_enabled 0, created_at = updated_at = stamp), `audit(..., "stripe_account_created", "acct=<id>", owner)`, then `mirrorAccount(ctx, pool, <decoded response map>, mode, stamp)`.
3. **`OnboardingLink(ctx, owner, base)`**: account as in 2, then guard, then `POST {base}/v1/account_links` form-encoded: `account=<id>`, `refresh_url=<base>/payments/connect/start`, `return_url=<base>/payments/connect/return`, `type=account_onboarding`; return the response `url`.
4. **`HandleReturn(ctx, owner)`**: no `stripe_account` row gives `ErrNoAccount` (no count). Else guard, `GET {base}/v1/accounts/<id>`, then `mirrorAccount` with the decoded map.
5. **HTTP**: `Authorization: Bearer <secret key>`, `Stripe-Version: 2026-09-30.endive` (the version stripe-python 16.0.1 sends; one const), `Content-Type: application/json` for v2 and `application/x-www-form-urlencoded` for v1; a 30 s client timeout. Non-2xx gives an error naming the status and Stripe's `error.message` / `error.code` only, never the body or key. API base `https://api.stripe.com` is a struct field so tests use `httptest`.

Known differences, write them in the type comment: no network retries (stripe-python's StripeClient retries twice with idempotency keys; a failed click is simply retried by the host).
## 3. Files
Create: `go/internal/payments/onboarder.go`, `go/internal/payments/onboarder_test.go`. Edit: `go/cmd/ubyhost-web/main.go` (routes only). Write `docs/tasks/0674-report.md`. Nothing else.
## 4. Steps
1. `onboarder.go`: `type StripeOnboarder struct { Pool *pgxpool.Pool; Getenv func(string) string; Now func() time.Time; Client *http.Client; APIBase string }` and `func NewStripeOnboarder(pool, getenv, now) *StripeOnboarder` (default client and base). Methods implement `Onboarder`; read env at call time. Comments name the Python lines. No new dependency; reuse `mirrorAccount`, `audit`, `stampAt`; `$n` placeholders.
2. `main.go`: next to the webhook line, build one onboarder and register `mux.Handle("GET /payments/connect/start", ...)`, `"POST /payments/connect/start"` (same handler) and `"GET /payments/connect/return"`, each wrapped with `m.wrap(<path>, ...)` and `payments.ConnectStartHandler(pool, os.Getenv, time.Now, ob)` / `ConnectReturnHandler`.
3. Tests (DB tests skip without `UBYHOST_TEST_DATABASE_URL`, schema as `connect_test.go`): fake Stripe with `httptest.NewServer` recording method, path, headers, body. Cases: mode off and empty key give `ErrStripeOff` with 0 requests; no entity gives `ErrNoEntity`, 0 requests, no usage row; first link creates the account (v2 JSON body equals section 2 exactly, incl. `"contact_email":null` when empty and `company` entity type), inserts the row, writes `stripe_account_created`, posts the link form and returns the url, and `lock_api_usage.calls` is 2; second link reuses the row (1 more call); budget at limit gives `ErrStripeOff` and no request; `HandleReturn` without a row gives `ErrNoAccount`; with a row and a fake account `{"id":..,"charges_enabled":true,"payouts_enabled":true,"requirements":{}}` it mirrors `complete` and writes `stripe_account_state`; Stripe 400 returns an error without the key in its text.
4. Commit: `0674: Go Stripe Connect onboarder and route wiring`.
## 5. Do not touch
`App/` (read only), `connect.go`, `webhook.go`, `go.mod`/`go.sum`, CI, compose, Caddy, templates, JS, CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ ./cmd/... -count=1 -v 2>&1 | grep -E "^(---|ok|FAIL|PASS)" | tail -40`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All payments tests pass with the database URL set, 0 skipped; build and vet clean; diff touches only section 3 files (plus this Status line).
## 8. Stop and ask
Stop if the Python ranges no longer match section 2, if a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0674-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
