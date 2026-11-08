# 1010 report: required stars

Status: blocked
Branch: claude/required-stars (local only, not pushed)
Done: steps 1 to 2. Left: steps 3 (test file fails, see Questions), 4, 5, 6.

## Files changed (committed)

- `App/app/templates/_property_editor.html` (step 1): `text_field` macro takes `required`; stars and `aria-required` on IDUB, login, facility abbreviation, facility name; password star plus `aria-required` only when no password is stored. No HTML `required` on police fields.
- `App/app/templates/_property_calendars.html`, `setup_wizard/calendar.html`, `setup_wizard/property.html` (ICO), `setup_wizard/police.html`, `setup_wizard/_layout.html`, `_stay_fee_fields.html` (step 2): stars per brief section 2; legend shown on the wizard calendar step.

## Commits

- `9a6dea7c` 1010 step 1
- `e4487e0e` 1010 step 2

## Test results

- Step 1: `tests/test_0952_lock_section.py tests/test_property_address_required.py`: `12 passed in 3.49s`
- Step 2: `tests/test_wizard_old_look_0953.py tests/test_calendar_platform_required.py tests/test_stay_fee.py`: `69 passed in 2.83s`
- Step 3: `tests/test_required_stars.py`: FAILED (`test_every_required_control_has_a_star`). Flagged, both real `required` controls with no star, not in the brief's table:
  - `_property_editor.html`: `permalink_pin` (line 229, `required`)
  - `guest_form_admin.html`: `reveal-reason` (line 61-62, `required`)
- Step 4 and the browser runs, layout lint and `context_lint`: not run (stopped at step 3 per brief section 8).
- Skipped counts: not measured.

## Screenshots (step 5)

None taken. Step 5 not reached.

## Deviations

- Step 3 test file `App/tests/test_required_stars.py` is written but not committed (it is red).
- Did not add the two flagged ids to `ALLOW` (brief forbids it without an owner decision).

## Questions for owner

1. `permalink_pin` (guest link PIN) and `reveal-reason` (identity reveal reason) are required in HTML but have no star. Should they get a star (brief amendment), or be allowed unstarred in `ALLOW` with a reason?
2. The street has no star because the server and test 0953 treat it as optional. Should it become required (separate validation brief)?
3. Door-code time stars show while door codes are off (kept, pinned by `test_ttlock_setup_0954_browser.py`). Hide them while off?

## Owner steps left

- Decide questions 1 to 3, then the orchestrator issues a follow-up brief to finish steps 3 to 6.
