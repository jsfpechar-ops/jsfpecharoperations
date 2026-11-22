# 2030 report

Status: review

## Files

- `go/internal/web/properties/stay_fee_guest_pay.go` (new)
- `go/internal/web/properties/stay_fee_guest_pay_test.go` (new)
- `go/internal/web/properties/apartment_create.go`, `apartment_update.go`
- `apartment_create_test.go`, `apartment_update_test.go`
- `docs/context/known-issues-recent.md` (guest-pay refs removed from K-2029; brief named `known-issues.md` but line lives in recent)

## Commands

`go test ./internal/web/properties/...` → ok (no `UBYHOST_TEST_DATABASE_URL`; DB-backed cases skipped)
`python3 scripts/context_lint.py` → context lint: OK
`gofmt -l ./internal/web/properties/` → clean

## §7

- [x] POST `stay_fee_guest_form` writes guest-pay columns (unit + save tests when DB present)
- [x] Kill switch off leaves values unchanged (`TestStayFeeGuestPaySwitchOff`)
- [x] `stay_fee_guest_form` in Go non-test code: template + `stay_fee_guest_pay.go`
- [x] No template/screenshot change

## Deviations

K-2029 edit applied in `known-issues-recent.md` (not parent `known-issues.md`).

## Owner

Draft PR → CI green → ready; merge `scripts/merge-pr-on-green.sh`; smoke guest-pay save on a property.