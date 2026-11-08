# 1007 report

Status: blocked

## Files changed
- App/app/routes/property_page.py (steps 1, 2, and fix 2b)
- App/app/booking_manage.py (step 3)
- App/app/templates/booking_manage.html (step 4)
- App/app/booking_webhook.py (step 5)
- App/app/templates/property_page.html (step 6)
- App/app/templates/_pp_booking_css.html (step 7)
- App/app/host_i18n.py, App/app/booking_direct.py (step 8)
- App/tests/test_booking_direct_0997.py (step 9, 3 tests added)

## Commands and results
- pytest 0997, 0998, property_page, booking_site, host_i18n: 84 passed, 0 skipped.
  Last lines: "84 passed, 1 warning in 3.12s"
- UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_booking_site_page_browser.py -rs: 4 passed, 0 skipped.
  Last line: "4 passed in 4.45s"
- UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py -rs: 4 passed, 0 skipped.
  Last line: "4 passed in 233.25s"

## Section 7 acceptance
- [ ] Reload of request page: covered by test_request_page_get_twice_same (passes). Not yet checked in a live browser.
- [x] Confirmed direct booking page: "Total", direct policy text, no paid wording (test passes).
- [ ] 390 px screenshots: NOT TAKEN. Not done before the executor tool cap.
- [x] Tests pass, 0 skipped in the browser file.

## Deviations
- Step 2 could not work as written: `_booking_or_none` returns None for statuses outside booking_manage.VISIBLE (requested and expired are not in it), so the GET 404'd before the new branch. Fix (commit "1007 step 2 (fix)"): `_booking_or_none(..., open_requests=False)` lets direct requested or expired bookings through, and only booking_manage_page passes True.
- Step 2 used a local `from .. import booking_webhook` inside the function.
- Step 7: the CSS is appended before `</style>` (the file wraps its CSS in a style tag). Spacing uses the file's existing `var(--space-*)` tokens.
- Step 8: `pp.book.send_request` CS value kept the file's ASCII-escape style.
- Step 9: existing 0997 tests already follow the redirect (TestClient follows it), so none needed changing.

## Done / Left
- Done: steps 1 to 9 (with the deviations above), tests above.
- Left: UX gate. Seed a requested direct booking, take 390/768/1280 screenshots of /p/<slug> (both pay modes), the request page, and the guest booking page into /mnt/project-files/pr803-review/after1007/, look at each, write per-page notes in the PR, tick the design-system checklist.
- Left: docs/tasks/screenshots-0818/booking-390.png was rewritten by the browser test run and was reverted.

## Owner steps
None.
