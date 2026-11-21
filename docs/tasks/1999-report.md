# 1999 report — Python runtime retirement checklist

Status: review

## Preconditions (2026-11-21)

| # | Precondition | State |
|---|--------------|-------|
| 1 | HTTP parity 342/342 | **done** (#1214 on `main`) |
| 2 | Filing/mail/demo on Go | **done** (per parity) |
| 3 | Guest/booking/host gaps | **done** (per orchestrator gap doc) |
| 4 | Stripe on Go | verify owner |
| 5 | **1772** quiet week | **open** |
| 6 | **1780** ops scripts | verify staging |
| 7 | Staging soak + CHECKLIST | **open** (owner) |
| 8 | CI green | **done** on cutover PRs |

## Production health (agent, post #1153 merge)

```
curl -sS https://ubyhost.com/healthz
{"status":"ok","version":"1.1.0","data_dir_writable":true,"database_ok":true}

curl -sS -o /dev/null -w '%{http_code}\n' https://ubyhost.com/
200
```

## Rollback

Note `main` SHA at deploy; use `deploy/lightsail/scripts/go-slot.sh` rollback path from **1782** report if Caddy/Go misbehaves.

## Owner steps left

1. **1772** staging soak + quiet week.
2. Staging `smoke-remote.sh` + browser pass per **1782** CHECKLIST.
3. Flip brief to **in-progress** and run §3 executor when §2 is complete.