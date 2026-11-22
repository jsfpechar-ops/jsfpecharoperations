# 2034 report

Status: review

## Files changed

- `go/internal/web/booking/pages.go` — `TermsHandler` takes `getenv`; passes `PaymentsRetired` as `Guest.Data`.
- `go/cmd/ubyhost-web/register_web_booking_pages.go` — wires `booking.TermsHandler(os.Getenv)`.
- `go/internal/web/booking/templates/terms.tmpl` — localized `role="note"` when `.Data` true.
- `go/internal/web/booking/pages_test.go` — `TestTermsRetiredNotice` (EN/CS, flag off/on).

## Commands (last 5 lines)

**Go tests:**
```
=== RUN   TestTermsRetiredNotice
--- PASS: TestTermsRetiredNotice (0.00s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking	0.013s
```

**Browser lint:**
```
....                                                                     [100%]
4 passed in 226.41s (0:03:46)
```

## Acceptance (§7)

- [x] Both localized notices with `UBYHOST_PAYMENTS_RETIRED=1`; absent when clear.
- [x] Card terms, lang switch, noindex unchanged in tests.
- [ ] Staging: seeded listing + webhook under retirement (owner deploy).

## Deviations

None.

## Questions

None.

## Owner steps

1. Review PR copy (EN/CS notice).
2. Deploy SHA to staging with retired payments; confirm screenshots 390/1280 both langs on Go terms page.