# 1858 report

Status: partial

## Landed

- `layout.Page.TurboCache`; `shell.html` conditional meta
- Stays handler sets `TurboCache: "cache"`
- `host.js`: `turbo:before-cache`, `turbo:load`, `pageshow` heal (scoped to stays)
- `cache_test.go`

## Not done

- `test_1858_stays_back_cache_browser.py`
- Stale-data browser proof; scroll-restore case
- PR Step 1 dependency scan write-up