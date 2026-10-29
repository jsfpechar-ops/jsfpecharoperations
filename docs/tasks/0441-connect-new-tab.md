# 0441: open Stripe onboarding in a new tab

Status: review
Depends on: 0440 (PR open) | Branch: task/0441-connect-new-tab

## 1. Objective

The "Open Stripe" form POST navigates the host's tab through the 303 to connect.stripe.com; with the service worker's navigation handling the page hangs on the skeleton loader. Opening the Stripe onboarding in a new tab fixes the hang and is the better pattern anyway (single-use link, host keeps the dashboard open).

## 2. Context

- Live-verified (29 Oct): the redirect chain works; left-click hangs on skeleton, right-click new tab works.
- `target="_blank" rel="noopener"` on the form; CSRF and session ride along (same-origin POST).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/payments.html` | edit | form target=_blank rel=noopener |

## 4. Steps

1. Add `target="_blank" rel="noopener"` to the connect form.

## 5. Do not touch

Service worker (navigate-mode fetch already passes cross-origin redirects through); routes.

## 6. Commands

- `pytest tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payments.py tests/test_payments_dashboard.py -q --tb=short` -> all passed, 0 skipped.

## 7. Acceptance

- [x] Form opens Stripe in a new tab; dashboard tab intact.

## 8. Stop and ask

None.

## 9. Report

In this brief (single template change).
