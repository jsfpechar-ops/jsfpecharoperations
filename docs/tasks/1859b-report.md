# 1859b report: Go hide Payments

## Summary

Go web `metrics.wrap` checks `appconfig.PaymentsHostPathBlocked` on every request so `/payments*` (except QR PNG), `/booking-sites`, and `/apartments/*/booking-site*` return 404 while `UBYHOST_PAYMENTS_HIDDEN=1`. Webhooks, guest booking, pay links, and `/payments/qr/{id}.png` are not gated.

## Tests

```text
go/cmd/ubyhost-web: TestPaymentsHiddenRoutesBlocked, TestPaymentsHiddenOffDoesNotGate
go/internal/appconfig: PaymentsHidden + path matrix
go/internal/hostweb: WantsHTML, BlockedPage
```

## Owner

After merge: `UBYHOST_PAYMENTS_HIDDEN=1` only — no GO_PATHS surgery.