# Integration: TTLock (smart door locks, door codes)

| Item | Value | Source |
|---|---|---|
| API base | `UBYHOST_TTLOCK_API_BASE`, default `https://euapi.ttlock.com` (EU) | `App/app/config.py:169` |
| Auth | `UBYHOST_TTLOCK_CLIENT_ID` / `UBYHOST_TTLOCK_CLIENT_SECRET` (env; Render marks them `sync: false`) | `App/app/config.py:170-171`, `render.yaml` |
| Feature switch | `UBYHOST_DOOR_CODES` default `0` (off); `UBYHOST_DOOR_CODES_LIVE` default `0` | `App/app/config.py:168`, `:194` |
| Call budget | `UBYHOST_TTLOCK_MONTHLY_CALLS`, default 30000 | `App/app/config.py:172` |
| Jobs | `door_codes` every 1 min: `door_codes.reconcile`, `cleaning.reconcile`, `cleaning_codes.process_queue` | `App/app/scheduler.py` |
| Retry | cleaning-code attempts capped at 5 (`App/app/cleaning_codes.py:156`) | — |
| Sandbox | `⚠️ UNKNOWN` — `docs/TTLOCK.md` (owner doc) describes staging use | `docs/TTLOCK.md` |
| Rate limits | monthly call budget only; per-second limit `⚠️ UNKNOWN` | — |
| Code | `App/app/ttlock.py`, `App/app/door_codes.py`, `App/app/cleaning_codes.py` | — |

Staging: door codes on Render staging with sync off until `UBYHOST_DOOR_CODES_LIVE=1`
(`render.yaml`, comment block).
