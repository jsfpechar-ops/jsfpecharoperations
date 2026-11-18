# 1857 report

Status: review (Go route switch pending for 2 cases)

## Landed

- `data-stays-more` on wrapper; `host.js` phone append + `replaceState`
- `filters_test.go`
- `App/tests/test_1857_stays_more_browser.py` (no-JS plain link passes on Python HTML)

## Tests

```
go test ./internal/web/stays/... 2>&1 | tail -30 → ok
pytest tests/test_1857_stays_more_browser.py -q 2>&1 | tail -30 → 1 passed, 1 skipped (Go append)
```

Owner: enable Go `/reservations` to un-skip append test.