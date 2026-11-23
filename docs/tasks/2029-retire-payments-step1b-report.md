# 2029 step 1b report

Status: review

## Files changed
- `go/internal/web/booking/property.go` — `Bookable` false when `PaymentsRetired`
- `go/internal/web/booking/property_test.go` — `TestPropertyPagePaymentsRetiredHidesBook`
- `App/app/property_page.py` — `widget_ready` returns false when retired
- `App/app/routes/property_page.py` — mirror `bookable` guard

## Commands (last 5 lines)
Go: `ok .../internal/web/booking 0.054s`
Python: `14 passed in 2.66s`

## §7 (step 1b scope)
- [x] RETIRED=1: property page has no `#book` / checkout CTA (Go test)
- [x] RETIRED unset: existing property tests unchanged
- [x] No migration, no secrets

## Deviations
No 390 px screenshot: handler-only change (template already gated on `bookable`).

## Questions
None.

## Owner
Merge after step 1 PR; stack 1b on step 1 branch.