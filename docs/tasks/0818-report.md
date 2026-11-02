# 0818 report

Status: blocked

## Done
- Steps 1 to 7: as before (commits 47f9ccc to 4908694).
- Step 8 (commit be52c83): `App/tests/test_booking_calendar.py` (4 tests) and `App/tests/test_booking_site_page.py` (8 tests). `pytest tests/test_booking_calendar.py tests/test_booking_site_page.py`: 12 passed.
- Step 9 (commit a464bec): `test_property_page_meta.py` test renamed and rewritten; two assertions in `test_booking_widget.py` changed to "Choose your dates"; decision line appended to `docs/context/decisions.md`. Run with calendar test and widget test: 15 passed.
- Step 10 (commit db18e54): `App/tests/test_booking_site_page_browser.py` (3 geometry tests at 360, 390, 1280, plus 1 no-JS calendar test). Run with `UBYHOST_REQUIRE_BROWSER=1`: 4 passed, 0 skipped.
- Screenshot: `docs/tasks/screenshots-0818/booking-390.png` (written by the 390 test; not yet looked at).

## Deviations
- Step 10 found the guests button (`.pp-bk-card .ui-btn`) at 21 px high. Added `min-height: 44px` to the page's own `.pp-bk .ui-btn` rule in `App/app/templates/property_page.html` (line 32). Template change, not a CSS file.
- Step 10 teardown hit a FK error on `user_account` delete. Added `alert` and `legal_entity` deletes to the browser test's `_cleanup`. Cause not confirmed.
- Playwright 1.63.0 was missing from the shared `App/.venv` (symlink to the main checkout). Installed it with pip. Chromium bundle not installed; tests run with `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/google-chrome`.
- Brief step 8 fixture: `apartment` fixture takes `fake_sessions` (Stripe monkeypatch), otherwise the page is not bookable.

## Not done
- Step 11: the section 6 commands were not run (tool budget reached). Not run: ruff, the long pytest list, the full browser list (`test_guest_browser_e2e.py`, `test_host_geometry.py` still to run), `design_lint`, `context_lint`, the section 7 greps.
- Open from before: `test_host_i18n.py` "no such table: apartment" when run alone. Not investigated.

## Next step
Run section 6 from `App/` in this order: ruff, the long pytest list, then the browser command with `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/google-chrome` added (check `0 skipped`). From repo root: `design_lint.py` and `context_lint.py`. Look at the screenshot once, then tick section 7 and set Status: review.

## Owner steps left
- None. Do not merge.
