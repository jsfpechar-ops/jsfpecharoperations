# Self-service lifecycle implementation report

Status: review; draft only, not ready to launch.

Owner authorized implementation with Sol on 2026-10-27. This is the backend
lifecycle slice of the self-service plan in draft PR #535.

## Implemented

- Verification POST activates the account and creates its initial trial in one
  short database transaction when billing is enabled. A failed trial insert
  rolls activation back; a repeated verification cannot restart the clock.
- Thirty calendar days, including activation day, use the configured timezone
  (Prague by default). The end date is inclusive to match existing trial finish
  and billing period conventions. Existing running trial dates are unchanged.
- Recovery of an existing pending billing row anchors to email verification;
  no seven-day delay, created-at fallback, or UbyPort-triggered start remains.
  One conditional write sets status and dates together. Recovery never creates
  billing accounts for legacy hosts.
- New orders cannot claim founder slots or quote a discount because slots are
  available. Existing confirmed founder flags remain honored.
- Added focused rollback/retry, calendar boundary, legacy, no-order, cancellation,
  and founder coverage. Updated existing trial expectations and billing test map.

## Validation and limits

The managed environment cannot start: "managed network requirements require
sandbox enforcement". No application, lint, security, billing or browser tests
were run. Files were inspected and edited through the connected GitHub tools.
No dependencies, schema, guest filing behavior, deployment or feature flags
were changed.

Required verification after workspace recovery: focused
test_billing_trial.py and test_billing_self_service.py, existing billing tests,
signup/auth/security test-map rows and context lint. Run browser/geometry tests
with zero skips and inspect 390 px screenshots for any subsequent UI edits.

## Remaining delivery

This PR does not implement the scalable operator dashboard, persistent pricing
preselection, optional passkey onboarding handoff, full recurring-worker and
bank-reconciliation validation, or launch readiness. Public and in-app/help/legal
trial copy must be reconciled with the activation rule before feature enablement;
pricing-copy work is separate in draft PR #536. The existing root signup redirect
and passkey/wizard journey still require end-to-end implementation and evidence.
Legacy free accounts remain free through absence of a billing_account row.
Existing cancellation and period transition logic is retained.
