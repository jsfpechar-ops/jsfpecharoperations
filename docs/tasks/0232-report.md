# 0232 report: workflow strip and stay tracker

Status: review
Executor: Haiku 5.5 | Branch: claude/project-thread-kbrf7w

## Files changed

- `App/app/templates/_workflow.html` (new): macros `workflow_strip` and `stay_journey_panel`.
- `App/app/templates/setup_wizard/property.html`: strip under the lede (step 2).
- `App/app/templates/dashboard.html`: strip before the empty-stays state (step 3).
- `App/app/templates/guide.html`: strip under the overview heading (step 4).
- `App/app/templates/reservation_detail.html`: tracker in the Next step panel (step 5).
- `App/app/templates/_components.html`: `progress_pill` takes `step` and shows "Step n of 5" (step 6).
- `App/app/templates/reservations.html`: passes `journey_step(progress.status)` (step 7).
- `App/tests/test_workflow_strip_0232.py` (new): 3 tests (step 8).
- `docs/tasks/0232-workflow-strip-and-tracker.md`: Status line set to `review`.
- `docs/tasks/0232-report.md` (new): this report.

## Commands (last 5 lines)

- Step 5, `tests/test_guest_link_window_0231.py`:
  `4 passed, 1 warning in 1.63s`
- Step 8, `tests/test_workflow_strip_0232.py`:
  `3 passed, 1 warning in 1.50s`
- §6 set (`test_workflow_strip_0232`, `test_guest_link_window_0231`, `test_workflow_0230`, `test_onboarding_wizard_survival`):
  `36 passed, 1 warning in 4.23s`

## §7 acceptance

- [x] The 3 new tests pass; the named older tests still pass.

## Deviations

None. Every anchor matched exactly once. No test needed `db.init_db()`.

## Questions

None.

## Owner steps left

None.
