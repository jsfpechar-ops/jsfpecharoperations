# 2030: Go port of the stay-fee guest-pay block (stay_fee_guest_form) on property create and update

Status: todo
Depends on: 2029 | Base commit: main after 2029 merges | Branch: task/2030-go-guest-pay-block
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (if you hit 25 calls, hand over per executor.md; this brief may need two sessions)

## 1. Objective

Go saves the guest-pay fields (rails, Revolut link, cash note, default rail, collect flag, operator account) when a property form posts `stay_fee_guest_form`, as Python does. After 2029 these posts redirect with the interim "not saved here" flash; this brief removes that.

## 2. Context

Python source of truth: `App/app/routes/stay_fees.py` `guest_pay_values` (283-309), the `STAY_FEE_GUEST_PAY and "stay_fee_guest_form" in form` branch (381), `apply_fee_account` / `revolut_link_ok`, and the operator-account block from line 615 (`apply_guest_operator_account`, `GUEST_OPERATOR_ACCOUNT_INVALID`). Go today: `apartmentNotPortedFields = []string{"stay_fee_guest_form"}` in `go/internal/web/properties/apartment_create.go:77`, used by `apartment_create.go` and `apartmentUpdateNotPorted` in `apartment_update.go`; the `refuse_fee_save` draft_account case at `apartment_update.go:122`. Kill switch: env `STAY_FEE_GUEST_PAY` (see docs/ENVIRONMENT.md, one section); with it off nothing is read. Stay-fee data is money data: rule 1 and RETENTION unchanged, no new personal field.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/stay_fee_guest_pay.go` | new | `guestPayValues(r)`, `revolutLinkOK`, operator-account apply, ported 1:1 from the Python above |
| `go/internal/web/properties/stay_fee_guest_pay_test.go` | new | table tests below |
| `go/internal/web/properties/apartment_create.go` | edit | drop `stay_fee_guest_form` from `apartmentNotPortedFields`; merge the values into the insert |
| `go/internal/web/properties/apartment_update.go` | edit | same for update; port the `:122` refused-account draft case |
| `go/internal/web/properties/apartment_create_test.go`, `apartment_update_test.go` | edit | replace the "guest pay block" not-ported case (create_test.go:351) with a save case |
| `docs/context/known-issues.md` | edit | remove the 2029 guest-pay line |

No other file may change.

## 4. Steps

1. Read `guest_pay_values` and write `guestPayValues` with the same rail normalisation (`qr` to `iban`), sorted csv, note cut at the Python `GUEST_NOTE_MAX`, Revolut link adds the rail, default-rail fallback order of `GUEST_RAILS`. Test with Python-recorded cases (run the Python function once in a scratch shell and paste inputs and outputs into the table; do not commit the scratch).
2. Wire create, then update. Kill switch off: read nothing, keep stored values.
3. Port the operator-account rules (account needed only when rails need it and `stay_fee_collect`; invalid raises the same flash key as Python). Test: needed and missing, present, cleared, switch off.
4. Remove the interim redirect for this branch; run §6; commit `2030 step k` each step.

## 5. Do not touch

Templates, CSS, `App/`, billing, UbyPort. No new dependency. No new personal-data field (rule 2).

## 6. Commands

From `go/`: `go test ./internal/web/properties/... 2>&1 | tail -30`. DB tests skip without `UBYHOST_TEST_DATABASE_URL`; say so in the report. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] POST with `stay_fee_guest_form` saves the same columns as Python for the recorded cases.
- [ ] Switch off: stored guest-pay values unchanged.
- [ ] `git grep -n stay_fee_guest_form -- go ':!*_test.go'` shows only the template reader and the new file.
- [ ] No template change, so no screenshots.

## 8. Stop and ask

An excerpt is not found, a Python rule is unclear, a test fails twice, a file outside §3 needs a change, 25 calls reached. Never push or merge.

## 9. Report

`docs/tasks/2030-report.md`, 600 tokens at most.

## Risk list (for the reviewer)

`stay_fee_guest_pay.go` rails and operator-account logic (money fields).

## Owner steps

1. Open the draft PR, wait for CI green, mark ready.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. After deploy, open a property, tick two guest-pay options, save, reload. Expect the choices to stay.
