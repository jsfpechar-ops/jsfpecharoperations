# 1702e3: Go property settings 3e3: after a wizard save (_setup_after_save)

Status: todo — scoped (split out of 1702e by its exact-diff pass, 2026-11-17). Needs its own exact-diff pass (sidecars in `docs/tasks/1702e3-files/`, step-0 hashes, sha256 table) after 1702e2.
Decision 2026-11-17 (owner/orchestrator, rule 11): the wizard saves are ported to Go.
Depends on: 1702e2 | Base commit: current tip of the working branch | Branch: task/1702e3-go-apartment-save-wizard-after
Executor: Haiku 5.5 | Tier: A

> **One big PR mode.** Commit each step as `1702e3 step k`; never branch, push or open a PR.

## 1. Objective

Replace the seam `"a return_to inside the setup wizard"` in `apartmentUpdateNotPorted` with `_setup_after_save` (`App/app/routes/admin.py` 2655-2737), called where Python calls it (2576, after the fee return): a `return_to` under `/apartments/{id}/setup/` decides where a successful save goes.

## 2. Context (found by the 1702e exact-diff pass; not built yet)

- Finished or hidden setup, or a `setup_step` that is not a step: back to `return_to` with the saved message (2671-2676).
- Marks: police with `automation_mode` posted marks `automation` done; `property` done when `property_details_complete`; `police` done when the report is complete. The stay_fee/door_lock/automation branches are unreachable (retired steps never get here). Go: `onboarding.Mark`, `Load`, `LegacyState`, `Current`, `Finish`, `StepStatus`, `PropertyDetailsComplete` (grep `go/internal/web/onboarding/setup.go`), the facts of `_setup_guide_bundle` (grep `Facts`, `wizardContext` loads them; export a loader if needed: that is an `onboarding` change).
- `return_to` ending `/done`: unresolved -> `303` to the current guide URL (else `/setup/police`); resolved -> `Finish` and `/setup/done` with `flash.setup.complete`.
- A step not done/skipped/not_needed: `onboarding.RenderSetupPage(..., step, SetupPage{Notice: ...})` with status 200 (1702e1): `flash.apartments.saved` with the missing report labels (`_missing_report_labels`, already in Go for the settings save), else with `wizard.step.<step>`; `door_lock` (`flash.error.door_code_lock`) is unreachable.
- Otherwise back to `return_to` with the saved message.
- A post without `setup_step` whose `return_to` is inside the wizard (an old page, the fee refusal at admin.py 2442 rendering the retired `stay_fee` page, which has no Go template: decide in the exact-diff pass; keep `notPorted` for it rather than a 501).
- Keys: `flash.setup.complete`, `flash.apartments.saved`: check which Go catalog has them (wizardtext has `flash.setup.complete`); add missing ones to `apartmentupdate/i18n_keys.txt` and regenerate with `App/scripts/go_host_i18n.py`.
- Tests: Go-only, hand-written expected output in `apartment_update_test.go`: property saved complete -> next step; police complete -> marks; `/done` unresolved -> guide URL; `/done` resolved -> finish + flash; incomplete step -> 200 page with the notice; finished setup -> plain back.
- After 1702e3, 1703 can start; 1705 switches `POST /apartments/{id}` together with the wizard paths (1599-1602 are dormant too).

## 3. Files

Fixed by the exact-diff pass.
