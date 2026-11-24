# 2063 report

Status: blocked (partial, tool-call cap reached)
Done: steps 1 to 3

## Commits

- `57fdd05 2063 step 3`: `go/internal/web/guest/stay_fee_panel.go` (new). Types `feeRail`, `feePerson`, `feePanel`; pure `buildFeePanel(fee, qr, cashDefault)`; `loadFeePanel` on `stayClaimDeps` (guest-pay switch as Python; Prague today; `stayfee.LoadApartment` and `stayfee.LoadCompletionFee`; failures logged as `stay_fee_panel_failed` with no amounts or names, box dropped). `go build ./internal/web/guest/` passes.

## Not done

- Step 4 (view glue): `stay_view.go` (FeePanel field, call after the HasRemaining block, drop the "not ported" comment), `stay.tmpl` (fee block before the party stepper, `all_done_body_fee`), the `fee_pay` partial, `pages.go`.
- Step 5 (tests): `stay_fee_panel_test.go` and the key test. `TestBuildFeePanel` is planned, not written.
- Step 6: the PR is not opened.

## Condition

Python's: the box is built only when `remaining <= 0`, `UBYHOST_STAY_FEE_GUEST_PAY` lowercased and stripped equals `on`, and `stayfee` returns a fee (apartment collect flag, total > 0).

## Deviations

- Decrypter: `stayClaimDeps` has no decrypter field, but it has `getenv`. `loadFeePanel` uses `secure.LoadDataKeys(d.getenv)` as `guestSaveDecrypter` does. Nothing was wired from `cmd/ubyhost-web`.
- Commits were made as `git add` and `git commit` in separate calls, one commit per step.
- Build not run for `go test` (no test file yet).

## Owner steps left

None for the Go side yet. Brief 2063 must finish steps 4 to 6 before the guest deploy.
