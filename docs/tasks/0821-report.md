# 0821 report

Status: review (steps 1-10 done; step 9 by the orchestrator, step 10 by the executor)

## Done

- Step 1: `App/app/booking_cancel.py` created. Commit `4b0ae40`.
- Step 2: `App/app/booking_manage.py` created. Commit `4a958c6`.
- Step 3: CSS moved to `App/app/templates/_pp_booking_css.html` (with the appended rules); `property_page.html` now has `{% include "_pp_booking_css.html" %}`. Four tokens checked present. Tests 0818 (`test_booking_site_page`, `test_property_page`) pass. Commit `35ec44f`.
- Step 4: English and Czech keys added to `App/app/host_i18n.py` after the `site_booking.invoice.note` lines. Commit `1b9d461`.
- Step 5: `App/app/routes/property_page.py`: imports and the three guest routes plus helpers before `/thanks`. Ruff passed. Brief test set (62 tests) passed. Commit `935598e`.
- Step 6: `App/app/templates/booking_manage.html` created exactly as the brief. Commit `952a522`. Rendered through the step 7 and 8 tests.
- Step 7: `App/tests/test_booking_cancel.py`, 8 tests. `python -m pytest tests/test_booking_cancel.py -q`: 8 passed. Ruff passed. Commit `addb645`.
- Step 8: `App/tests/test_booking_manage_browser.py`, 4 tests (360, 390, 1280 geometry, plus the no-JS cancel). `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/usr/bin/google-chrome pytest tests/test_booking_manage_browser.py`: 4 passed, 0 skipped. Ruff passed. Screenshot saved to `docs/tasks/screenshots-0821/guest-390.png`. Commit `3e4853c`.

## Step 10 results (§6, run from App/ unless noted)

- Ruff `--select E9,F63,F7,F82,F401,F841` on the five brief files: All checks passed!
- First pytest set (17 files, `-x`): `201 passed, 1 warning` (DeprecationWarning from starlette `cookies=`, not a failure).
- Browser set (`UBYHOST_REQUIRE_BROWSER=1`, `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/google-chrome`; manage, site_page, guest e2e, host geometry): `27 passed`, 0 skipped.
- Extra guards: `test_a11y_guard_browser.py`, `test_static_versions.py`, `test_flash_literals.py`: `12 passed`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK`.
- `grep refunds.create`: `options=` carries `stripe_account` and `idempotency_key`; `params` has no `stripe_account`.
- `grep style=|#hex` on the two templates: no output.
- `git diff --stat task/0820-booking-site-invoice...HEAD`: 14 files, all in §3 (the three `host_i18n`/`property_page` edits and the step 9 doc lines included).
- Screenshot `docs/tasks/screenshots-0821/guest-390.png` viewed. Badge, h1, policy card with grey refund box and closed "Zrušit rezervaci" row render. Visible issue: the "Přidat do kalendáře" link renders as an unstyled bordered box, full width, not a grey button like the mockup. Not changed here (it is a CSS fix in the §3 partial, not a failing command); flagged for review.

## Deviations

- Step 7, test 8: the brief says the masked e-mail is `j***@`. The guest e-mail in the fixture is `petr@example.test`, so the test asserts `booking_manage.mask_email(...)` equals the page text and that the full address is absent.
- Step 7, test 1 and test 4: `mail.enqueue` also records the paid-time host notice. Test 1 clears the mail list after payment; test 4 checks the last host mail.
- Step 7, test 2: the "says nothing is refunded" check is loose (`"refund"` in the lowercase guest text).
- Step 7, test 7: the storno check asserts two invoice rows for the entity, with one of kind `storno` or `corrective`.
- Step 7: the `site` fixture replaces the brief's `booking` fixture. `_paid(site, policy, ...)` takes the fixture dict, not the policy only.
- Step 8: the visibility filter is `el.is_visible()`, not a bounding-box check. The danger button sits in the closed `<details>` and has a zero-height box, so it is skipped for the 44 px check.
- Step 8: the browser test uses a stub Stripe client (`_api`, `_client` patched) for the no-JS cancel.
- Step 4 (carried over): `tests/test_host_i18n.py` alone fails with DB-order errors ("no such table: apartment"). Run it together with `tests/test_booking_site.py` in one pytest call. Not investigated further.
- Commits use named files only.

## Test counts (this run)

- `tests/test_booking_cancel.py`: 8 passed, 0 failed.
- `tests/test_booking_manage_browser.py` (browser, required): 4 passed, 0 skipped.
- Ruff `--select E9,F63,F7,F82,F401,F841` on the step 6-8 files: all checks passed.
- Step 10 full §6 set and extras: see "Step 10 results" above.

## Owner steps left

Merge and deploy only (owner). No push was made.
