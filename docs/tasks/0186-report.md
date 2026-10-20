# 0186 report

Status: blocked

## Files changed
- App/tests/test_onboarding_followup_browser.py (step 1, commit "0186 step 1"): the before/after colour now reads the first td; the final check asserts all td share one colour and it differs from the initial one.

## Commands
- Step 2 grep (`tr[data-href|ui-row` in browser tests): found test_host_stay_actions_browser.py and test_onboarding_followup_browser.py. Neither has transparent-cell or row-gap checks needing change. No edits there.
- Step 3: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_onboarding_followup_browser.py tests/test_host_stay_actions_browser.py -q -rs --tb=line`
  last lines: `4 failed, 13 passed, 1 warning in 65.52s`. All 4 failures are `test_onboarding_followup_browser.py:52`: `assert 'rgba(0, 0, 0, 0)' != 'rgba(0, 0, 0, 0)'`. Skipped: 0.
- Step 4: 0102-evidence cleanup done; `python3 scripts/context_lint.py` last line: `context lint: OK`.

## Acceptance (section 7)
- [ ] Browser files pass with 0 skipped. NOT MET: 4 failures (see above). Lint OK.

## Deviations
- Done: steps 1 to 2 and 4. Step 3 failed. Step 5 (commit) done for step 1 and this report; no push, no PR.
- The brief's premise does not match the local render: the first td is `rgba(0, 0, 0, 0)` before hover and after hover, so comparing td colours fails. The row (tr) colour does change on hover. CI's failure was on the all-transparent td check (line 53), which suggests CI sees opaque td cells. Local and CI renders disagree, or the 0181 td styling is not what the brief describes. I did not change CSS or guess a new expectation.

## Questions
- Are desktop td cells meant to be opaque (var(--surface), hover var(--surface-2)) after 0181? If yes, why is the first td transparent here, and which test should be the source of truth? If no, the test should keep the tr-based check from before this task.

## Owner steps left
- Orchestrator decides the expected td background, then a new brief or a corrected 0186 brief is needed. Nothing to deploy or merge.
