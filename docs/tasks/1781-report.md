# 1781 report

Status: review

## Files changed

- `go/internal/payments/webhook.go` — always runs `BookingWebhook`; removed Python forward and `bytes` import.
- `go/internal/payments/booking_webhook.go` — removed `BookingSwitchEnv` / `bookingSwitchOn`.
- `go/internal/payments/webhook_forward_test.go` — deleted.
- `go/internal/payments/webhook_test.go` — `fwdPost` / `fwdSigned` helpers for booking tests.
- `go/internal/payments/booking_webhook_test.go` — `TestBookingWebhookHandlesInGo` (no switch/forward cases).
- `deploy/lightsail/docker-compose.yml` — dropped `UBYHOST_PY_WEBHOOK_URL`.
- `docs/ENVIRONMENT.md` — removed forward row; `UBYHOST_GO_PATHS` documents Go-native booking webhook.
- `docs/plans/go-cutover-runbook.md`, `docs/plans/go-cutover-env-commands.md` — cutover text updated.
- `docs/tasks/1781-stripe-webhook-path-decision.md` — Tier B brief.
- `docs/tasks/1781-files/**` — sidecars + manifest.

## Commands

```text
gofmt -l internal/payments/*.go → empty
go vet ./internal/payments/... → silent
go test ./internal/payments/ -run 'Booking|Webhook' → ok (DB tests SKIP without UBYHOST_TEST_DATABASE_URL)
python3 scripts/context_lint.py → context lint: OK
```

Anchors: `forwardToPython` 0; `UBYHOST_PY_WEBHOOK_URL` in compose and ENVIRONMENT 0; `booking := NewBookingWebhook` 1.

## §7

- [x] No forward/switch env in Go or compose
- [x] Cutover docs describe Go-native handling
- [x] Only §3 paths in diff

## Deviations

None.

## Owner steps left

Add `/webhooks/stripe` to `UBYHOST_GO_PATHS`, deploy, `caddy reload`, Stripe test booking event.