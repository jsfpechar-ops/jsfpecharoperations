# 1702c2: Go property settings 3c2: the page a refused settings save draws again

Status: todo — scoped (split out of 1702c by its exact-diff pass, 2026-11-17). Executable only after its own exact-diff pass (sidecars in `docs/tasks/1702c2-files/`, step-0 hashes, sha256 table, rules of [workflow](../context/workflow.md#writing-briefs-for-haiku)).
Depends on: 1702c1 | Base commit: current tip of the working branch | Branch: task/1702c2-go-apartment-save-refused-page
Executor: Haiku 5.5 | Tier: A (Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Commit each step as `1702c2 step k`; never branch, push or open a PR.

## 1. Objective

Replace the body of `refuseApartmentSave` (`go/internal/web/properties/apartment_update.go`, the 1702c1 seam that answers `notPorted`) with Python's `_refuse_apartment_save` (`App/app/routes/admin.py` 2303-2385) and the property-page branch of `refuse_fee_save` (2404-2498, with `_fee_save_errors` 2388): the page drawn again through `Pages.detailRender` with the host's unsaved values, status 400 (200 for `operator_refresh`). Nothing is written.

## 2. Context (from the 1702c pass)

- The seam receives `apartmentRefusal{operatorError, addressErrors, sharedTimeError, lockTimesError, feeAccountError}`; its callers and order are final in 1702c1. Keys come from Go code only (`{{t .OpError}}`, `{{t .SharedTimeError}}`).
- Draft (`_property_draft` 423): every `apartmentTextFields` value posted replaces the row's; `legal_entity_id` always the posted int (none: no operator); `data_controller_entity_id` only when posted; `checkin_hour`/`checkout_hour` only when posted, through `_hour_or_none` (133: 0..23 or none, never text). A lock-times refusal keeps the posted `lock_id` (else the stored one) and opens `section=lock`; `door_switch_posted` is read by no template (1702b).
- View fields of 1702b to fill: `SaveErrors` (`_save_error` order: address fields in `addressErrors` order, then `legal_entity_id` or `data_controller_entity_id`, then `checkin_hour`, then `lock/lock_checkin_hour`; fee: `_fee_save_errors`), `AddressErrors`, `OperatorError`, `SharedTimeError`, `LockTimesError`, `FeeAccountError`, `Status`, `SettingsSection` (`property`, `lock` or `reporting`), `property_view=settings`. Python always passes `copy_property_peers` here (GET only when setup is unfinished): check what the template shows with it before porting.
- Fee branch (`refuse_fee_save`): the fee draft is `fee_form_values(form)` without the raw keys, the posted `stay_fee_council_account` with no IBAN, the typed `account_prefix/number/bank` (`fee_account_draft`), `flash_error` drawn on the page (`flash.stay_fees.account_invalid`; the link, rate and operator-account flashes belong to the guest-pay block, still `notPorted`), `fee_return_to` (`fee_return_path`; a posted `fee_return_to` is still `notPorted` until 1702d), `guest_pay_operator` (reuse `stayfees.GuestPayOperator` of 1701b). A wizard `return_to` never reaches here (1702c1 sends it to Python).
- Parity: extend `App/scripts/go_apartment_update_golden.py` with page `fragments` for the nine `page` cases (patterns as `go_apartment_create_golden.py` FRAGMENTS, plus the save summary, the address `aria-invalid` lines, the operator/controller messages, the shared and lock time lines, the council-account line, `data-dirty-start`) and turn the `page` branch of `TestApartmentUpdateMatchesPython` into an exact status + fragments comparison. Accepted differences go in the report.
- UX gate: template unchanged (1702b drew the lines); the 400 screenshots stay pending until 1705.

## 3. Files

Fixed by the exact-diff pass. Expected: `go/internal/web/properties/apartment_update.go` (the seam only), maybe `apartment_detail.go` (a draft hook in `detailBuild`), `apartment_update_test.go`, the golden script, its JSON and its Python test, `docs/tasks/1702c2-files/**`, `docs/tasks/1702c2-report.md`.

## 5. Do not touch

`UBYHOST_GO_PATHS`, server files, `App/app/`, filing code.

## 9. Report

`docs/tasks/1702c2-report.md`; UX: the 400 re-render screenshots stay pending until 1705.
