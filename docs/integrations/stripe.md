# Integration: Stripe (payments and Connect)

| Item | Value | Source |
|---|---|---|
| Client | `stripe` 16.0.1 | `App/requirements.txt`, `App/app/stripe_connect.py` |
| Mode | `UBYHOST_STRIPE_MODE`, default `off` | `App/app/config.py:176` |
| Auth | secret key `UBYHOST_STRIPE_SECRET_KEY`; webhook signing secret `UBYHOST_STRIPE_WEBHOOK_SECRET` (env only) | `App/app/config.py:177-178` |
| Webhook | `POST /webhooks/stripe`, public by design (`App/app/routes/stripe_connect.py:102-103`); dedupe table `stripe_webhook_events` | migration `App/app/migrations/0027_stripe_webhook_events.sql` |
| Connect | hosts onboard via Stripe Connect; `⚠️ UNKNOWN` account type and fee model (not read) | `App/app/stripe_connect.py`, migration `0026` |
| Sweeps | cron 04:15 `stripe_sweep` (payment-request expiry, webhook dedupe) | `App/app/scheduler.py` |
| Call budget | `UBYHOST_STRIPE_MONTHLY_API_CALLS`, default 50000 | `App/app/config.py:179` |
| Sandbox | Stripe test mode via `UBYHOST_STRIPE_MODE` — `⚠️ UNKNOWN` which key set is used in staging | — |
| Retry / idempotency | `⚠️ UNKNOWN` — not read in full | — |

Stripe is used for billing of hosts and payment requests. It is **not** part of the
police filing path. `⚠️ UNKNOWN`: whether Stripe is enabled in production
(`UBYHOST_STRIPE_MODE` value is not in the repo; `docs/context/status.md` says billing is ON).
