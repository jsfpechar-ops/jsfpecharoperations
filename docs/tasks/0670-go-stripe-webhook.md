# 0670: Go API A1: Stripe webhook in Go, plus the Caddy route switch (off by default)
Status: review
Depends on: 0551 (#646) | Base commit: main | Branch: claude/project-thread-g70pki
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
First slice of the API port (task block 0670-0699; police is 0550-0559, jobs have their own block). Two things, both inert in production until the owner sets env vars:
1. A Caddy route switch: paths listed in `UBYHOST_GO_PATHS` go to the Go service; empty (the default) means nothing changes.
2. `POST /webhooks/stripe` in Go, byte-for-byte the same database effect as Python `App/app/routes/stripe_connect.py` `stripe_webhook` (line 101-129).
Python keeps serving the route until the owner adds `/webhooks/stripe` to `UBYHOST_GO_PATHS`. No Python change.
## 2. Context
- Python source of truth: route `App/app/routes/stripe_connect.py` 101-129; `App/app/stripe_connect.py` `verify_event` 326, `_record_event` 348, `process_event` 381, `mirror_by_account_id` 275, `_mirror` 243, `_onboarding_state` 218, `_requirements_json` 235 (and the `_REQUIREMENT_KEYS`, `_REJECT_CODES` constants at the top of the file); `App/app/payment_links.py` `on_paid` 64; `App/app/payment_request.py` `set_status` 105, `mark_paid` 129, `_TRANSITIONS` 22; `App/app/rate_limit.py` `blocked` 52, `record` 45, `client_key` 114; `App/app/config.py` 343-345.
- Go already has: package `go/internal/payments` (`sweep.go`: `insertAuditSQL`, the test helpers `testPool`, `applyMigrations`, `auditDetails` in `sweep_test.go`, reuse them); `jobs.Now(0)` gives the Python `db.utcnow()` stamp; `cmd/ubyhost-web/main.go` builds the mux (`m.wrap`).
- Caddy: `deploy/lightsail/caddy/Caddyfile.cloudflare` and `Caddyfile.acme` each end in one `reverse_proxy ubyhost:8080 { header_up CF-Connecting-IP ... }`. Compose service `caddy` passes env in its `environment:` list; `ubyhost-go` likewise.
- **Traps:**
  - Signature (Stripe SDK `construct_event`, default tolerance 300 s): header `t=<unix>,v1=<hex>[,v1=...]`; expected = hex HMAC-SHA256(secret, `"<t>." + raw body`); accept if any `v1` matches (constant-time compare) and `|now - t| <= 300`. Missing `t` or no `v1`, or a mismatch, or too old: 400 `bad signature`. Never log the secret or the header value.
  - Order exactly as Python: rate limit first (scope `stripe_webhook`, 600 per 3600 s, 429 `slow down`, then record a row), then mode: mode not `test`/`live` gives 200 `ignored`; mode on with empty secret gives 500 `webhook secret not configured`; then verify; then process; 200 `ok`. Bodies are `text/plain`.
  - Rate limit rows: table `rate_limit_event (scope, key, at)`, `at` = Unix seconds as float. Prune rows older than the window for that scope+key before counting, like `_count`. Key = the `CF-Connecting-IP` header (Caddy sets it), else the host part of `RemoteAddr`, else `unknown`.
  - Dedupe: insert into `stripe_webhook_event (event_id, event_type, mode, created_at)`; unique violation (`23505`) means already seen: 200 `ok`, nothing else. Do the insert and all effects in **one transaction** (an error rolls back, answer 500, Stripe retries).
  - `account.updated`: find `owner_user_id` by `stripe_account_id` and mode; update only when the row exists and `onboarding_state != new state` (same WHERE as Python); audit `stripe_account_state` with the exact detail string only when a row changed. `requirements_json` must equal Python `json.dumps(subset)`: key order of `_REQUIREMENT_KEYS`, separators `", "` and `": "`, `ensure_ascii=True`; NULL when empty.
  - `payment_link.paid` and `checkout.session.completed`: link id = `object.payment_link` or else `object.id`; skip when no row or status `paid`; from `draft` walk to `sent` first (audit `payment_request_status` `id=N draft->sent`), then to `paid` with `paid_at` set (audit `id=N sent->paid` or `awaiting_payment->paid`), then audit `payment_request_paid` `id=N via=stripe_webhook amount=<amount_czk> CZK`. Any other status: do nothing (Python raises; Go must not write a half state). Audit actor `host`, owner from the row.
  - Other event types: recorded, nothing else.
## 3. Files
New: `go/internal/payments/webhook.go`, `go/internal/payments/webhook_test.go`. Edit: `go/cmd/ubyhost-web/main.go` (register the route), `deploy/lightsail/caddy/Caddyfile.cloudflare`, `deploy/lightsail/caddy/Caddyfile.acme`, `deploy/lightsail/docker-compose.yml` (env only), the "Connect payments" section of `docs/ENVIRONMENT.md` (two lines: `UBYHOST_GO_PATHS`, and that the Go service needs the same two Stripe vars). Write `docs/tasks/0670-report.md`.
## 4. Steps
1. Caddy, both files: replace the single `reverse_proxy ubyhost:8080 {...}` with
   ```
   @go path {$UBYHOST_GO_PATHS:/__go_off__}
   handle @go {
   	reverse_proxy ubyhost-go:8081 {
   		header_up CF-Connecting-IP <same value as today in that file>
   	}
   }
   handle {
   	<the existing reverse_proxy block, unchanged>
   }
   ```
   with a two-line comment (paths are space-separated; empty = all traffic to Python). If `caddy` is installed, run `caddy validate` on both with and without the env set; else say so in the report.
2. Compose: add `UBYHOST_GO_PATHS: ${UBYHOST_GO_PATHS:-}` to `caddy.environment`; add `UBYHOST_STRIPE_MODE: ${UBYHOST_STRIPE_MODE:-off}` and `UBYHOST_STRIPE_WEBHOOK_SECRET: ${UBYHOST_STRIPE_WEBHOOK_SECRET:-}` to `ubyhost-go.environment`. Nothing else.
3. `webhook.go`: top comment naming the Python lines. `func WebhookHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc`; read mode (trim, lowercase) and secret (trim) at construction; body limit 1 MiB. Unexported helpers `verifySignature(raw []byte, header, secret string, now time.Time) error`, `onboardingState`, `requirementsJSON`.
4. `main.go`: `mux.Handle("POST /webhooks/stripe", m.wrap("/webhooks/stripe", payments.WebhookHandler(pool, os.Getenv, time.Now)))`.
5. `webhook_test.go`: signature unit tests without a database (valid; two v1 one matching; wrong secret; old timestamp 301 s; missing t). `onboardingState` table test for all five states, `requirementsJSON` bytes vs a literal copied from running Python once (put the Python one-liner you used in the report). Database tests (skip without `UBYHOST_TEST_DATABASE_URL`, via `httptest`): mode off gives 200 `ignored` and no event row; on without secret 500; bad signature 400; account.updated mirrors + one audit, replay gives one event row and no second audit; same state twice gives no audit; payment link paid from draft gives two status audits + paid audit + `paid_at`; already paid untouched; unknown type recorded only; 601st request in the window gives 429.
6. Commit: `0670: Go Stripe webhook matching Python, Caddy route switch off by default`.
## 5. Do not touch
`App/` (all), `go/internal/` outside `payments/`, `go.mod`/`go.sum` (stdlib only), CI, templates/CSS/JS, other compose services.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/payments/ -count=1 2>&1 | tail -30`. Database tests skip locally unless a local PostgreSQL is set; CI is their gate, say so.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
- With `UBYHOST_GO_PATHS` unset every request still reaches `ubyhost:8080` (show the validated config or the diff).
- Go answers the same status and body as Python for each case in step 5 and writes the same rows.
- No new dependency; nothing in `App/` changed.
## 8. Stop and ask
Stop if `stripe_webhook_event`, `stripe_account`, `payment_request` or `rate_limit_event` lacks a column named here, if Caddy rejects the `{$VAR:default}` matcher, or if matching Python would need a new dependency.
## 9. Report
`docs/tasks/0670-report.md`: command tails, diff stat, the Python one-liner for the `requirementsJSON` literal, anything you decided beyond section 2.
