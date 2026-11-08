# 1028 report

Status: review. Done on branch `claude/fee-rate-dates` together with 1027 (one branch, not `claude/dated-rates-1028`).

## What changed, in plain words

- **Sealing** (the seal button and the daily auto-seal, `stay_fee_auto.confirm`) prices each night at its dated rate. The row stores the last-day rate plus the per-rate split.
- **Corrections**: the 3 recalculations in `routes/stay_fees.py` and the correction seal use `stay_fee_filing.correction_rate`. A sealed flat period keeps its old rate. A period that spans a rate change is priced per night again, and the total stays the same.
- **Save hook**: `routes/stay_fees.record_rate_change` runs after the property editor or wizard save (`admin._save_apartment_form`, the one apartment UPDATE) and after property create. It records a dated row when the rate changed. The date is `stay_fee_rate_from` if valid, otherwise today (Prague date). A past date becomes today. An unchanged rate writes nothing. Earlier nights keep the old rate. `onboarding_wizard.py:252` only builds a draft and writes nothing, so it was left alone. No other UPDATE of `stay_fee_rate_czk` exists besides the one-time reset in `db.py`.
- **Guest pages** (`routes/guest.py`): the pay panel's per-person amount is now the per-night line amount; it was `nights x rate` (old line ~2198). The estimate box amount is per night; it was `days x column rate` (old line ~2301). Live JS recalculation is off (`live = None`) when the stay spans a rate change. The rate shown is the rate on the last night. No template, JS or CSS changed, so no cache bump was needed.

## Money impact

- The pay panel total, each person's amount, the QR (SPAYD AM), the register and the period total all agree: 140 CZK in the test across a 30 to 40 change.
- No history rows means the same amounts as before (full test row green).

## Commands (last lines)

- `pytest tests/test_stay_fee_rate_dates_1028.py`: 6 passed (auto-seal frozen and correction, legacy flat correction, editor dated rows with clamping and invalid date, estimate mixed and single, pay panel / QR / register agreement)
- Test row plus `test_guest_pay*.py test_property_form_save.py test_static_versions.py`: 428 passed, 2 skipped (screenshot-only tests in invoice_autofill)
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_stay_fee_guest_pay_browser.py tests/test_stay_fee_pay_steps_browser.py tests/test_0896_fee_pay_geometry_browser.py -rs`: 19 passed, 0 skipped
- No PNG or `.s4a.log` was changed.

## Acceptance

- [x] The new seal and the auto-seal price per night and store the last-day rate plus the split
- [x] Corrections keep a legacy flat rate; a mixed period is priced per night
- [x] Editor, create and wizard write a dated row, never in the past; an unchanged rate writes nothing
- [x] Guest estimate and pay total are per night; live JS is off across a rate change
- [x] No template, JS or CSS change; no new dependency

## Not covered by a test

- Create with a rate through HTTP: the test create POST with a fee rate was refused by fee validation. The path calls the same helper with `previous=0`. `record` covers the logic.

## Questions for the owner

1. For a stay across a rate change, the pay panel line "N CZK per person for each counted night" and the estimate line "days x rate" show the last-night rate, while the total is correct. Hide or reword those lines (a guest-page change with browser tests, follow-up brief)?
2. The booking-site city tax (`booking_site.py`) still uses the current column rate. Leave it?
3. With 1029, a host can set a future effective date. The column (`is_active`, editor, booking site) takes the new rate at once, while the nights are priced by date. Is that acceptable?
