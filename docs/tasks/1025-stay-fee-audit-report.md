# 1025 Stay-fee audit report

Status: review (branch `claude/stay-fee-audit`, based on PR #815 `claude/obec-fee-exempt`; no PR opened)

## What was checked

- Guest form Check-step estimate: `routes/guest.py::_fee_estimate`, `_fee_estimate.html`, `signature.js` syncFeeBox.
- Pay step: `_fee_pay_panel`, `stay_fee.charge_for_reservation`, rails, SPAYD amount, VS, message.
- Engine `App/app/stay_fee.py`: nights, threshold, minors, same obec, host decisions, rounding, periods, scope ruling, per-guest dates, groups, unsigned/archived guests.
- Legal intent: `04_legal_positions.md` §8, `docs/POPLATEK_Z_POBYTU.md` (zákon 565/1990 Sb. §3a to §3g).
- Host settings: rate (whole CZK, capped at 50), collect flag, `is_active`, demo stays.

## Cases and results

| # | Case | Result |
|---|---|---|
| 1 | Nights = (arrival, departure]; same-day stay = nothing | OK, pinned |
| 2 | 60 nights in scope, 61 out (§3a says 60; the brief's "63" is not the law) | OK, pinned |
| 3 | Under 18 decided per counted day (birthday mid-stay, unknown day/month = 1st, leap day) | OK in engine, pinned |
| 4 | Group: adult, child, turning 18, same obec, host-exempt, own shorter dates, unsigned, archived | Panel total = sum of persons = QR amount = register (July + August) |
| 5 | VS = reservation id, QR `AM` = total with `.00`, message `STAY FEE <id>` | OK |
| 6 | Rate change between registration and payment | Panel and open register both use the current rate: agree |
| 7 | Same group total on every device, one VS | OK (one total per stay) |
| 8 | 61-night stay | No panel, no estimate |
| 9 | Preview ignores a typed child's birth date | **Bug, fixed** |
| 10 | Edit page preview ignores stored record | **Bug, fixed** |
| 11 | Demo stay: preview shown, pay step asks nothing | **Bug, fixed** |
| 12 | Host "charge" on a real minor | Still exempt (deliberately pinned by `test_charge_cannot_bill_known_minor_days`) |
| 13 | Rounding | None needed: whole days x whole CZK rate |

## Bugs fixed

1. **Child shown a fee on the form.** The estimate is drawn before the birth date is typed, so a child (or a teen turning 18 mid-stay) saw the full adult amount (up to 50 CZK x nights). The pay step was already right. `signature.js` now recomputes days by the engine's rules as the guest types; a node test checks 57 birth/stay pairs against the Python engine, a browser test checks the page.
2. **Edit page priced a full adult stay.** Opening "change my details" ignored the stored birth date, residence, the guest's own stay dates and the host's decision. Now uses the stored record; typed values still win.
3. **Demo stay showed an estimate** that the pay step would never charge. Now none.
4. When the typed values owe nothing the box is rendered `hidden` (not left out), so correcting a birth date or city shows it again. A host decision turns the script off (decision wins).

No bug found in the money the guest is actually asked to pay (QR, panel) or in the register.

## Open questions for Josef

1. **Exactly 60 nights with no council ruling recorded:** the guest is asked to pay 60 nights. Should the pay step show nothing until the host records the ruling?
2. **Which month a night belongs to:** the `stay_fee.py` docstring says "the night of 31 Aug counts in August", but the code (and `test_nights_split_by_month`) put the counted day 1 Sep in September. Totals are the same; only the monthly split differs. Which one does your council expect?
3. **Rate change after a period is sealed:** the guest pays today's rate, the sealed report keeps the old one. Should the rate carry an effective date (the OZV date)?
4. **Hidden stay dates:** a guest can edit the hidden `stay_from`/`stay_to` to a shorter stay inside the booking and so pay less (it also changes the police record). Refuse guest changes to stay dates?
5. **Paying twice:** two guests of one stay can each pay the full group total; nothing is tracked by design. Add one line of copy ("one payment for the whole group")?
6. A guest the host added without a signature is not counted on the pay step or in the register (consistent, by design). Confirm.

## Tests run (from `App/`)

- `pytest tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_0911_guest_fee_ruian.py tests/test_0913_property_stay_fee.py tests/test_fee_*.py` : 417 passed, 2 skipped (screenshot-only)
- `tests/test_stay_fee_audit_1025.py` : 18 passed (new)
- `tests/test_static_versions.py tests/test_guest_pay_form_values.py tests/test_stay_fee_guest_pay_0897.py` : passed
- `tests/test_guest_browser_e2e.py -k "1025 or estimate"` : 3 passed; `-k fee` + `test_0896_fee_pay_geometry_browser.py` + `test_stay_fee_guest_pay_browser.py` : 26 passed, 0 skipped
- `test_0884_wizard_geometry_browser.py test_0896_fee_pay_geometry_browser.py test_layout_lint_browser.py -k "guest or form or fee or wizard"` : 27 passed
- 390 px screenshot of the form Check step looked at: box, amount and calc line unchanged (attribute-only template change). Not committed.
