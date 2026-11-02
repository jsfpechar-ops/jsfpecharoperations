# 0833 report

Status: blocked (executor checkpoint at 25 tool calls). Done: steps 1 to 3 code, steps 1 and 2 tests. Left: step 3 tests, step 4, step 5.

## Files changed
- App/app/routes/signup.py: `_workspace_from_email` helper; blank workspace derived from e-mail.
- App/app/templates/signup.html: workspace input block removed.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `signup.workspace` and `signup.workspace_ph` removed (grep: no other use).
- App/tests/test_signup.py: blank-workspace cases now expect success; derivation test added.
- App/app/booking_site.py: `DEFAULT_CHECKOUT_HOUR = 11`.
- App/app/routes/admin.py: default 15/11 hours on property create; step 3 guest-link send on manual stay create.
- App/tests/test_calmer_forms.py: default-hours test.

## Commands (last lines)
- `pytest tests/test_signup.py -q` (after step 1): `42 passed in 3.81s`
- `pytest tests/test_signup.py tests/test_calmer_forms.py -q --tb=short -x`: `51 passed in 4.00s`
- `pytest tests/test_dashboard_calendar.py -q` (regression check after step 3): `34 passed in 1.62s`
- Browser test `tests/test_signup_selection_browser.py -rs`: NOT RUN. Playwright is not installed in App/.venv.

## Deviations
- Step 1: "plus-tag" read literally as "+" turned into a space, so `jan+booking@x` gives "jan booking" (tag kept).
- Step 2: the property create form posts no check-in/check-out hours, so the "creating with 14/10 keeps 14/10" half cannot be tested through POST /apartments. Only the 15/11 default is tested. The guard (`in (None, "")`) is unchanged in behaviour.
- Step 3: language follows the resend route rule, `claim row lang or "cs"`. A brand-new stay has no claim row yet, so the mail goes out in Czech unless the rule is changed.
- Step 3 tests (a)(b)(c) not written yet. Code is committed as `0833 step 3`.
- Steps 4 and 5 not started.

## Questions
- Owner: keep "+" as a space in the derived name, or drop the tag?
- Owner: for a brand-new stay, should the guest mail default to Czech (`cs`, the resend rule) or English?

## Owner steps left
- Run the browser test `tests/test_signup_selection_browser.py -rs` in CI or locally with Playwright (0 skipped required).
- Decide the two questions above.
