# 2035 report

Status: review

## Files changed

- `go/internal/web/properties/apartment_detail.go` — missing property and missing copy source use `hostweb.NotFoundPage`.
- `go/internal/web/properties/apartment_new.go` — missing copy source uses `hostweb.NotFoundPage`.
- `go/internal/web/properties/apartment_detail_test.go` — branded 404 body expectations.
- `go/internal/web/properties/apartment_new_test.go` — same; removed plain-text 404 fallback assertion.
- `docs/tasks/2035-go-property-branded-404.md` — brief copy.

## Commands (last 5 lines)

**gofmt** — no output (ok).

**go test** (from `go/`):

```
ok  	.../go/internal/web/properties	0.094s
ok  	.../go/internal/hostweb	0.048s
ok  	.../go/internal/hostweb/layout	0.139s
```

**pytest layout lint** (from `App/`):

```
....                                                                     [100%]
4 passed in 228.55s (0:03:48)
```

## §7 acceptance

- [x] Branded HTML 404 (title, heading, home link) for unknown property, unknown/inaccessible copy source; Go tests assert `Page not found` + `href="/"`.
- [x] Scope checks unchanged; Go property tests green (includes cross-workspace negatives).
- [ ] Staging: owner opens three live 404 URLs after deploy (not run here).

## Deviations

None.

## Questions

None.

## Owner steps left

1. Verify PR screenshot/CI evidence; deploy SHA to staging and spot-check the three 404 examples in the brief.