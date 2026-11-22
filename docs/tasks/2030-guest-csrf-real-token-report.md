# 2030 report: Guest CSRF real token

Status: review

## Files

- `go/internal/web/guest/form_pages.go` — mint CSRF in remove confirm + `buildFormView`; removed `*` stubs.
- `go/internal/web/guest/stay_claim.go` — mint on claim + confirm pages.
- `go/internal/web/guest/csrf_forms_test.go` — GET/POST round-trip (skips without `UBYHOST_TEST_DATABASE_URL`).
- `go/internal/web/guest/form_save.go` — `buildFormView` call passes `w` (compile-only).

## Commands

```
cd go && go test ./internal/web/guest/... ./internal/hostweb/... 2>&1 | tail -30
ok  	.../guest	0.029s
ok  	.../hostweb	(cached)

gofmt -l (touched go files) — empty
```

## §7

- [x] No `return "*"` in `go/internal/web/guest/*.go`
- [x] Round-trip test added; goldens unchanged
- [x] No template/CSS change — no screenshot
- [x] Owner: on staging, guest link → PIN → party step → claim mail

## Deviations

`form_save.go` one-line signature fix (not in brief §3; required after `buildFormView` gained `w`).

CI fix: `party_claimed` GET uses `/claim` (overview has no `_csrf` when claim state is claimed).

## Questions

None.