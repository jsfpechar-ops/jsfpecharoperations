# 1859b: Hide host Payments routes (Go half)

Status: done
Depends on: 1859 Python half (#1095)
Branch: `cursor/1859-hide-payments-go-8615`
Executor: Cloud agent | Tier: B

## Objective

When `UBYHOST_PAYMENTS_HIDDEN=1`, every Go handler under blocked host paths returns **404** (branded HTML when `Accept` includes `text/html`, else empty body). **`POST /webhooks/stripe`**, guest **`/p/*`**, **`/pay/{id}/*`**, and **`/payments/qr/*.png`** stay reachable.

## Files

| Path | Action |
|---|---|
| `go/internal/appconfig/payments_hidden.go` | `PaymentsHidden`, `PaymentsHostPathBlocked` (mirror Python) |
| `go/internal/hostweb/notfound.go` | `WantsHTML`, `BlockedPage` |
| `go/cmd/ubyhost-web/main.go` | Gate in `metrics.wrap` before handlers |
| `go/internal/web/stays/tpl.go` | Use `appconfig.PaymentsHidden` |
| `go/cmd/ubyhost-web/payments_hidden_test.go` | Hidden on/off smoke |
| `go/internal/appconfig/payments_hidden_test.go` | Path matrix |
| `go/internal/hostweb/notfound_test.go` | 404 shape |

## Commands

```bash
cd go/cmd/ubyhost-web && go test -run PaymentsHidden -count=1 2>&1 | tail -15
cd go/internal/appconfig && go test -count=1 2>&1 | tail -10
cd go/internal/hostweb && go test -run 'BlockedPage|WantsHTML' -count=1 2>&1 | tail -10
```

## Owner steps

1. Merge PR; set `UBYHOST_PAYMENTS_HIDDEN=1` in production `.env` (Python half already expects it).
2. Reload stack; confirm Go-served `GET /payments` is 404 and `POST /webhooks/stripe` still works.
3. No `UBYHOST_GO_PATHS` change required.