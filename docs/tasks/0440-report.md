# 0440 report

Status: review
Branch: task/0440-connect-base-url

## Files changed

- `App/app/routes/stripe_connect.py` — connect start builds onboarding URLs from `config.app_base_url()` (env-configured https), not `request.base_url` (http behind the proxy).

## Commands (last lines)

- `37 passed in 3.31s` (stripe connect + rails)
- `from app.main import app` — ok

## Owner steps left

1. Ensure prod `.env` sets `UBYHOST_APP_BASE_URL=https://ubyhost.com` (or `UBYHOST_PUBLIC_BASE_URL`).
2. Merge + deploy.
3. Click "Open Stripe": the Stripe onboarding form should load and, after completion, return to the logged-in dashboard (no login-page bounce).
