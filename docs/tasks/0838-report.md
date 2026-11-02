# 0838 report: guest form, 2nd person carry-over

Status: done (steps 1 to 3 done; screenshot added after the orchestrator decision)

## Files changed
- `App/app/routes/guest.py`: `_residence_prefill` also returns `surname`, `stay_from`, `stay_to` (only when non-empty); docstring sentence added.
- `App/tests/test_guest_residence_prefill.py`: anchor assertion split (address keys, `surname == "SMITH"`, no first_name/birth_date); `id="surname"` value check added to the next-person test; new browser test `test_the_second_person_on_a_phone_sees_the_copied_surname_and_dates` (390 px, person 2 step 1, imports `browser` and `live_server` fixtures from `tests/test_guest_browser_e2e.py`; device and claim cookies copied from the TestClient into the Playwright context). It writes the screenshot only when `UBYHOST_0838_SHOTS=1`.
- `docs/tasks/0838-report.md`: this report.
- Nothing committed or staged (launch instruction: orchestrator commits). Working tree also holds other threads' changes (`App/scripts/flow_taps.py`, `App/tests/test_flow_taps_browser.py`, 0841 files); not touched.

## Commands (last lines)
1. `pytest tests/test_guest_residence_prefill.py -q --tb=short -x -rs`: `11 passed in 1.69s`, 0 skipped.
2. `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x -rs`: `560 passed in 245.56s (0:04:05)`, no skip lines.
3. `pytest tests/test_endtoend.py tests/test_ubyport_*.py -q --tb=short -x`: `67 passed, 2 warnings in 6.31s` (warnings are a Pillow deprecation in test_ubyport_sample_pdf.py).

## Acceptance (section 7)
- [x] 2nd person sees surname, street, city, country; first name empty (asserted in tests).
- [x] Different device sees nothing copied (existing test passes).
- [x] Commands 1-3 pass, 0 skipped.
- [x] 390 px screenshot of the 2nd person's step 1: `docs/tasks/screenshots-0838/person2-step1-390.png` (shows SMITH, empty given name, stay dates 02.11.2026 to 05.11.2026).

## Deviations
- Surname is stored upper-cased on save, so the form shows `SMITH`, not `Smith` as the brief's example assumed. Tests use `SMITH`.
- Step 3 first stopped on the browser flow; the orchestrator then approved the new test in the same file. Run with `UBYHOST_0838_SHOTS=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_residence_prefill.py -q -rs`: `12 passed`, 0 skipped. The screenshot test was added after the guest browser set (command 2) ran, so command 2 was not rerun.
- Brief says commit per step; not done per launch instruction.
- 0841 count for the 2nd person after the change: not measured.

## Owner steps left
1. Commit `guest.py`, the test file, `docs/tasks/0838-report.md` and `docs/tasks/screenshots-0838/` on the branch (orchestrator).
2. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
