# 1084 report: one pay rule (F2, P5)

Status: review

## Files changed
- `App/app/stay_fee.py`: `guest_pay_ways` now builds on `payout_account` + `usable_rail_keys`, decides the QR itself (`qr_ok=None` means the stay rule); `GUEST_RAIL_ORDER` removed.
- `App/app/routes/guest.py`: `_qr_offered` and `QR_NATIONALITIES` deleted; `_fee_pay_panel(..., qr_ok=None)` reads `guest_pay_ways`; three callers drop the QR argument.
- `App/app/claim.py`: `_completion_fee` calls `guest_pay_ways(apartment, reservation, charge)`.
- `App/tests/test_stay_fee_rate_dates_1028.py`: line 130 passes `qr_ok=True` (the allowed edit).
- `App/tests/test_pay_rule_1084.py`, `App/tests/test_pay_rule_1084_browser.py`, `docs/tasks/screenshots-1084/stay-qr-390.png`: new.

## Commands (last lines)
- Section 6 unit row: `202 passed, 1 skipped` (skip: 1078 Postgres two-connection test, needs a Postgres URL; preexisting).
- Stay fee + invoice row: `1009 passed, 2 skipped` (skips: invoice autofill screenshots need `UBYHOST_SHOTS_DIR`; preexisting, not browser).
- Guest row, `UBYHOST_REQUIRE_BROWSER=1`: `684 passed, 9 warnings`, 0 skipped.
- Browser row incl. layout lint: `24 passed`, 0 skipped.
- `context_lint.py`: `context lint: OK` (3 preexisting WARN lines).

## Section 7
- [x] One place: `guest_pay_ways`; both callers use it; `_qr_offered`, `QR_NATIONALITIES`, `GUEST_RAIL_ORDER` gone.
- [x] Same ways, same order, same QR decision on screen and mail (4a, 4b).
- [x] 1077 tests green unedited.
- [x] Stay page browser/geometry 0 skipped at 390/768/1280; layout lint green; screenshot saved.
- [x] Diff touches only section 3 files.

## Screenshot
`stay-qr-390.png`: the bank way shows the 176 px QR, then the recipient, IBAN, amount and VS rows below with no overlap; Revolut and cash follow; no sideways scroll.

## Layout lint (stay page)
No findings reported; the run passed green.

## Deviations
- `test_pay_rule_1084.py` uses its own 1025-style fixture (a real collecting apartment and stay) rather than the 1077 `_stay` helper, because `_completion_fee` needs a live charge. It imports `_completion` and `_fee` from the 1077 test.
- The browser test sets the signed owned-guest cookie for the German guest, so the "this phone" case is really exercised.
- Installed `playwright==1.63.0` into the local `.venv` only (the CI pin); no repo dependency change.

## Questions
None. Owner steps: none.
