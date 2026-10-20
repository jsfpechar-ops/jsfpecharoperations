# 0178 report: setup checklist is a normal card

Status: review

## Files changed
- `App/app/static/host2.css`: appended the 0178 override (card padding, tokens, no tint, solid border).
- `App/app/templates/base.html`: host2.css key bumped to `-0178`.
- `App/tests/static_versions.json`: regenerated with `--write`.
- `App/tests/test_design_guardrails_browser.py`: new `test_setup_checklist_is_a_padded_card`.
- `docs/tasks/0178-screenshots/`: `apartments-1280.png`, `apartments-1280-collapsed.png`, `apartments-390.png` (property list page, not the checklist).

## Commands (last lines)
- `python3 scripts/design_lint.py`: `design lint: FAIL`, `DESIGN App/app/templates/reservations.html: T3 class not in catalog: stay-col-property-name`. Pre-existing: the class comes from 0177 (`0b940c7`), not from this change.
- `test_static_versions.py`: `3 passed, 1 warning in 0.10s`
- `test_setup_checklist_is_a_padded_card` (browser): `1 passed, 1 warning in 4.39s`. Run with `-s`, it printed `setup checklist absent ... test body not run`.
- `test_design_guardrails_browser.py` + `test_a11y_guard_browser.py` (browser, `-rs`): `9 passed, 1 warning in 114.15s`, 0 skipped.
- `0102-evidence` cleanup: ran, exit 0, no changes to clean.
- `shots.py` 1280 and 390 on `/apartments`: `2 shots, 0 with problems` and `1 shots, 0 with problems`.

## Brief section 7
- [ ] No pink or dashed block: not verified. The checklist does not render on the fixture property (see Questions).
- [ ] Heading inside padding: not verified, same reason.
- [x] Test passes: yes, but it returns early without asserting (see Deviations).
- [x] Guards pass with 0 skipped: yes (9 passed).

## Deviations
- The test returns early when `[data-setup-status]` is absent, which the brief allows. On the fixture property the checklist is absent, so the test asserts nothing today.
- Cause: `_property_overview.html` line 47 renders the checklist only when `readiness` is set and the setup wizard is not active (`setup_progress.hidden`). The fixture does not meet that.
- The 390 px screenshot is required by the executor doc but the brief asked for 1280 only. Both were taken. Neither shows the checklist.
- No PR opened: the executor doc asks for one, but pushing is not allowed in this run.

## Questions
1. Design lint fails on `reservations.html` (`stay-col-property-name`, from 0177). Fix in 0177 or a new brief? Not changed here.
2. How should the test reach the checklist? Options: a fixture property with the setup wizard hidden, or setting that state in the test. Needs owner input.
3. `docs/tasks/0179-guest-card-grid.md` is untracked in the working tree. Not mine, not committed.

## Owner steps left
- Decide on Questions 1 and 2.
- Push the branch and open the PR: `git push -u origin claude/project-thread-5hw8cf`, then open the PR against `main` (not pushed by the executor).
