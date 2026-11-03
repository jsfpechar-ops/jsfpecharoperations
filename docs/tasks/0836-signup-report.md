# 0836 report: signup box becomes an unticked marketing opt-in

Status: review (Command 2 not green: pre-existing failure, see Deviations)

## Files changed (commits, not pushed)
- 0836 step 1: `App/app/templates/signup.html` (field `marketing_opt_in`, new label key)
- 0836 step 2: `App/app/host_i18n.py` (EN and CS keys renamed, new text)
- 0836 step 3: `App/app/host_vi_i18n.py` (VI key renamed, new text)
- 0836 step 4: `App/app/routes/signup.py` (reads `marketing_opt_in`, passes `not marketing_opt_in`)
- 0836 step 5: `App/app/signup.py` (comment), `App/app/lifecycle_mail.py` (docstring)
- 0836 step 6: `App/tests/test_signup.py` (helper, assertions, three tests)
- 0836 step 7: `docs/UbyHost_workplan/04_legal_positions.md`, `docs/context/decisions.md`
- 0836 step 8: `docs/tasks/screenshots-0836/` (two 390 px PNGs)

## Commands (last 5 lines)
1. `pytest tests/test_signup.py tests/test_signup_selection.py tests/test_meta_capi.py tests/test_lifecycle_mail.py`: `97 passed in 6.50s`
2. `pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py`: `3 failed, 11 passed`. Failures in `tests/test_host_i18n.py` (`no such table: apartment`). Same 3 failures on base commit 0386de0^, so not caused by this change.
3. `pytest tests/test_signup_selection_browser.py -rs`: `16 passed in 23.78s`, no skipped lines.
4. `python3 scripts/context_lint.py`: `context lint: OK`

## Section 7
- [x] New label in EN, CS (VI string added), unticked, not required, field `marketing_opt_in`
- [x] Unticked stores `1` plus time; ticked stores `0` and NULL (test_signup)
- [x] Form error re-renders the box ticked (test_form_errors...)
- [x] grep for `onboarding_opt_out` lists only `signup.py` (register parameter, lines 496, 535-536) and `routes/signup.py:131`
- [ ] Command 2 passes (pre-existing failure, see below)
- [x] Command 3 passes, 0 skipped; Command 4 OK
- [x] Two 390 px screenshots (EN and CS) in `docs/tasks/screenshots-0836/`; both viewed: new label visible, box unticked

## Deviations
- Command 2: 3 failures in `tests/test_host_i18n.py`, identical on the base commit. Not fixed (outside the brief).
- The brief's expected grep for `opt_out\|opt_in` in `routes/signup.py` shows 3 lines, not 4: the comment line uses "opt-out" with a hyphen and does not match. Content is as specified.
- Brief section 9 asks for no push; executor.md asks for a PR. I did not push and did not open a PR. The orchestrator updates PR #729.
- Screenshots also copied to `/mnt/project-files/onboarding-speed/signup-optin-390-en.png` and `signup-optin-390-cs.png`.

## Questions
- Command 2 failure: fix the pre-existing `test_host_i18n.py` DB setup separately, or accept it for this PR?

## Owner steps left
- Push the branch and merge PR #729 with `scripts/merge-pr-on-green.sh` (owner or orchestrator).
- Lawyer to confirm the new wording (logged in decisions and legal positions).
