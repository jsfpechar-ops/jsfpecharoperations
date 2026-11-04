# 0898-fix-1 report

Status: review

## Files changed
- App/app/stay_fee.py: near-miss code, flag and _CHARGE_KEYS entry removed; comment block rewritten.
- App/app/routes/stay_fees.py: check_residence dropped; obec_resident flag added; local_hint off when auto-exempt.
- App/app/templates/stay_fee_detail.html: check-residence badge and help_tip import removed; obec_resident reason line added.
- App/app/host_i18n.py: 4 check-residence keys removed; stay_fees.hint.obec_resident added (en, cs).
- App/app/host_vi_i18n.py: stay_fees.hint.obec_resident added (vi).
- App/tests/test_stay_fee_obec_0898.py: near-miss tests replaced; flags pairs; route test added.
- docs/tasks/screenshots-0898/*.png: 4 screenshots overwritten. No guest template changed.

## Commands (last lines)
- `.venv/bin/python -m pytest tests/test_stay_fee*.py -q`: 196 passed, 0 failed, 0 skipped.
- `pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q`: 38 passed, 3 failed, 0 skipped. The 3 failures are all in test_host_i18n.py ("no such table: apartment"). Run after test_stay_fee_obec_0898.py, that file passes 30/30. Pre-existing DB-init ordering, not from these edits (see Questions).
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q -rs`: 4 passed, 0 skipped.
- `python3 scripts/design_lint.py`: OK.

## Screenshots (what I saw)
- en-768: "G1 Test" (Praha 5, CZ) shows grey Exempt pill and the reason line; no "Check residence". Layout clean.
- en-1280: header Save period top right, no overflow in the crop. Did not confirm the G1 row pill at this scale.
- en-390: page is 3336 px tall; I viewed only the top 1400 px. Save period is full width. The guest list is below the crop; reason line not seen.
- cs-390: top 1400 px only; Czech copy renders. Guest rows below the crop; reason line not seen.
- Noted, not fixed (out of brief): the input placeholder "e.g. ZTP/P card checked; registered in this mur..." is clipped at 390 and 768.

## Design-system checklist (§5)
- [x] Layout lint green, 0 skipped.
- [x] Screenshots at 390/768/1280 opened; notes above.
- [x] CS and EN keys added together; no em dash (copy tests pass).
- [ ] Other items not verified in this session.

## Deviations
- Screenshots: capture used a temporary test (deleted) that drives the TestClient through Playwright route interception.

## Questions
- test_host_i18n.py fails when run before any DB-initialising module. Confirm this is the known ordering issue.
- Clipped placeholder at 390 px (see above): fix in a separate brief?

## Owner steps left
- None for this brief. Merge and deploy are the owner's; no commit made.
