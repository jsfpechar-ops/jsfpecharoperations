# 1858 report

Status: review (Turbo cache browser proof pending Go route)

## Landed

- `TurboCache: "cache"` on stays handler; conditional meta in Go shell (prior commits)
- `host.js` scoped heal handlers (prior commits)
- `cache_test.go` structural checks
- `App/tests/test_1858_stays_back_cache_browser.py` (skipped without `content="cache"`)

## Tests (tails)

```
pytest tests/test_1858_stays_back_cache_browser.py -q 2>&1 | tail -30
(skipped — Turbo cache meta only on Go-served Stays)
```

## Blocker

Back/scroll case needs Go-served `/reservations` with `turbo-cache-control` = `cache`. Switch `UBYHOST_GO_PATHS`, then run brief §6 browser row.