# 1702e: Go property settings 3e: the setup-wizard saves (POST /apartments/{id} with setup_step)

Status: replaced by 1702e1, 1702e2 and 1702e3 (exact-diff pass 2026-11-17 split it: [1702e1](1702e1-go-wizard-refused-step-page.md) ready, [1702e2](1702e2-go-apartment-save-wizard-step.md) and [1702e3](1702e3-go-apartment-save-wizard-after.md) scoped, each needs its exact-diff pass after 1702d2).
Decision 2026-11-17 (owner/orchestrator, rule 11): option 1 of the former owner question: the wizard step saves are ported to Go, not moved to a Python path. The wizard pages themselves are already Go (briefs 1599-1602: `go/internal/web/onboarding/wizard*.go`, dormant), so no page-port brief is needed.
Depends on: 1702d2 | Base commit: current tip of the working branch | Branch: task/1702e-go-apartment-save-wizard
Executor: Haiku 5.5 | Tier: A

Nothing to run here. 1702e1: `onboarding.RenderSetupPage`, the wizard step drawn again with a save's notice, errors and draft (onboarding package only; independent of 1702d2). 1702e2: the `setup_step` branches of `_save_apartment_form` and their 400 re-renders. 1702e3: `_setup_after_save` and a `return_to` inside the wizard.
