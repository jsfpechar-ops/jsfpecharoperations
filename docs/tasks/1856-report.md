# 1856 report

Status: review (partial — UX gate pending)

## Landed

- **1855b:** `types.go`, `guests.go`, `progress_list.go`, `row_build.go` — row progress, deadline cell, send_enabled, guest names
- **1856:** `handlers.go`, `register_web_stays.go`, `templates/stays_list.tmpl` (simplified desk table + v2_status_pill define), `handlers_test.go`
- Merges: **1859** hide Payments, **1660** entry-code migration/retention

## Not done (blocker for §7)

- Full block-by-block port of `reservations.html` (add-stay panel, filter form, phone groups, row menus)
- `parity_test.go` / Python goldens
- Browser row: `test_0766_phone_stays_browser.py`, `test_layout_lint_browser.py`, `test_host_geometry.py` (0 skipped)
- 390/768/1280 screenshots

## Commands

```
go test ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30
ok .../stays (cached); ok .../ubyhost-web (cached)
go test ./internal/hostweb/layout/... 2>&1 | tail -30
ok .../layout 0.125s
pytest tests/test_payments_hidden.py tests/test_static_versions.py -q 2>&1 | tail -30
8 passed
python3 scripts/context_lint.py → OK
```

## Owner

After merge: add `/reservations` to `UBYHOST_GO_PATHS` per brief §7.