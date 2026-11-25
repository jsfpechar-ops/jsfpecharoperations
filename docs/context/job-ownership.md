# Worker job intervals

These intervals apply whether Python or Go runs a kind. When `UBYHOST_SCHEDULER=go`, Go enqueues every kind on the same schedule as `App/app/scheduler.py` (`job_intervals()`). Kinds listed in `UBYHOST_GO_JOB_KINDS` are executed in `go/cmd/ubyhost-web/` (for example `register_job_guide_import.go` for `guide_import`); other kinds still run in the Python worker. The Operations page calls a job late when its last success is older than twice its interval.

| Job | Every | Why |
|---|---|---|
| `ical` | `ICAL_POLL_MINUTES` | Calendar feeds change slowly; the poll rate is set in config. |
| `submit` | `SUBMIT_SWEEP_MINUTES` | UbyPort submission sweep; set in config. |
| `deadlines` | 30 min | The police deadline watch; alerts are due within hours, not minutes. |
| `mail` | 5 min | Drains the mail queue. |
| `meta_capi` | 10 min | Conversion events; no user waits on them. |
| `posthog` | 15 min | Analytics sync; no user waits on it. |
| `door_codes` | 5 min | Reconciles door PINs with the lock gateway. A 5-minute lag is acceptable; the gateway is slow and rate-limited. |
| `push` | 1 min | Drains `push_outbox`, the queue of alerts due now. It must stay at one minute so alerts arrive promptly. |
| `guide_import` | 60 min | Drains queued `guide_import` rows (Booking, Airbnb, and public-page URL on Go). Fetches via Apify, then merges draft guide cards. Hourly is enough. Handler: Python `guest_guide_import` / `guest_guide_merge`; Go `go/internal/guideimport` when the kind is in `UBYHOST_GO_JOB_KINDS`. |
| `photo_sweep` | 12 h | Cleans up passport photos on a schedule. |
| `retention` | daily | Retention deletions run once a day. |
| `stay_fee_mail`, `billing_snapshot` | daily | Billing jobs run once a day. |
| `stripe_sweep` | daily | Payment expiry and webhook dedupe; skipped (no schedule) when `UBYHOST_PAYMENTS_RETIRED=1`. `billing_snapshot` keeps running. |

Change a value here and in `job_intervals()` together. `App/tests/test_scheduler.py` checks the three values set on 2026-10-31.
