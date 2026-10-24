# 0344 report

Status: review

## Files changed
- New: App/app/migrations/0014_guide_token.sql, App/app/guide_token.py, App/app/routes/guest_guide_view.py, App/app/templates/guest/guide.html, App/tests/test_guest_guide_view.py, App/tests/test_guest_guide_browser.py
- Edited: App/app/main.py, App/app/routes/guest_guide.py, App/app/i18n.py, App/app/guest_uk_i18n.py, App/app/templates/guest/base.html, App/app/templates/guest/stay.html, App/app/static/guest.css, App/tests/static_versions.json

## Commands (last lines)
- `pytest tests/test_guest_guide_view.py + group (12 files) -q`: `144 passed, 1 warning`
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_guide_browser.py -rs`: `2 passed`
- `pytest tests/test_*_i18n.py -q`: `3 failed, 23 passed` (the 3 known failures in test_host_i18n.py, Vietnamese; not fixed)
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -rs`: `436 passed` (0 skipped)
- `python3 scripts/design_lint.py`: OK
- `python3 scripts/context_lint.py`: OK

## Section 7
- [x] Only the brief's files changed (plus report). Screenshots in App/.screenshots (not committed).
- [x] test_guest_guide_view.py passes; guest group 0 skipped; both lints OK.
- [x] Screenshots written: App/.screenshots/0294-guide-qr-en-390.png, App/.screenshots/0294-guide-qr-cs-390.png
- [x] Headers asserted by tests (no-store, noindex, no-referrer) on the QR page.

## Deviations
- Group 1 ran 144 tests (brief says 143); guest group 436 (brief says 435). Counts differ by one; all pass.
- Skipped the 390 px screenshot review; orchestrator takes them.

## Questions
- None.

## Owner steps left
- Review and merge after CI is green (no push by executor).
