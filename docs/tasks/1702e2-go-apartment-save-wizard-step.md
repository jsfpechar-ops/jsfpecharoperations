# 1702e2: Go property settings 3e2: the wizard step save (setup_step) and its refusals

Status: todo — scoped (split out of 1702e by its exact-diff pass, 2026-11-17). Needs its own exact-diff pass (sidecars in `docs/tasks/1702e2-files/`, step-0 hashes, sha256 table) **after 1702d2 is done**: it changes the same `apartment_update.go` / `apartment_update_test.go`.
Decision 2026-11-17 (owner/orchestrator, rule 11): the wizard saves are ported to Go.
Depends on: 1702d2 (its last step committed) and 1702e1 | Base commit: current tip of the working branch | Branch: task/1702e2-go-apartment-save-wizard-step
Executor: Haiku 5.5 | Tier: A

> **One big PR mode.** Commit each step as `1702e2 step k`; never branch, push or open a PR.

## 1. Objective

Replace the seam `"a wizard step (brief 1702e)"` in `apartmentUpdateNotPorted` (`go/internal/web/properties/apartment_update.go`, about line 217) with the `setup_step` branches of `_save_apartment_form` (`App/app/routes/admin.py` 2791-3046) as Python behaves today. Only `property` and `police` save anything: `automation`, `stay_fee`, `door_lock` and `try_it` are `RETIRED_STEPS` (0884) and answer `303` to `/apartments/{id}/setup/done` before anything else (admin.py 2801-2805); an unknown `setup_step` is an ordinary settings save (`_wizard_setup_step` 1685).

## 2. Context (found by the 1702e exact-diff pass; not built yet)

- Payload: `_wizard_step_payload` (admin.py 1690-1719): property: the `STEP_FIELDS["property"]` text fields, `normalise_zip`, `city_en = guest_city(addr_obec)`, `_form_int` for both entity ids, `default_purpose` in `PURPOSE_CODES` else `"10"`; police: the five police fields, `uby_mark.upper()`, plus `_automation_timing_values` when `automation_mode` is posted. Reuse the Go twins already in `properties` (grep `apartmentPayload`, `normaliseZip`, `GuestCity`, `PurposeCodes` in `go/` first) and `onboarding.StepFields`.
- Hours (2817-2884): `owns_shared_hours` is true for `property`; `_property_hour_changes`; on the property step a blank posted select is `flash.error.times_required`; a bad hour `flash.error.door_code_hours`. The refusal is `onboarding.RenderSetupPage(..., "property", SetupPage{Status: 400, Notice: <flash text>, Draft: <_property_draft keys in form + posted hours>})` (1702e1). The `door_lock` branches (`_lock_section_refusal`, `edits_lock`) are unreachable for a wizard post (retired) and are not ported for `setup_step`.
- Operator (2892-2913): property step: `_property_operator_error` -> `_refuse_apartment_save` (1702c2's `refuseApartmentSave`), whose Python version calls `refuse_setup_save` first (admin.py 2333) when `setup_step` is a step: so the Go refusal must route to `RenderSetupPage` with `OperatorError` and the `refuse_setup_save` draft (onboarding_wizard.py 237-271: owned text fields in form, `legal_entity_id` blank keeps the stored one, `default_purpose`, police `automation_mode`/`submit_after_hours`) instead of the settings page. Police step with a posted `legal_entity_id`: the probe and `refuse_setup_save(operator_error=...)` (2902-2913).
- Address (2928-2936): property step: `_create_address_errors` on the merged row -> the same `refuseApartmentSave` route -> `RenderSetupPage` with `AddressErrors` (reuse `apartmentAddressErrors`, already in the host's language).
- Police (2938-2958): `automation_choice_error` (Go: grep `AutomationChoiceError` / the 1602 timing check in `onboarding/wizard_post.go`) -> `OperatorError`; `_wizard_police_format_errors` (2627-2643: `validation.ValidateApartment` on the probe with the posted or stored decrypted password, only the four fields, only non-empty ones, first issue per field, Python dict order) -> `PoliceErrors` (messages through the same `validation_message` translation `apartmentAddressErrors` uses); a typed password is encrypted (`secure`, as 1702d1); `credentials_changed` (3006-3013) -> `privacy.ResolveAlert("ubyport_auth_failed:{id}")`. A typed password on the police step also triggers 1702d2's connection test (admin.py 3488/3614: `wizard = setup_step == "police"`): check how 1702d2 left `apartmentUpdateNotPorted` and keep its rule.
- Skipped for `setup_step`: `active`, the permalink PIN, the fee account (`setup_step in ("", "stay_fee")`), the address-only pops (`not setup_step`).
- Writes: one `UPDATE apartment` through the existing owner-scoped save of 1702c1, `apartment_updated` audit, `follow_name` on a changed name, `reconcile_no_pay_way_alert`: all already in Go; reuse.
- After the write: 1702e3 (`_setup_after_save`). Until 1702e3, a successful wizard save answers the existing seam for a `return_to` inside the wizard (`"a return_to inside the setup wizard (brief 1702e)"`, rename to 1702e3).
- CSRF: the handler is the existing `POST /apartments/{id}` behind `enter`; nothing new.
- Tests: extend `TestApartmentUpdateMatchesPython` only if `App/scripts/go_apartment_update_golden.py` already records wizard cases; else Go-only cases with hand-written expected output in `apartment_update_test.go` (retired step -> done; times_required; bad hour; operator missing; address error; police format error; mark upper-cased and saved; foreign apartment). No new Python test file.
- Size: likely one Haiku session; the exact-diff pass may split police (format errors, password, alert) from property.

## 3. Files

Fixed by the exact-diff pass (expected: `go/internal/web/properties/apartment_update.go`, `apartment_update_test.go`, maybe `apartment_create.go` for a shared helper).
