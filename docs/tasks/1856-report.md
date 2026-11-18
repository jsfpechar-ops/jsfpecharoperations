# 1856 report

Status: review

## Landed

- Full `go/internal/web/stays/templates/stays_list.tmpl` port of `reservations.html`
- `parity_test.go` + `testdata/stays_page{1,2}.html`, `stays_report_failed.html`
- `GET /reservations` registered in `register_web_stays.go`
- Go unit tests green

## Tests

```
go test ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30
ok .../stays; ok .../ubyhost-web
pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q 2>&1 | tail -30
17 passed in ~266s
```

## Go-switched browser (owner)

`test_1857` / `test_1858` append/cache cases **skip** until `UBYHOST_GO_PATHS` includes `/reservations` (Playwright hits Python HTML today). 390/768/1280 screenshots on Go HTML pending that switch.

## Owner

Add `/reservations` to `UBYHOST_GO_PATHS`, reload Caddy; re-run `0766`, `1857`, `1858` with 0 skipped.