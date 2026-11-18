# 1858 report

Status: review (Go route switch pending)

## Landed

- `TurboCache` on Stays handler; `shell.html` conditional meta
- `host.js` turbo:before-cache / turbo:load heal scoped to stays
- `cache_test.go`
- `App/tests/test_1858_stays_back_cache_browser.py` (skips without Go HTML + `content="cache"`)

## Tests

```
go test ./internal/hostweb/layout/... ./internal/web/stays/... 2>&1 | tail -30 → ok
pytest tests/test_1858_stays_back_cache_browser.py -q 2>&1 | tail -30 → 1 skipped
```