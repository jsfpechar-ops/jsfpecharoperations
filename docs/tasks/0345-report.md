# 0345 report

Status: review

## Files changed
- App/app/guide_token.py: imports, qr_png
- App/app/routes/guest_guide.py: QR routes (qr, qr.png, qr/rotate) above the item routes
- App/app/templates/guest_guide_qr.html (new)
- App/app/templates/guest_guide.html: secondary "QR code for guests" action
- App/app/host_i18n.py: _GUIDE_QR_STRINGS (en, cs)
- docs/design/catalog.json: enforced_templates entry
- App/tests/test_design_guardrails_browser.py: guest-guide-qr route
- App/tests/test_guide_qr.py (new, 6 tests)
- docs/tasks/0295-report.md

## Commands (last lines)
- `pytest tests/test_guide_qr.py tests/test_guest_guide_pages.py tests/test_guest_guide_view.py tests/test_guide_photos.py tests/test_guest_guide.py -q`: `51 passed, 1 warning in 14.10s`
- `pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q` (browser env not set): `3 failed, 149 passed, 31 skipped`
- Same with UBYHOST_BROWSER_EXECUTABLE set and -rs: `3 failed, 180 passed, 0 skipped`
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_design_guardrails_browser.py -k every_host_page`: `1 passed, 9 deselected in 51.54s`
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, informational)

## Acceptance (§7)
- [x] Only the §3 files changed, plus the report
- [x] test_guide_qr.py tests pass (inside the 51 passed above)
- [x] Both lints OK

## Deviations
- The 3 failures are the known tests/test_host_i18n.py failures that predate this work.
- No 390 px screenshot: the brief has no screenshot step.
- Only one commit, as the owner asked, not one per step.

## Questions
None.

## Owner steps left
1. Review and merge once CI is green.
2. After deploy: open a property, Guest guide, "QR code for guests", download, print at least 5 cm wide, stick it inside the front door.
3. Confirm UBYHOST_PUBLIC_BASE_URL is the real public address.
