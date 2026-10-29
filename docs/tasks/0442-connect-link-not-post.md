# 0442: "Open Stripe" is a plain link, not a form POST

Status: review
Depends on: 0440, 0441 (merged) | Branch: task/0442-connect-link-not-post

## 1. Objective

The connect form POST navigated same-origin and was eaten by the PWA submit handling: the page hung on the skeleton loader and nothing happened (live-observed; Cmd+click, which falls back to plain link navigation, worked). The button is now a plain link (GET) — the navigation path that provably works — opening the single-use Stripe onboarding in a new tab.

## 2. Context

- The GET route already exists (it is the refresh target) and carries the same session guard; no server change needed.
- The PWA layer intercepts form POSTs (progress/skeleton handling); plain link navigation bypasses it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/payments.html` | edit | form POST -> ui_button href with target=_blank rel=noopener |

## 4. Steps

1. Replace the form with a ui_button link to /payments/connect/start, target=_blank rel=noopener.

## 5. Do not touch

Routes (GET handler unchanged, POST handler remains for API compat), service worker.

## 6. Commands

- `pytest tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payments.py tests/test_payments_dashboard.py -q --tb=short` -> `58 passed`

## 7. Acceptance

- [x] Plain click opens the Stripe onboarding in a new tab (same navigation as the live-verified Cmd+click path).
- [x] Dashboard tab stays open; tests green.

## 8. Stop and ask

None.

## 9. Report

`docs/tasks/0442-report.md` — Status: review.
