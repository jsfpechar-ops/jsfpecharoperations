# 0818 report

Status: review

## Files changed (step 11)
- `App/tests/test_booking_site_page_browser.py`: removed unused `stripe_connect` import (ruff F401).
- `docs/tasks/screenshots-0818/booking-390.png`: 390 px screenshot, viewed once.
- `docs/tasks/0818-report.md`: this report.

## Commands (section 6, from App/ unless noted)
- ruff (E9,F63,F7,F82,F401,F841): first run `Found 1 error.` (F401, stripe_connect). Fixed. Rerun: `All checks passed!`
- Unit list (incl. test_host_i18n.py with test_booking_site.py, one call): `143 passed, 1 warning in 5.55s`
- Browser, 3 files, `UBYHOST_REQUIRE_BROWSER=1`, `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/google-chrome`: `23 passed in 180.17s`, no skip lines.
- Browser file rerun after the import fix: `4 passed in 7.28s`, 0 skipped.
- `design_lint.py` (repo root): `design lint: OK`
- `context_lint.py` (repo root): `context lint: FAIL`. `ERROR docs/context/decisions.md: ~2264 tokens > cap 2200`. Not fixed (see Deviations).
- Section 7 greps: colour grep prints nothing; `ui-input` count 3; `<script` count 0.
- `git diff --stat origin/main...HEAD`: 18 files. No requirements/lock file and no .venv path.

## Section 7
- [x] Three test runs pass; browser run shows 0 skipped.
- [x] No raw colour in property_page.html.
- [x] `ui-input` count 3; no `<script` in the template.
- [ ] Fresh `GET /p/<slug>` is Czech and `?lang=en` is English with no `Set-Cookie`: not checked by hand in this step.
- [ ] `git diff --stat origin/main` lists only §3 files: NOT MET. The diff also has `docs/tasks/0819-*` to `0822-*` (4 briefs), `docs/plans/booking-site-v1.md`, and `docs/context/decisions.md`. The first five were not in §3 and were not changed by step 11.
- [x] 390 px screenshot at `docs/tasks/screenshots-0818/booking-390.png`, named here.

## Deviations
- Context lint fails on `decisions.md`. origin/main is 8806 chars (~2201 tokens) and is already over the 2200 cap. The step 9 line adds ~63 tokens. Fixing it needs compacting other decisions, which is an orchestrator call.
- Screenshot check (by eye, against §1): card order is calendar, price lines, policy, form. Arrival (10) and departure (13) use the accent. Booked 20 and 21 are struck through. Visible issue: the guests label wraps ("Počet / hostů") and the guests input is narrow. Not fixed.
- Two mockup deviations from §1 were not re-read in this step.
- Step 10: guests button was 21 px high; added `min-height: 44px` to `.pp-bk .ui-btn` in `App/app/templates/property_page.html` (line 32).
- Step 10: teardown FK error on `user_account` delete; added `alert` and `legal_entity` deletes to the browser test `_cleanup`. Cause not confirmed.
- Playwright 1.63.0 installed with pip into the shared `App/.venv`; Chromium bundle not installed, tests use `/usr/bin/google-chrome`.
- Step 8: `apartment` fixture takes `fake_sessions` (Stripe monkeypatch), otherwise the page is not bookable.
- Open from before: `test_host_i18n.py` alone gives "no such table: apartment". Not investigated; it passes in the unit run together with test_booking_site.py.

## Questions
- Diff scope: keep the 0819-0822 briefs and the plan file on this branch, or move them out?

## Owner steps left
- None. Do not merge.
