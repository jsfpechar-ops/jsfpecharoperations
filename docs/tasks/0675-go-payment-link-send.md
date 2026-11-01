# 0675: Go card rail, create or reuse a Stripe Payment Link (payment_links.send)
Status: todo
Depends on: 0674 (#675, 2b4a919) | Base commit: origin/main | Branch: claude/project-thread-ach4z4
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
Port `App/app/payment_links.py` `send` (lines 26-95) to Go as-is, as a method on the existing `StripeOnboarder`. No route yet (0676 wires `POST /payments/requests/{id}/send`). Production stays unchanged: the Go container is off.
## 2. Context
Python source of truth (read only these): `App/app/payment_links.py` 26-95; `App/app/stripe_connect.py` 84-100 (`_api`) and 169-175 (`account_for_owner`). Go to build on: `go/internal/payments/onboarder.go` (`guard`, `call`, `mode`, `stampAt`), `webhook.go` (`audit`, `dbtx`), `onboarder_test.go` (DB + httptest setup to copy). Schema: grep `payment_request` and `stripe_account` in `App/app/migrations/`.

Behaviour, in Python's order. `func (s *StripeOnboarder) SendPaymentLink(ctx context.Context, requestID int64) (string, error)`:
1. `SELECT id, owner_user_id, rail, reason, amount_czk, COALESCE(stripe_payment_link_id, '') FROM payment_request WHERE id = $1`. No row: return `"", nil`.
2. `rail != "card"`: return an error `card rail only` (Python raises ValueError).
3. Account: `SELECT stripe_account_id, onboarding_state FROM stripe_account WHERE owner_user_id = $1 AND mode = $2` (mode = `s.mode()`). No row, or `onboarding_state != "complete"`: return `"", nil` (no guard, no count, no request).
4. `s.guard(ctx)` once (one count for the whole send, exactly like Python's single `_api()` call, even when two Stripe requests follow). Errors pass through (`ErrStripeOff`).
5. If the stored link id is non-empty: `GET {base}/v1/payment_links/<id>` with header `Stripe-Account: <acct>`. If the response `active` is true, return its `url` (no DB write). Otherwise continue.
6. `POST {base}/v1/payment_links` with `Stripe-Account: <acct>`, form-encoded (the stripe-python encoding of the Python params):
   `line_items[0][quantity]=1`, `line_items[0][price_data][currency]=czk`, `line_items[0][price_data][unit_amount]=<amount_czk*100>`, `line_items[0][price_data][product_data][name]=<name>`, `restrictions[completed_sessions][limit]=1`, `metadata[payment_request_id]=<id>`, `payment_intent_data[metadata][payment_request_id]=<id>`.
   `<name>` is `product_name`: `<Czech reason> (žádost č. <id>)`, Czech reasons from `App/app/host_i18n.py` 3149-3154: repair `Příspěvek na opravu`, extra_guest `Další host`, late_checkout `Pozdní odjezd`, cleaning `Úklid`, damage `Škoda`, custom `Vlastní`. An unknown reason uses the key itself, `payments.reason.<reason>` (host_i18n fallback; check `translate` in host_i18n.py for the exact fallback and follow it).
7. `UPDATE payment_request SET stripe_payment_link_id = $1, updated_at = $2 WHERE id = $3` (stamp from guard), then `audit(ctx, s.Pool, stamp, "payment_link_created", "id=<id> link=<link id>", owner)`. Return the response `url`. A response with no `id` or `url` is an error.

`call` has no extra-header parameter today: add the `Stripe-Account` header with the smallest change (for example a variadic or a new small helper used by both); existing callers and tests keep working unchanged.
## 3. Files
Create: `go/internal/payments/paylink.go`, `go/internal/payments/paylink_test.go`. Edit: `go/internal/payments/onboarder.go` (only the header support in `call`). Write `docs/tasks/0675-report.md`. Nothing else.
## 4. Steps
1. `paylink.go`: the method, a `reasonCS` map, comments naming the Python lines. `$n` placeholders, no new dependency.
2. Tests (DB tests skip without `UBYHOST_TEST_DATABASE_URL`, setup as `onboarder_test.go`; fake Stripe with `httptest` recording method, path, `Stripe-Account` header, form body). Cases: missing request gives `""`, nil, 0 requests; qr rail gives the error; no account row and `pending` account give `""`, nil, 0 requests, no usage row; mode off gives `ErrStripeOff`; fresh send posts the exact form above (compare parsed `url.Values`), sets the header, stores the link id, writes `payment_link_created`, returns the url, `lock_api_usage.calls` is 1; resend with an active stored link does one GET, no POST, returns its url, calls is 1 more; resend with an inactive stored link does GET then POST and stores the new id, still 1 count; Stripe 400 gives an error without the key in its text.
3. Commit: `0675: Go card rail payment link send`.
## 5. Do not touch
`App/` (read only), `connect.go`, `webhook.go`, `main.go`, `go.mod`/`go.sum`, CI, compose, Caddy, templates, JS, CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`; schema: see `onboarder_test.go` setup.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ -count=1 -v 2>&1 | grep -E "^(---|ok|FAIL|PASS)" | tail -40`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All payments tests pass with the database URL set, 0 skipped; build and vet clean; diff touches only section 3 files (plus this Status line set to `review`).
## 8. Stop and ask
Stop if the Python ranges no longer match section 2, or a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0675-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
