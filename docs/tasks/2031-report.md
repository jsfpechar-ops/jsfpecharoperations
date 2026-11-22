# 2031 report (go wizard setup steps save)

Status: review

## Files changed

- `go/internal/web/properties/apartment_update_wizard_steps.go` — wizardSetupStep, wizardStepPayload, apartmentWizardStepSave
- `go/internal/web/properties/apartment_update_wizard_steps_test.go` — redirect steps + payload table
- `go/internal/web/properties/apartment_update.go` — not-ported narrowed; route calendar/guest_link
- `go/internal/web/properties/apartment_update_wizard.go` — police-only else branch
- `go/internal/web/properties/apartment_update_test.go` — not-ported cases
- `go/internal/web/onboarding/wizard_after_save.go` — stay_fee, door_lock, automation marks
- `go/internal/web/onboarding/wizard_save_export.go` — AutomationTimingValues, WizardSetupStep
- `docs/context/known-issues-recent.md` — K-2029 wording (2031 landed)

## Commands (last lines)

```
cd go && go test ./internal/web/properties/... → ok 0.070s (DB skipped without URL)
gofmt -l → (clean after gofmt -w)
python3 scripts/context_lint.py → ok
```

## §7

- [x] calendar/guest_link write only their columns (none) and redirect via AfterSave
- [x] stay_fee, door_lock, automation re-render saves still interim redirect (named here)
- [x] No template/screenshots

## Deviations

Known-issue edit in `known-issues-recent.md` (2029 wizard line lived there, not `known-issues.md`).

## Questions

None.