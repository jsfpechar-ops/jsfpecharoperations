# 2031: Go port of the other wizard setup_step saves (calendar, guest_link, stay_fee, door_lock, automation) and wizard return_to

Status: todo
Depends on: 2029 | Base commit: main after 2029 merges | Branch: task/2031-go-wizard-steps
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (hand over at 25 calls per executor.md; likely two sessions, one per half)

## 1. Objective

`POST /apartments/{id}` in Go handles only `setup_step` property and police. Any other step, and a save without `setup_step` whose `return_to` is under `/apartments/{id}/setup/`, hits the interim "not saved here" redirect after 2029. Port them so the wizard behaves as Python.

## 2. Context

Python: `App/app/routes/admin.py` `_wizard_setup_step` (1685), `_wizard_step_payload` (1692, only the columns a step owns), the wizard advance logic from about 2660 (`property_setup.mark`, step resolved rules), the save route from 2801 (`RETIRED_STEPS`, `owns_shared_hours`, door_lock hour handling 2817-2833). Steps list: `property_setup.STEPS`, `STEP_FIELDS`. Go: `apartmentUpdateNotPorted` and `apartmentWizardReturn` in `go/internal/web/properties/apartment_update.go` (226-250); existing wizard code `apartment_update_wizard_test.go`, `apartment_update_wizard_after_test.go`; `onboarding.RetiredSteps`, `onboarding.WizardURL`. Do the half that needs no re-render first: saves that redirect (calendar and guest_link are written by their own routes; check which steps really post here with `grep -n 'setup_step' App/app/templates/*.html`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_update.go` | edit | accept the steps; per-step payload; remove the not-ported cases for them |
| `go/internal/web/properties/apartment_update_wizard_steps.go` | new | `wizardStepPayload(step, r)` and the step-resolved marks, ported from admin.py |
| `go/internal/web/properties/apartment_update_wizard_steps_test.go` | new | per step: columns written, step marked, redirect target, unresolved step still redirects with the same flash as Python |
| `go/internal/web/properties/apartment_update_test.go` | edit | drop the "setup_step other than property or police" not-ported case |
| `docs/context/known-issues.md` | edit | remove the 2029 wizard lines |

No other file may change. A step whose Python path re-renders HTML with errors stays on the interim redirect; list each such step in the report as a follow-up.

## 4. Steps

1. For each step in `property_setup.STEPS` other than property and police, read `_wizard_step_payload` and write the Go payload; record Python outputs for 3 inputs per step in the test table.
2. Port the advance/mark rules and the shared-hours rule for door_lock.
3. Port the wizard `return_to` branch (no `setup_step`): same redirect as Python's `_back(return_to)`.
4. Run §6; commit `2031 step k` each step.

## 5. Do not touch

Templates, CSS, `App/`, the interim flash key (still used by the re-render sites), UbyPort. No new dependency.

## 6. Commands

From `go/`: `go test ./internal/web/properties/... 2>&1 | tail -30` (DB tests skip without `UBYHOST_TEST_DATABASE_URL`; say so). Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Each ported step writes exactly its own columns and marks the same step state as Python for the recorded cases.
- [ ] Steps left on the interim redirect are named in the report.
- [ ] No template change, so no screenshots.

## 8. Stop and ask

An excerpt is not found, a step's Python path is unclear, a test fails twice, a file outside §3 needs a change, 25 calls reached. Never push or merge.

## 9. Report

`docs/tasks/2031-report.md`, 600 tokens at most.

## Risk list (for the reviewer)

Step marks (`property_setup.mark`) and the shared-hours rule: they decide whether a host finishes onboarding.

## Owner steps

1. Open the draft PR, wait for CI green, mark ready.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. After deploy, walk the setup wizard of a test property through each step and save. Expect each step to advance, never a "not saved here" message.
