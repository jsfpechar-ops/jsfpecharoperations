# 0491 report

Status: review

## Files changed
- App/app/routes/signup.py (step 1: verify redirects to `/`)
- App/app/templates/onboarding.html (step 2: Předplatné card removed)
- App/app/routes/onboarding.py (step 3: `signup_selection` context and import removed)
- App/app/templating.py (step 4: `SECURITY_PROMPT_DELAY_DAYS = 7`, delay check in `_security_prompt.prompt()`)
- App/tests/test_signup_selection.py (step 5: two redirect assertions to `/`)
- App/tests/test_security_prompt_delay.py (step 6, new: 0 days no pop-up, 8 days pop-up)
- App/tests/test_signup_selection_browser.py (owner-approved extra: the card assertion now checks count() == 0; the billing click removed)
- docs/tasks/screenshots-0491/onboarding-390.png

## Commands
- §6 set (`test_signup_selection.py test_security_prompt_delay.py test_passkeys.py test_onboarding*.py test_setup_banner.py test_signup*.py test_two_factor_*.py`) with `UBYHOST_REQUIRE_BROWSER=1 ... -rs`: `276 passed in 242.53s`, 0 skipped.
- `tests/test_host_geometry.py tests/test_design_guardrails_browser.py` with `UBYHOST_REQUIRE_BROWSER=1 -rs`: `13 passed in 58.88s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (warning only: App/ commits after last status.md update).

Skip cause: the 57 earlier skips were `browser not required`, gated by `UBYHOST_REQUIRE_BROWSER`. Set to 1 for the run.

## Screenshot and flow
Staging on 127.0.0.1:8091 (stopped after). Signed up at /signup?plan=max&interval=year&apts=3, verify link from the console mail, submit on the verify form. Landed on `/` with no security pop-up. `/onboarding?lang=cs`: no `.ui-section` with `/predplatne` (count 0). One `/predplatne` link remains in the main content, from the welcome checklist, not the removed card. Screenshot taken at 390 px, full page.

## Deviations
- Step 5/6 and the browser test used `login_as(..., follow_redirects=False)`, as in test_passkeys.py. The `url=` form returned no pop-up even at 8 days.
- The browser test change was approved by the coordinator (Q1). Nothing else in it changed.

## Questions
None open.

## Owner steps left
- Review and merge through `scripts/merge-pr-on-green.sh`. No push or PR was made by the executor.
