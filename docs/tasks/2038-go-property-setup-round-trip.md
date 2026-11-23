# 2038: Verify property setup saves and isolate setup friction

Status: todo
Depends on: staging SHA from 2037 step 1, #1276 and #1277 present on candidate | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2038-go-property-setup-round-trip
Executor: Haiku 5.5 | Tier: A | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Walk the Go property setup on a disposable fixture and prove each choice survives reopening. Capture the smallest host UI changes needed to make setup easier.

## 2. Context

The audit successfully created a property and used manual calendar setup. It stopped at Police reporting without a test credential fixture. Wizard save code (#1276) and guest-pay create/update (#1277) are already on main. Recheck acceptance before opening another port task. The Go default derives the police short name from the UbyPort login suffix, preserves explicit input, and uses the operator email as the default contact. The mobile review showed a large address form, while Go already has a RÚIAN suggestion endpoint. A follow-up typed Vinohradská at 390 px. The existing lookup answered 200 with zero suggestions. The address-specific follow-up is [2039](2039-go-address-lookup-staging.md).

Exact anchors: `func applyPoliceDefaults(p apartmentPayload, operatorEmail string) []column {` in `go/internal/web/properties/apartment_create.go`; `validation.MarkFromWSUser(p.text["uby_ws_user"])`; `func TestApartmentUpdateWizardSteps(t *testing.T) {`; and `func TestStayFeeGuestPaySwitchOff(t *testing.T) {`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/2038-report.md` | new | Step, submitted values by category, redirect, persisted result and screenshots. |

Read only: `go/internal/web/properties/apartment_create.go`, `go/internal/web/properties/apartment_update.go`, `go/internal/web/properties/apartment_update_wizard.go`, `go/internal/web/properties/apartment_update_wizard_steps.go`, `go/internal/web/properties/apartment_update_wizard_steps_test.go`, `go/internal/web/properties/stay_fee_guest_pay.go`, `go/internal/web/properties/stay_fee_guest_pay_test.go`, `go/internal/web/properties/ruian_suggest.go`, `go/internal/web/properties/apartmentnew/apartment_new.tmpl`, `docs/design/design-system.md` and the host forms sections in `docs/design/MASTER.md`.

## 4. Steps

1. Open Add property at both widths. Create one disposable property with a synthetic operator. Use the existing address fields or lookup if it is working. Verify manual submission still works. Expected: one property to complete the remaining setup checks. Use 2039 for address lookup.
2. Walk calendar save and manual skip separately on disposable fixtures. Use a harmless staging-owned iCal fixture. At the police step use owner-provisioned mock/test details in the permitted environment. Leave the short name and contact empty once, save, reopen and verify derived values by presence/match only. Repeat with an explicit short name and confirm it persists. Never submit a real filing in this setup check.
3. Follow the actual wizard steps for guest link, stay fee and lock. Change one synthetic option per save, check correct next step, reopen and verify persistence. Exercise the no-lock path or use a mock lock fixture. Confirm adjacent fields survive and a retry doesn't duplicate records. Expected: per-step readback and clear, localized errors or explicit skipped cases.
4. On the candidate containing #1277, use the supported create path carrying the guest-pay block and an existing property's update form with the stay-fee feature on. Reopen both and check configured rails/default values persisted. Repeat with the feature off and check its fields have no write effect. Exercise ordinary property update and non-destructive visible small POSTs. For a known unsupported branch require the localized “not saved here” redirect or branded 404 and proof no unintended write occurred.
5. In the report describe 390/768/1280 layout. Verify one primary action and clear escape/optional steps. If address lookup works but is hard to find, define its exact label and location with manual entry behind a secondary control for a dedicated UX brief. Record whether the dashboard calendar causes the Today list to fall below the initial view with many properties. Do not tie a dashboard layout redesign to this property verification.

## 5. Do not touch

Application code, real UbyPort, payment rails with real data, lock hardware, requirement to keep identifiers for filing, or feature flags outside the owner-controlled staging profile. Do not print the PIN, operator email or police credential strings.

## 6. Commands

- From `go/`, using dedicated preconfigured Postgres, `go test ./internal/web/properties -run 'TestApartmentUpdateWizardSteps|TestGuestPayValuesRails|TestStayFeeGuestPaySwitchOff' -count=1 -v 2>&1 | tail -30`. Expect executed tests with evidence of the DB case.
- Chromium on the matching staging SHA. EN/CS at 390/768/1280 px for touched or reported host screens. Record form, resulting step and reopened state in the report.

## 7. Acceptance

- [ ] Calendar, police defaults, guest link, fee and door lock each have proven save/advance, skip or an explicit reason blocked.
- [ ] Guest-pay create/update readbacks pass on the merged build with the switch on and the switch-off case is safe.
- [ ] Property small POSTs have a successful or gracefully refused result and no unexpected writes.
- [ ] Manual address entry and the police short-name default are verified. The result references 2039 for address automation.

## 8. Stop and ask

Stop if an external calendar, police-test account, lock, test database or guest-pay activation is unavailable for its check. Continue independent checks and report which cases require owner fixtures. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2038-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

Wizard inputs, scoped writes and any touched Go properties code in a later fix. Review the screenshots from each reported setup screen.

## Owner steps

1. Point the auditor to the candidate deployed under 2037.
2. Confirm mock/test police and lock settings. Provide the synthetic fixture, test calendar and clean property for create/update, without sending credentials through chat.
3. Enable the existing stay-fee guest-pay workflow in the isolated profile for its acceptance window. Hand back any failed readback with the exact step and screenshots.