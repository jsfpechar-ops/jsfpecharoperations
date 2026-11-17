# 1702e: Go property settings 3e: the setup-wizard saves (POST /apartments/{id} with setup_step)

Status: todo — scoped, **blocked on an owner question** (exact-diff pass of 1702b, 2026-11-17).
Decision 2026-11-17 (orchestrator, rule 11): the wizard save is ported to Go here, not moved to a Python path.
Depends on: 1702d | Base commit: current tip of the working branch | Branch: task/1702e-go-apartment-save-wizard
Executor: Haiku 5.5 | Tier: A

## Owner question (decide before the exact-diff pass)

The setup wizard (`/apartments/{id}/setup/<step>`, `App/app/routes/onboarding_wizard.py`, templates `setup_wizard/*.html`) is not ported to Go and is in no brief of [the plan](../plans/go-sqlite-final.md). Its forms post `setup_step` to the same `POST /apartments/{id}`, and Caddy does not re-send a POST to Python. So 1705 cannot switch `POST /apartments/{id}` while the wizard is on Python. Choose one:

1. Port the wizard step saves to Go here, including the 400 re-render of the wizard pages (`render_wizard`, `refuse_setup_save`, `_wizard_rerender`, `_lock_section_refusal`, `_setup_after_save`, `_wizard_police_format_errors`): needs the wizard pages in Go first (a new brief before this one).
2. Recommended: a small Python change gives the wizard its own save path (for example `POST /apartments/{id}/setup/save`, the same `_save_apartment_form`), so `/apartments/{id}` serves only the settings page and this brief shrinks to that move. Needs your "yes" (it changes `App/`).

## 1. Objective

After the decision: the `setup_step` branches of `_save_apartment_form` (`App/app/routes/admin.py` 2791-3046: `RETIRED_STEPS`, `_wizard_setup_step`, `_wizard_step_payload`, the property/door_lock/police/stay_fee steps) and `_setup_after_save` 2655, as Python behaves today.
