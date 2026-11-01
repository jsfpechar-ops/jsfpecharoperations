# 0491 report

Status: blocked

## Files changed
- App/app/routes/signup.py (step 1: verify redirects to `/`)
- App/app/templates/onboarding.html (step 2: Předplatné card removed)
- App/app/routes/onboarding.py (step 3: `signup_selection` context and import removed)
- App/app/templating.py (step 4: `SECURITY_PROMPT_DELAY_DAYS = 7`, `timedelta` import, delay check in `_security_prompt.prompt()`)
- App/tests/test_signup_selection.py (step 5: two redirect assertions `/onboarding` to `/`)
- App/tests/test_security_prompt_delay.py (step 6, new: no pop-up at 0 days, pop-up at 8 days; 2 passed)

## Commands
- `pytest tests/test_signup_selection.py tests/test_security_prompt_delay.py tests/test_passkeys.py tests/test_onboarding*.py tests/test_setup_banner.py tests/test_signup*.py tests/test_two_factor_*.py -q --tb=short -x`
  Last lines: `1 failed, 178 passed, 57 skipped in 79.16s`
  Failure: `tests/test_signup_selection_browser.py::test_signup_and_onboarding_review_fit_without_js[False-360-en]`, line 67 `assert review.is_visible()`. The locator is `.ui-section` containing `a[href="/predplatne"]`, the card removed in step 2.
- Browser geometry and guardrails command (brief §6, second command): not run, blocked by the failure above.
- `python3 scripts/context_lint.py`: not run.
- 390 px screenshot of `/onboarding`: not taken. The local staging signup flow was not started.

## Checked
- `/signup/verify` path: `test_signup_selection.py` passes with `/` as the redirect.
- The security pop-up delay: `test_security_prompt_delay.py` passes. Before step 4 the 8-day case failed, so the test does exercise the change.

## Deviations
Done: steps 1 to 6. Left: §6 browser run (0 skipped), context lint, 390 px screenshot, and the owner's staging check.

## Questions
1. `test_signup_selection_browser.py::test_signup_and_onboarding_review_fit_without_js` asserts the removed card. Should I update that test to expect the card gone (it is outside §3, so I did not edit it), or should the card stay?
2. The first §6 run reported 57 skipped. The brief requires 0 skipped for browser tests. Needs a check of why the browser tests skip (probably a missing browser or environment flag) before the run is green.

## Owner steps left
- Answer question 1, then the executor continues from the §6 browser run.
