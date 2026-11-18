# 1856 report

Status: review (browser/UX gate blocked on Go route switch)

## Landed

- Full `go/internal/web/stays/templates/stays_list.tmpl` port (banner, chips, filter, phone groups, desk rows/menus, pager, `data-stays-more`, empty states, index card)
- `v2_status_pill` demo branch matches Python (`p-n` on demo ready rows)
- `parity_test.go` + `testdata/stays_page{1,2}.html`, `stays_report_failed.html`; `handlers_test.go` render markers
- `tpl.go` helpers: `encode_return`, `day_of_month`, `is_nil_int`
- Removed duplicate `stays_list_gen.tmpl`

## Tests (tails)

```
go test ./internal/web/stays/... 2>&1 | tail -30
ok .../stays 0.027s
```

Browser row: `test_1857` / `test_1858` skip until `GET /reservations` is served from Go (`UBYHOST_GO_PATHS`).

## Blockers

- `UBYHOST_GO_PATHS` must include `/reservations` for Playwright append/cache proofs and UX gate screenshots (390/768/1280).
- Full brief §6 browser row (`0766`, `layout_lint`, `host_geometry`) not run on Go HTML yet.

## Owner

Add `/reservations` to `UBYHOST_GO_PATHS`, reload Caddy, then re-run browser rows per brief §7.