# 0180 report

Status: review

## Files changed
- `App/app/templates/reservations.html`: removed unlisted `stay-col-property-name` (line 154); now `<div class="ui-sub">`.
- `App/tests/test_design_guardrails_browser.py`: `test_setup_checklist_is_a_padded_card` now uses `configured_apartment`, seeds the setup wizard as finished (`property_setup.start` + `finish`), no early return, asserts the element exists, prints measured values.
- `docs/tasks/0180-screenshots/checklist.png` (1280 px, element screenshot).
- `docs/tasks/0180-report.md`.

## Commands (last lines)
- `python3 scripts/design_lint.py`: `design lint: OK`
- Attempt 1, `wait_for_selector` on `configured_apartment` without seeding: Timeout 5000 ms, element absent (count 0). Cause: `_property_overview.html` line 48 hides the checklist while the setup wizard is active; the fixture seeds no wizard state.
- Attempt 2 (seeded finished wizard): `1 passed`. Measured: background equals card background, border solid, heading 17 px inside.
- `pytest tests/test_design_guardrails_browser.py -q -rs` (UBYHOST_REQUIRE_BROWSER=1): `5 passed, 1 warning`, 0 skipped.
- `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`: ran, no refusal.
- `pytest tests/test_overhaul.py -q --tb=short`: `26 passed, 1 warning`.

## Checklist §7
- [x] design lint OK
- [x] checklist test measures the card (fails on absence, passes with it)
- [x] guards pass, 0 skipped

## Screenshot
White card, thin solid border, about 17 px padding, heading and status tiles in a 2-column grid. Looks right.

## Deviations
- Commit trailer: the brief asked for "Claude Sonnet 5.5"; the harness attribution says "Claude Haiku 5.5" (the model running this brief). I used the harness value.
- The test seeds the wizard as finished (brief §2 allowed the smallest seeding step); no app code changed.

## Questions
None.

## Owner steps left
None. Not pushed.
