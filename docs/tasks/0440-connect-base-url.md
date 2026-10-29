# 0440: connect onboarding URLs from the configured public base

Status: review
Depends on: 0439 (merged; deployed) | Branch: task/0440-connect-base-url

## 1. Objective

Fix the onboarding bounce: the connect start/return URLs were built from `request.base_url`, which behind the TLS-terminating proxy (Cloudflare/Caddy) resolves to `http://…`. Stripe redirects back over http, the Secure session cookie is not sent, `auth.require_login` bounces the host to the login page — the "click Open Stripe, see UbyHost login page" symptom.

## 2. Context

- Live-verified chain (29 Oct): account creation works (acct in the production mirror, state pending), onboarding links generate, Stripe serves them. The bounce is the refresh/return URL being http.
- `config.app_base_url()` returns `UBYHOST_APP_BASE_URL` or `UBYHOST_PUBLIC_BASE_URL` — the env-configured canonical https URL.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/stripe_connect.py` | edit | onboarding_link base_url from config.app_base_url() |

## 4. Steps

1. Replace `str(request.base_url).rstrip("/")` with `config.app_base_url()` in `connect_start`.

## 5. Do not touch

Everything else; the module signature (`base_url=` kwarg) is unchanged.

## 6. Commands

- `pytest tests/test_stripe_connect.py tests/test_payment_rails.py -q --tb=short` → `37 passed`
- `from app.main import app` → ok

## 7. Acceptance

- [x] Onboarding link refresh/return URLs are the configured https base, never request-derived http.
- [x] Tests green; app imports.

## 8. Stop and ask

None.

## 9. Report

`docs/tasks/0440-report.md` — Status: review.
