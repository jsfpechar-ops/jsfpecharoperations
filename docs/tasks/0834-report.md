# 0834 report (executor: Haiku 5.5)

Status: review. Branch `claude/project-thread-mb7ww2`. Not pushed (brief §0 and §9).

## Files changed
- `App/app/routes/admin.py`: step 1 revert (5 lines and the `booking_site` import removed); step 2 `import logging`, `log` logger, and the claim-mail rule in `reservation_create` (calendar, blank count, and start_claim errors excluded).
- `App/app/booking_site.py`: `DEFAULT_CHECKOUT_HOUR` removed.
- `App/tests/test_calmer_forms.py`: `test_a_new_property_starts_at_15_and_11` removed; the claim-mail test replaced by 4 tests (step 3).
- `App/app/routes/signup.py`: plus-tag dropped from the derived workspace name.
- `App/tests/test_signup.py`: one assertion changed; `test_a_plus_tag_is_left_out_of_the_workspace_name` added.
- `docs/tasks/0833-faster-onboarding.md`: one line added.
- `docs/tasks/0834-onboarding-review-fixes.md`: Status set to review.

## Commits (in order)
`0834 step 1`, `0834 step 2-3`, `0834 step 4`, `0834 step 5`, `0834 report`.

## Commands (section 6)
1. `App/`: `.venv/bin/python -m pytest tests/test_calmer_forms.py tests/test_dashboard_calendar.py -q --tb=short -x 2>&1 | tail -30`
   last lines: `48 passed in 2.67s`
2. `App/`: `.venv/bin/python -m pytest tests/test_signup.py -q --tb=short -x 2>&1 | tail -30`
   last lines: `43 passed in 3.11s`
3. repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`
   last lines: `next free: task 0835 | migration 0035` and `context lint: OK` (WARN lines are existing notices about open briefs, not errors)

## Section 7 (acceptance)
- [x] `DEFAULT_CHECKOUT_HOUR` and `booking_site` grep checks print nothing.
- [x] The four named form tests pass (run 1).
- [x] Both signup tests pass (run 2).
- [x] Both pytest commands pass with 0 failed; lint reports no errors.

## Deviations
- Step 2b anchor is at about line 3399 (brief said about 3405). It was unique, so I applied the replacement there.
- A temporary edit script was written to /tmp (not the scratchpad); it was deleted after use.
- Browser tests and screenshots not run: no template or CSS changed (brief §6).
- No PR opened: the brief says do not push and the orchestrator updates PR #729.

## Questions
None.

## Owner steps left
- Push to update PR #729: `git push origin claude/project-thread-mb7ww2`
