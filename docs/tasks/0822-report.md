# 0822 report (executor run)

Status: review

Done: steps 1 to 7. Not pushed, not merged.

## Files changed

- `App/app/booking_manage.py`: `List` import, `host_rows` (step 1).
- `App/app/routes/payments.py`: `booking_manage` import, `bookings=` in `booking_site_setup`; `POST /apartments/{apartment_id}/booking-site/cancel` (step 2).
- `App/app/templates/booking_site_setup.html`: "Rezervace z webu" section (step 2).
- `App/app/host_i18n.py`: `bsite.bookings.*`, flash and error keys, EN and CS (step 3).
- `docs/design/pages/booking-site.md`: one bullet, 35 lines (step 4).
- `App/tests/test_booking_host_cancel.py`: 5 tests, all pass (step 5).
- `App/tests/test_booking_site_host_browser.py`: `paid_booking` fixture and `test_host_bookings_section_fits` at 390 and 1280 (step 6).
- `docs/tasks/screenshots-0822/host-390.png`: 390 px screenshot of the host page.

## Commands (section 6 and extras, App/ unless noted)

- ruff E9,F63,F7,F82,F401,F841 (5 files): `All checks passed!`
- Section 6 pytest set: `121 passed, 1 warning in 5.60s` (warning is a Starlette DeprecationWarning in test_host_i18n)
- Browser set (test_booking_site_host_browser, test_design_guardrails_browser, test_host_geometry), REQUIRE_BROWSER=1: `17 passed in 81.74s`, 0 skipped
- Browser extras (test_a11y_guard_browser, test_static_versions, test_flash_literals, test_booking_cancel), REQUIRE_BROWSER=1: `20 passed in 99.40s`, 0 skipped
- `design_lint.py`: `design lint: OK`
- `context_lint.py`: `context lint: OK` (warnings only, no ERROR or FAIL)
- Inline style or hex grep on `booking_site_setup.html`: no output
- `git diff --stat task/0821-booking-site-cancellation...HEAD`: 8 files, the 6 brief files plus `docs/tasks/0822-report.md`

## Section 7

All six boxes ticked. Test 3 and test 4 of step 5 cover the foreign-owner and retry criteria.

## Deviations

- The brief's `git diff --stat origin/main` check was run against `task/0821-booking-site-cancellation...HEAD` instead, because origin/main is not the base of this branch. Result is the expected file list.
- Step 6 seeds the paid booking through `create_pending`, `attach_session` and the paid webhook, because no direct `site_booking` insert pattern exists in the tests.
- Step 5 uses `registry_entry` "ZR" (ASCII) in the fixture.
- Step 1 to 3 deviation from the earlier run: `test_host_i18n.py` passed in the combined run here (121 passed).

## Screenshot

`docs/tasks/screenshots-0822/host-390.png` (390 px, full page). The new "Rezervace z webu" card is at the bottom: "Jana N.", dates, "6500 Kč", a green "Zaplaceno" badge and a red "Zrušit a vrátit platbu" button. Cramped: the dates wrap onto two lines and the button sits tight beside them. Not a test failure; a possible polish item.

## Questions

- None blocking. Confirm the cramped row layout at 390 px is acceptable, or ask for a stacked layout.

## Owner steps left

None.
