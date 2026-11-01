# 0491: Calmer first screen after signup

Status: todo

## 1. Objective

After a new host confirms their e-mail, show one thing: the setup card on the Overview. Remove the saved-plan card and keep the "second login method" pop-up away during the first 7 days. Owner approved 2026-11-01 (signup review).

## 2. Context

Today `/signup/verify` sends hosts with a pricing selection to `/onboarding`, which repeats the 5 steps in full and adds a "Předplatné" card. The selection is still preselected on `/predplatne` by `billing_order.py`, so the card adds nothing. The security pop-up (`templating._security_prompt`) fires on the very first page.

## 3. Files

`App/app/routes/signup.py`, `App/app/routes/onboarding.py`, `App/app/templates/onboarding.html`, `App/app/templating.py`, `App/tests/test_signup_selection.py`, and one new test file `App/tests/test_security_prompt_delay.py`.

## 4. Steps

1. `App/app/routes/signup.py`, anchor `destination = "/onboarding" if signup_selection.for_owner(refreshed["id"]) else "/"`: replace that line with `destination = "/"`. Keep the import if the file still uses `signup_selection` elsewhere (it does at the form handlers).
2. `App/app/templates/onboarding.html`: delete from `{% if signup_selection %}` through its matching `{% endif %}` (the `ui_section` block). Nothing else.
3. `App/app/routes/onboarding.py`: delete the line `"signup_selection": signup_selection.for_owner(access.owner_id(request)),` and remove `signup_selection` from the `from .. import` line on line 13. Keep `access` if still used in the file (check with grep).
4. `App/app/templating.py`: under `_NO_SECURITY_PROMPT = (...)` add
   ```python
   SECURITY_PROMPT_DELAY_DAYS = 7  # a new self-signup host sets up first, then secures the account
   ```
   and add `timedelta` to the existing `from datetime import ...` line. In `prompt()`, directly after the `if request.url.path.startswith(_NO_SECURITY_PROMPT):` / `return None` pair and before `db.update_if`, insert:
   ```python
        signup_at = account["signup_at"] if "signup_at" in account.keys() else None
        if signup_at:
            started = datetime.fromisoformat(str(signup_at))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - started < timedelta(days=SECURITY_PROMPT_DELAY_DAYS):
                return None
   ```
   If `account` has no `.keys()` (check its type where `_security_prompt` is called, `templating.py` line ~672), stop and ask.
5. `App/tests/test_signup_selection.py`: the two assertions that expect `"/onboarding"` as the verify redirect (around lines 81 and 134) now expect `"/"`. Nothing else.
6. New `App/tests/test_security_prompt_delay.py`: copy the fixture and login pattern from `App/tests/test_passkeys.py` around line 125–135 (open only that range). Two tests: an account with `signup_at` = now gets no pop-up on `/` and keeps `two_factor_prompted_at` NULL; the same account with `signup_at` 8 days ago gets the pop-up (`security-prompt-title` in the HTML) and `two_factor_prompted_at` is set.

## 5. Do not touch

`onboarding.py` (the module), `_components.html`, `base.html`, `signup_selection.py`, `billing_order.py`, any CSS.

## 6. Commands

From `App/`:
`.venv/bin/python -m pytest tests/test_signup_selection.py tests/test_security_prompt_delay.py tests/test_passkeys.py tests/test_onboarding*.py tests/test_setup_banner.py tests/test_signup*.py tests/test_two_factor_*.py -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/context_lint.py | tail -3`.

## 7. Acceptance

- [ ] Verify lands on `/`; `/onboarding` has no Předplatné card; `/predplatne` still preselects the saved plan.
- [ ] No security pop-up in the first 7 days after self-signup; unchanged for operator-created accounts (`signup_at` NULL).
- [ ] §6 green, 0 skipped. One 390 px screenshot of `/onboarding` in `docs/tasks/screenshots-0491/`.

## 8. Stop and ask

An anchor is missing, `account` is not a row with `.keys()`, or a test outside the changed lines fails.

## 9. Report

`docs/tasks/0491-report.md`.
