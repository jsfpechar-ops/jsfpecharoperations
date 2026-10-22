# 0234 report: door lock as one question

Status: review

## Files changed

- `App/app/property_setup.py`: `not_needed` mark (steps 1 to 5), commit `0234 step 1-5`
- `App/app/routes/onboarding_wizard.py`: `none` action and mark (step 6)
- `App/app/routes/admin.py`: `not_needed` counts as answered (step 7)
- `App/app/templates/setup_wizard/door_lock.html`: question with two choices (step 8), replaced as the brief gives it
- `App/app/templates/setup_wizard/done.html`: summary status (step 9)
- `App/app/templates/_property_overview.html`: overview status (step 10)
- `App/app/templates/setup_wizard/_layout.html`: "(optional)" suffix on the meta line (step 11)
- `App/tests/test_lock_question_0234.py`: created, 3 tests (step 12)
- `docs/tasks/0234-report.md`: this report
- `docs/tasks/0234-lock-question.md`: Status line set to `review`

## Commands (last 5 lines)

1. Steps 1 to 5: `cd App && .venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py -q --tb=short -x 2>&1 | tail -8`
   `24 passed, 1 warning in 2.82s`
2. Step 8: `cd App && .venv/bin/python -m pytest tests/test_smart_locks_page.py tests/test_onboarding_wizard_survival.py -q --tb=short -x 2>&1 | tail -30`
   `40 passed, 1 warning in 4.02s`
3. Step 12: `cd App && .venv/bin/python -m pytest tests/test_lock_question_0234.py -q --tb=short -x 2>&1 | tail -10`
   `3 passed, 1 warning in 0.08s`
4. Brief §6: `cd App && .venv/bin/python -m pytest tests/test_lock_question_0234.py tests/test_onboarding_wizard_survival.py tests/test_smart_locks_page.py tests/test_onboarding_why_0206.py -q --tb=short 2>&1 | tail -15`
   `45 passed, 1 warning in 4.35s`

## Section 7 (acceptance)

- [x] The 3 new tests pass; the named older tests still pass (45 passed in command 4).
- [ ] Without a lock, two big choices and no "Skip this step" button. Not checked in a browser (browser tests are out of scope for this brief). By reading the template, the no-lock branch has no "Skip this step" text.

## Deviations

- `tests/test_property_setup*.py` matched no file, so it was dropped from the command (§6).
- No existing test expectation changed. The allowed `skipped` to `not_needed` edit and the "Skip this step" edit were not needed.
- Step 6 and step 7 were each committed alone, as the brief's commit lines say. Steps 1 to 5 went in one commit.

## Questions

None.

## Owner steps left

None.
