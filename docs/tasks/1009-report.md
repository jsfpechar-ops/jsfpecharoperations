# 1009 report

Status: blocked
Done: steps 1 to 8 (code, copy, route flag, 3 tests) committed as 0f65d724.
Left: step 9 UX gate (seeded lint, 390/768/1280 screenshots of request page and guest booking page states, LOOK at each, per-page notes in PR), tick design-system checklist, PR.

Files changed: App/app/booking_manage.py, App/app/templates/booking_manage.html, App/app/host_i18n.py, App/app/routes/property_page.py, App/app/templates/property_page_requested.html, App/tests/test_booking_direct_0998.py.

Tests:
- pytest test_booking_direct_0997, 0998, test_booking_site, test_host_i18n, test_booking_cancel: 88 passed.
- Browser test_booking_manage_browser, test_booking_site_page_browser (UBYHOST_REQUIRE_BROWSER=1, -rs): 9 passed, 0 skipped.
- test_booking_direct_0998.py alone: 20 passed (3 new).

Deviations:
- App/.venv does not exist in the container; a scratch venv was built outside the repo from requirements.txt, requirements-dev.txt and playwright==1.63.0.
- CS strings in host_i18n.py use \u escapes; the typo fix uses the escaped form (Zaplaťte).
- Test runs rewrote docs/tasks/screenshots-0818/booking-390.png and docs/tasks/screenshots-0821/guest-390.png; reverted with git checkout.

Questions: none.
Owner steps left: none for this brief. Tool-call cap reached before the UX gate.
