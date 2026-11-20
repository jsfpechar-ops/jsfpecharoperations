# 1429 report

Status: review

## Files

- `go/internal/web/invoices/send.go` — POST send handler (sidecar)
- `go/internal/web/invoices/send_test.go` — route + DB outbox test
- `go/internal/web/invoices/routes_test.go` — nine routes, send allowed
- `go/cmd/ubyhost-web/register_web_invoices_test.go` — send pattern registered (dormant: no `UBYHOST_GO_PATHS` cutover)
- `go/internal/web/invoices/handlers_test.go` — `UBYHOST_PUBLIC_BASE_URL` for send tests

## Commands

```
gofmt -l internal/web/invoices/ cmd/ubyhost-web/  → (empty)
go vet ./internal/web/invoices/... ./cmd/...  → ok
go test -count=1 ./internal/web/invoices/ -run TestSendRouteIsRegistered|TestRoutesAreListed  → ok
go test -count=1 ./cmd/ubyhost-web/ -run TestInvoiceRoutesRegistered  → ok
python3 scripts/context_lint.py  → OK
```

`UBYHOST_TEST_DATABASE_URL` was not set in this agent; `TestSendInvoiceQueuesMail` not run here (CI postgres shard).

## §7

- [x] Send POST queues `invoice_issued` with suffix `0`; second send uses `1` (test code present).
- [x] Payload uses marker; `claim_secret_enc` set (test code present).
- [x] Route tests list send; register_web test passes.

## Deviations

- Started from `origin/cursor/1428-go-mail-invoice-issued-dff7` while PR **#1179** was still open (CI red: `test_invoice_issued_golden_is_fresh`). Rebase onto `main` after **#1179** merges.
- Added `handlers_test.go` env line (not named in brief §3) for public base URL in send content.

## Questions

None.

## Owner

Merge **#1179** first, then this PR. Cut over `/invoices/<id>/send` with the detail page when ready.