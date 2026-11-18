# 1702c: Go property settings 3c: save the property settings (POST /apartments/{id}, no wizard step)

Status: split (exact-diff pass 2026-11-17) into [1702c1](1702c1-go-apartment-save-core.md) (ready: the save, redirects, golden pair) and [1702c2](1702c2-go-apartment-save-refused-page.md) (todo, scoped: the refused page drawn again). Execute those, not this file.
Depends on: 1702b | Base commit: current tip of the working branch | Branch: task/1702c-go-apartment-save
Executor: Haiku 5.5 | Tier: A (Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Commit each step as `1702c step k`; never branch, push or open a PR.

## 1. Objective

Port `apartment_update` (`App/app/routes/admin.py` 2535-2601) and `_save_apartment_form` (2791-3046) for a post **without** `setup_step`, as Python behaves today. It writes police filing data (rule 1, [UBYPORT_CORE](../UBYPORT_CORE.md)).

## 2. Context (from the 1702b pass)

- Helpers to port line by line: `_with_lock_tab_hours` 2771, `_property_hour_changes` 2751, `_apartment_payload` 1749 (with `_automation_timing_values`, `stay_fee_routes.fee_form_values`), `_apply_police_defaults` 1780, `_property_operator_error` 404, `_property_draft` 423, `_refuse_apartment_save` 2303 (draft overlay, `_save_error` list, status 400 rule), `refuse_fee_save` 2404 (`_fee_save_errors` 2388; its wizard branch is 1702e), `_missing_report_labels` 328, `_form_return_to` 342.
- Reuse, never copy: `server.enter` (`_csrf`, id, login), `Pages.detailLoad` (owner scope `IS NOT DISTINCT FROM` the workspace), `Pages.detailRender` and the view error fields of 1702b, `apartmentOperatorError`, `apartmentAddressErrors`, `apartmentFormInt`, `newApartmentPayload` pieces of 1700b2 (refactor only by exact diff), `validation.ValidateApartment`/`ErrorsOnly`, the `stayfees` account, guest-pay and rate helpers (`apply_fee_account`, `check_guest_pay_setup`, `apply_guest_operator_account`, `record_rate_change`, `reconcile_no_pay_way_alert`: grep `go/internal/web/stayfees` and `go/internal/stayfee*` first), `detailLockAllowed`/`detailLockUsers` (lock edits, as 1702), `secure` for `uby_ws_password_enc`, the slug helper of `slug.go` (`guest_slug.follow_name`), the alerts resolve helper (`ubyport_auth_failed:<id>`), `server.audit` (`apartment_updated`, `door_codes_on/off`).
- A post with `setup_step`, a retired step, `fee_signature_section=1` with a drawn signature, or police-letter ticks answers `notPorted` until 1702d/1702e (dormant route, no partial write).
- Parity (owner decision, as 1700b*): `App/scripts/go_apartment_update_golden.py` + `App/tests/test_go_apartment_update_golden.py` on the harness of `go_apartment_create_golden.py`/`test_go_apartment_create_golden.py`: seeds, posts through the real FastAPI app, writes `testdata/apartment_update_golden.json` (rows, audit, Location, re-render fragments, also for refused input: no partial write); the Go test replays the seeds and must match. Accepted differences are listed in the report.
- Mid-filing guard: a property with `submit_state` set must not lose a required police field (same refusal as Python).

## 3. Files

Fixed by the exact-diff pass. Expected: `go/internal/web/properties/apartment_update*.go` (+ tests, testdata), `go/cmd/ubyhost-web/register_web_properties_apartment_update.go` (+ test), a catalog dir `apartmentupdate/` for new flash keys, the golden script pair, `docs/tasks/1702c-files/**`, `docs/tasks/1702c-report.md`.

## 5. Do not touch

`UBYHOST_GO_PATHS`, server files, `App/app/`, filing code beyond calling it.

## 9. Report

`docs/tasks/1702c-report.md`; UX: the 400 re-render screenshots stay pending until 1705.
