# 1700b2: Go property create (POST /apartments): handler, golden, tests

Status: blocked (needs its exact-diff pass: the Tier A writer of 2026-11-17 ran out of budget after 1700b1; this file is the scope sheet for that pass, not runnable by Haiku)
Depends on: 1700a done, 1700b1 (`go/internal/validationi18n.Localize`) | Base commit: current tip of the working branch | Branch: task/1700b2-go-apartment-create
Executor: Haiku 5.5 after the exact-diff pass | Fits one session: to be decided by that pass (split 1700b2/1700b3 if the sidecars need more than 30 tool calls)
Tier: A (writes filing data: Python golden script plus Go tests)

> **One big PR mode.** Commit each step as `1700b2 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Port `apartment_create` (`App/app/routes/admin.py` 1802-1857, `@router.post("/apartments")`) to `go/internal/web/properties`, dormant (nothing added to `UBYHOST_GO_PATHS`). A refusal re-renders the 1700a form through `RenderApartmentNew` with `loadApartmentNewChoices`; a success writes the same `apartment` row as Python and redirects to `/apartments/{id}/setup/calendar` with the `flash.apartments.created` message.

## 2. Context

Rules: 1 filing correctness first (the row holds `addr_*`, `uby_*`, `default_purpose`, `legal_entity_id`, `data_controller_entity_id`, `automation_mode`, `submit_after_hours` read by the UbyPort serializer); 2 no new personal-data field, no outbound request; 5 SQL only through the Go pgx helpers, `$n`, every query scoped by `owner_user_id IS NOT DISTINCT FROM` the workspace; no schema change; 6 the form posts `_csrf` and works without JavaScript; 11 Go first. RÚIAN suggest is 1700d, not here. Address fields are saved as typed (only `addr_zip` goes through `normalise_zip`); a `č.ev.` in `addr_house_no` is stored as Python stores it.

**Python flow to port, in order (each item: Python source, Go piece to reuse; never copy a helper that exists):**

1. `auth.require_login` → `hostweb.Login`; `_csrf` checked as the other Go POST handlers of `properties` do (find the helper with `grep -rn '_csrf' go/internal/web/properties/*.go go/internal/hostweb/*.go`).
2. `_apartment_payload(form)` (admin.py 1749): 16 `APARTMENT_TEXT_FIELDS` stripped as `_form_str`; `guest_message[:1000]`; `uby_mark.upper()`; `validation.normalise_zip`; `city_en = property_setup.guest_city(addr_obec)` (`property_setup.py` 490, plus `_GUEST_CITY_NAMES`: check for a Go twin before porting); `_form_int` ids; `_automation_timing_values` (default `manual`, hours `min(int or 24, 48)`); `permalink_window_days or 1`; `normalise_reachback_days`; `passport_photo_policy` in (`off`, `required_foreign`); `ocr_scan`; `stay_fee_routes.fee_form_values(form)` only when `stay_fee_rate_czk` was posted (`stayfee.ClampRate` exists in `go/internal/stayfee/calc.go`); `default_purpose` in `PURPOSE_CODES` else `10`; `active = 1`.
3. `operator_refresh` posted → refusal render with no errors, status 200, nothing written.
4. Checks before any write: `name_error` (blank `internal_name`); `_property_operator_error` (admin.py 404: missing, foreign or archived operator → `apartment.form.operator.add_first` when the host has no operator, else `apartment.form.operator.required`; a posted controller that is not the host's live entity → `flash.error.no_such_controller`); `_create_address_errors` (admin.py 1552: `validation.ValidateApartment` errors on the seven `_ADDRESS_ONLY_FIELDS`, first per field, plus `Street is required.`). Any error → `_refuse_apartment_create` (admin.py 1508) = `RenderApartmentNew` with `Draft`, `Prefill` (every posted copy key except the two ids; the controller id from the draft), `CopyFromID`/`CopiedFromName` only when `copy_from` is this workspace's property, `AddressErrors` passed through `validationi18n.Localize(msg, lang)`, `Status: 400`.
5. `_apply_police_defaults` (admin.py 1780): blank `uby_mark` → `validation.MarkFromWSUser`; blank `uby_contact` → the operator's `contact_email[:50]`.
6. Quirks to keep exactly: `_stay_fee_account_raw` and the guest-operator-account raw key are **dropped** on create (a copied `stay_fee_council_account` is not saved: confirm with the golden); an invalid Revolut link is set to NULL (`booking.RevolutLinkOK` exists); blank `guest_message` → the host-language text of `apartment.form.guest_message.default`; `data_controller_entity_id == legal_entity_id` → NULL; `uby_ws_password` → `db.encrypt_secret` (look for the Go twin used by `go/internal/stayfee/save.go` or `session/totp.go`) or NULL.
7. Writes, in one transaction: `INSERT INTO apartment` (with `permalink_token`/`permalink_pin` from `properties/slug.go`, `created_at`, `owner_user_id`); when the fee was posted, the dated rate row of `stay_fee_routes.record_rate_change` (`previous=0`, `stay_fee_rate_from` or today in Prague); the guest slug (`guest_slug.ensure`; Go twin in `go/internal/palette/slug.go`); `audit('apartment_created', 'id=N')`; `property_setup.start` (`{"steps": {}, "finished": false}`).

**Parity method:** golden script `App/scripts/go_apartment_create_golden.py` (pattern: `App/scripts/go_onboarding_page_golden.py`, `docs/tasks/1595-go-onboarding-checklist-page.md`) seeds a throwaway PostgreSQL with made-up hosts, posts the same forms to the real FastAPI app and writes `testdata/apartment_create_golden.json` (status, Location, the written `apartment` row minus random token/pin/slug code and timestamps, the rate row, the setup row, the refusal's error fragments). The Go test replays the seeds and posts and must match. Cases at least: valid minimal; copy_from with stay fee and council account; controller equal to operator; foreign operator; foreign controller; archived operator; no operator at all; blank name; each missing address field; invalid zip; `č.ev. 12` in `addr_house_no`; `operator_refresh`; missing `_csrf`; signed out; admin preview (owner scoping).

## 3. Files

To be fixed by the exact-diff pass (expected: `go/internal/web/properties/apartment_create.go`, its test and testdata golden, `go/cmd/ubyhost-web/register_web_properties_apartment_create.go` and test, `App/scripts/go_apartment_create_golden.py`, `App/tests/test_go_apartment_create_golden.py`, sidecars under `docs/tasks/1700b2-files/`).

## 4. Steps

None yet: the exact-diff pass writes them (sidecars, sha256 table, verified in a throwaway worktree with 0 skips) and sets `Status: todo`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; 1700a's files except through their exports; `App/app/`; filing code (`go/internal/ubyport`, `App/app/reporting.py`); the RÚIAN suggest route (1700d).

## 6. Commands

Fixed by the exact-diff pass (gofmt, vet, `go test ./internal/web/properties/... ./cmd/ubyhost-web/...` on PostgreSQL, the golden pytest).

## 7. Acceptance

Same row as Python for every golden case; a refusal re-renders with the same field errors; every query owner-scoped; `_csrf` enforced.

## 8. Stop and ask

This file is blocked: an executor stops at once and reports.

## 9. Report

`docs/tasks/1700b2-report.md`.

## Rollout wave and rollback

- **Rollout:** dormant; the switch is brief 1705.
- **Rollback:** revert the PR.

## Owner steps

None.
