# Worker job intervals

The worker (`App/app/scheduler.py`, `job_intervals()`) runs these jobs. The Operations page calls a job late when its last success is older than twice its interval.

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
| `guide_import` | 60 min | Processes queued guide imports. Imports are not time-critical, so hourly is enough. |
| `photo_sweep` | 12 h | Cleans up passport photos on a schedule. |
| `retention` | daily | Retention deletions run once a day. |
| `stay_fee_mail`, `stripe_sweep`, `billing_snapshot` | daily | Billing jobs run once a day. |

Change a value here and in `job_intervals()` together. `App/tests/test_scheduler.py` checks the three values set on 2026-10-31.
