# 1857 report

Status: review (Go-route browser proof pending)

## Landed

- `data-stays-more` on Go stays template; `host.js` phone append (already on branch)
- `filters_test.go` chip rules
- `App/tests/test_1857_stays_more_browser.py` (1 passed, 1 skipped without Go route)

## Tests (tails)

```
pytest tests/test_1857_stays_more_browser.py -q 2>&1 | tail -30
1 passed, 2 skipped in 4.33s
```

## Blocker

`test_phone_show_more_appends_rows` skips when page lacks `data-stays-more` (Python still serves `/reservations` in App TestClient runs). Enable Go path and re-run full brief §6 row.