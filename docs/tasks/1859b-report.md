# 1859b report: Go hide Payments

## Summary

Go web `metrics.wrap` checks `appconfig.PaymentsHostPathBlocked` on every request so `/payments*` (including `/payments/qr/*.png`), `/booking-sites`, and `/apartments/*/booking-site*` return 404 while `UBYHOST_PAYMENTS_HIDDEN=1`. Webhooks, guest booking `/p/*`, and guest `/pay/{id}/*` are not gated. Go `hostweb/layout` sidebar, v2 nav, More sheet, and `/menu` omit payments links when hidden (parity with Python #1106).

## Tests

```text
go/cmd/ubyhost-web: TestPaymentsHiddenRoutesBlocked, TestPaymentsHiddenOffDoesNotGate
go/internal/appconfig: PaymentsHidden + path matrix
go/internal/hostweb: WantsHTML, BlockedPage
App: test_payments_hidden.py
```

## Owner

After merge: `UBYHOST_PAYMENTS_HIDDEN=1` only — no GO_PATHS surgery. Production Go nav/404 need `UBYHOST_PAYMENTS_HIDDEN: ${UBYHOST_PAYMENTS_HIDDEN:-}` on the `ubyhost-go` service in Lightsail compose (allowlist); without it Go never sees the flag.