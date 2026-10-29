# 0442 report

Status: review
Branch: task/0442-connect-link-not-post

## Files changed

- `App/app/templates/payments.html` — the connect button is a plain link (GET /payments/connect/start, target=_blank rel=noopener), not a form POST.

## Commands (last lines)

- payments scope: `58 passed in 5.10s` (fresh venv from requirements.lock + requirements-dev.txt)

## Deviations

None. The POST route stays (CSRF-protected, unchanged) — API compat and any future in-app use.

## Owner steps left

Merge + deploy; a plain click on "Open Stripe" should open the onboarding tab directly.
