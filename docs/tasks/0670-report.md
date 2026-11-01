# 0670 report: Go Stripe webhook and Caddy route switch

Status: executor finished the code; not pushed, no PR (orchestrator asked for commit only). Brief status line left at `todo`.

## Files
- New: `go/internal/payments/webhook.go`, `go/internal/payments/webhook_test.go`
- Edited: `go/cmd/ubyhost-web/main.go` (one route line), `deploy/lightsail/caddy/Caddyfile.acme`, `deploy/lightsail/caddy/Caddyfile.cloudflare` (route switch, `@go path {$UBYHOST_GO_PATHS:/__go_off__}`), `deploy/lightsail/docker-compose.yml` (env only), `docs/ENVIRONMENT.md` (two rows)
- `App/` untouched. No new dependency.

## Commands
- `cd go && test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/payments/ -count=1 -v` : gofmt clean, vet clean. Tail:
  - `--- PASS: TestVerifySignature`, `--- PASS: TestOnboardingState`, `--- PASS: TestRequirementsJSON`
  - `--- SKIP: TestWebhookDatabase` and `--- SKIP: TestWebhookRateLimit` (`UBYHOST_TEST_DATABASE_URL is not set`). `ok ... internal/payments`
- `python3 scripts/context_lint.py | tail -3` : `context lint: OK`

## requirementsJSON literal
Run with `python3 -I`, copy of `_requirements_json` with `_REQUIREMENT_KEYS`, input `currently_due=["business_profile.url","external_account ü"]`, `eventually_due=["tos_acceptance.date"]`, `disabled_reason="requirements.pending_verification"`, `past_due=[]`:
`{"currently_due": ["business_profile.url", "external_account ü"], "eventually_due": ["tos_acceptance.date"], "disabled_reason": "requirements.pending_verification"}`

## Not done / not verified
- Database tests (`TestWebhookDatabase`, `TestWebhookRateLimit`) were written but not run here: no PostgreSQL. CI is the gate.
- `caddy validate` not run: caddy is not installed. Config was edited by hand; the new blocks use the same directive style as the existing file.
- Table columns: `stripe_webhook_event`, `stripe_account`, `payment_request` checked against migrations 0026/0027. `rate_limit_event (scope, key, at)` taken from the brief; `audit` columns taken from `sweep.go`.
- Compose not validated (no docker run).

## Decisions beyond brief section 2
- Body over 1 MiB answers 413 `payload too large` (Python has no limit).
- Stamps use `stampAt(now())`, the same format as `jobs.Now(0)`, so the injected clock controls them.
- Replay: unique violation on `event_id` returns 200 `ok` with nothing written.
- `payment_request` status other than draft/sent/awaiting_payment/paid: nothing written, 200 `ok`. Python would raise here.
- A row that does not change in the transition UPDATE returns an error, so the transaction rolls back and Stripe retries. Python would return False silently.
- `requirementsJSON` renders map values with sorted keys (Python keeps dict order); Stripe sends no map values under the four keys, so this does not change output.

## Owner steps left
None before CI. Setting `UBYHOST_GO_PATHS` (for example `/webhooks/stripe`) and the Go service env is a later owner step.
