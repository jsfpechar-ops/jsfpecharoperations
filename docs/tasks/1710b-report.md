# 1710b report

Status: review

## Files

`booking_sites_list.go`, `booking_sites_list_test.go`, i18n catalog, `templates/booking_sites.tmpl`, golden JSON, `register_web_booking_host_booking_sites.go` (+ test), golden script/pytest, `docs/tasks/1710b-go-booking-sites-list.md`, `docs/tasks/1710b-files/`.

## Commands

- `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1` — ok
- `pytest tests/test_go_booking_sites_list_golden.py -q` — 1 passed
- `context_lint.py` — OK

## §7

- [x] GET `/booking-sites` registered dormant
- [x] Single-apartment 303 to setup; multi lists rows; `SiteAllowed` banner
- [x] Golden shape tests

## Deviations

`docs/tasks/1710b-files/` was not on origin/main; sidecars generated from implementation in this run (Composer exact-diff + executor).

## UX gate

Pending path switch (rule 10); dormant until 1714.

## Owner steps

None.