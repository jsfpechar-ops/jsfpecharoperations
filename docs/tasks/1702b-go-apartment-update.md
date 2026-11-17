# 1702b: Go property settings 3b: update property settings (POST /apartments/{id})

Status: todo — scoped (split out of 1702 by its exact-diff pass, 2026-11-17). Executable only after its own exact-diff pass: sidecars in `docs/tasks/1702b-files/`, anchors and sha256 table, written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1702 | Base commit: current tip of the working branch | Branch: task/1702b-go-apartment-update
Executor: Haiku 5.5 | Fits one session only if split again: the exact-diff pass decides (likely 1702b plain save, 1702c wizard steps and police-letter test)
Tier: A (exact files only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702b step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1702b step'`.

## 1. Objective

Port `apartment_update` (`App/app/routes/admin.py` 2535-2601) with `_save_apartment_form` (2791-3046) and its helpers (`_property_hour_changes`, `_with_lock_tab_hours`, `_lock_section_refusal`, `_wizard_police_format_errors`, `_setup_after_save`, `_refuse_apartment_save`, `refuse_fee_save` 2404-2498), as Python behaves today. It writes police data: a wrong write becomes a wrong police submission (rule 1).

## 2. Context

What the exact-diff pass of 1702 found (2026-11-17):

- Inputs: every field of the settings form of 1701/1701b (`id="property-settings-form"`, multipart, `_csrf`), the lock tab hours (`lock_checkin_hour`, `door_code_section`, `door_codes`, `door_codes_fields`), the operator selector and `operator_refresh`, the fee fields and the signature (`fee_signature_section`, `signature_drawn`; `_signature_payload`), `setup_step` (wizard), `fee_return_to`, `return_to`, the police-letter ticks (`police_letter.confirmed_fields`).
- Outputs: the `apartment` row, the operator's signature on `legal_entity`, audit rows, the redirect with `saved=1` or the flash naming missing report fields (`_missing_report_labels`), or a 400 re-render of the whole property page with the error lines. 1701b §8 (b) left the fee error lines (`fee_account_error`, `fee_operator_account_error`, `fee_rate_error`, `fee_link_error`, and `flash.stay_fees.operator_account_required`, `.link_invalid`) to this POST re-render.
- Outbound: the police-letter branch runs `_run_connection_test` (UbyPort, read-only login) only when the password was typed in the same save. Porting it is a new outbound request on Go: give the reason in the PR, reuse `go/internal/ubyport`, never a new client.
- Reuse, never copy: `validation.ValidateApartment` is the only validator; the address and RÚIAN checks of 1700b2/1700c (`apartmentAddressErrors`, `apartmentOperatorError`, `apartmentFormInt`), the stay fee helpers of `stayfees`, the 1701 page builder (`detailBuild`) for the re-render, `server.enter`, `server.audit`.
- Parity method (owner decision: golden scripts are allowed here because it writes filing data): `App/scripts/go_apartment_update_golden.py` seeds a throwaway database, posts through the real FastAPI app and writes `testdata/apartment_update_golden.json` (rows, audit lines, Location, re-render fragments); the Go test replays the same seed and must match. Accepted differences are listed in the report, never silently.
- 1701b readings kept: an undecryptable stored signature shows as none in Go (Python 500s); the inline `fee_return_to` copy of 1701 stays.

## 3. Files

Fixed by the exact-diff pass. Expected: `go/internal/web/properties/apartment_update*.go` (+ tests, testdata), one `go/cmd/ubyhost-web/register_web_properties_apartment_update.go` (+ test), a catalog dir of its own for new keys, `App/scripts/go_apartment_update_golden.py` and `App/tests/test_go_apartment_update_golden.py` (go-first exception 1), `docs/tasks/1702b-files/**`, `docs/tasks/1702b-report.md`. Edits of 1701 files only as exact diffs with step-0 hashes.

## 4. Steps

Written by the exact-diff pass (same shape as [1702](1702-go-apartment-update-door-codes.md)).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; anything under `App/app/`; filing code (`go/internal/ubyport`, `App/app/reporting.py`) beyond calling it.

## 6. Commands

From the exact-diff pass: `gofmt`, `go vet` and `go test` on `./internal/web/properties/... ./cmd/ubyhost-web/...` (PostgreSQL), the golden freshness test, `python3 scripts/context_lint.py`.

## 7. Acceptance

- Every changed field produces the same row and the same `audit` entry as Python for the golden seeds, also for invalid input (same error text, no partial write).
- A property that is mid-filing (`submit_state` set) cannot lose a required police field: same refusal as Python.
- `git log --oneline --grep='^1702b step'` shows one commit per step.

## 8. Stop and ask

An anchor not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3; a new column, retention line or outbound request beyond the connection test; a test skip.

## 9. Report

`docs/tasks/1702b-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots of the re-render (host page, rule 10), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant; the switch is brief 1705.
- **Rollback:** Revert the PR.

## Owner steps

None.
