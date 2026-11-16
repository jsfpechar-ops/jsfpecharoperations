# Integration: TTLock (smart door locks, door codes)

| Item | Value | Source |
|---|---|---|
| API base | `UBYHOST_TTLOCK_API_BASE`, default `https://euapi.ttlock.com` (EU) | `App/app/config.py:169` |
| Auth | `UBYHOST_TTLOCK_CLIENT_ID` / `UBYHOST_TTLOCK_CLIENT_SECRET` (env; Render marks them `sync: false`) | `App/app/config.py:170-171`, `render.yaml` |
| Feature switch | `UBYHOST_DOOR_CODES` default `0` (off); `UBYHOST_DOOR_CODES_LIVE` default `0` | `App/app/config.py:168`, `:194` |
| Call budget | `UBYHOST_TTLOCK_MONTHLY_CALLS`, default 30000 | `App/app/config.py:172` |
| Worker job | `door_codes` every **5** min: stay PIN reconcile, cleaning checkout events, permanent cleaning-code queue | `App/app/scheduler.py` `job_intervals()`; Go `go/cmd/ubyhost-web/register_job_door_codes.go` when `door_codes` is in `UBYHOST_GO_JOB_KINDS` |
| Cleaning code latency | After the host creates or removes a **cleaning** TTLock code (Go cleaning settings), `ubyhost-go` runs one queue pass in the background so the lock updates in seconds. The 5-minute job remains the fallback and the only retry path. Requires `UBYHOST_DOOR_CODES` on and Go owning `door_codes` (not Python). | `go/cmd/ubyhost-web/cleaning_queue_kick.go`, `go/internal/web/cleaning/host_codes.go` |
| Retry | Cleaning-code rows retry transient TTLock errors while `attempts < 5` | `go/internal/doorcodes/cleaning/deps.go` (`queueMaxAttempts`); Python `App/app/cleaning_codes.py` |
| Sandbox | `⚠️ UNKNOWN` — `docs/TTLOCK.md` (owner doc) describes staging use | `docs/TTLOCK.md` |
| Rate limits | monthly call budget only; per-second limit `⚠️ UNKNOWN` | — |
| Code | Python: `App/app/ttlock.py`, `door_codes.py`, `cleaning_codes.py`. Go: `go/internal/doorcodes/`, `go/internal/web/cleaning/` | — |

Staging: door codes on Render staging with sync off until `UBYHOST_DOOR_CODES_LIVE=1`
(`render.yaml`, comment block).

When `door_codes` runs in Go, the `ubyhost-go` container must receive the TTLock and door-code variables listed in `deploy/lightsail/docker-compose.yml` (same names as the Python worker).

## Official references

- Official docs: https://euopen.ttlock.com/doc/api/v3/lock/list