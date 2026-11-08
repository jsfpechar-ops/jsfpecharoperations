# 1030: Stay-fee pay box shows all options; receipt mail shows what is due

Status: review. Executor: Haiku 5.5. Branch: the current branch, do not push.
Do NOT touch the stay-fee preview/recalculation code (another thread owns it): `stay_fee.py`, `_fee_estimate.html`, `signature.js`, `_fee_obec_rule`, `_fee_typed_guest`, `_fee_liable_days`.

## Why
The pay box on the guest hub (`guest/_fee_pay.html`) looks like a radio picker: three identical round marks, no sign of which is chosen, and "Choose one way below". Nothing is chosen in the app; the guest simply pays one way. Show every option the host enabled, equal and always open, no radios. The receipt mail must also say how much is due and how it is calculated. The app cannot know which way the guest paid (bank transfer and cash are invisible to it), so the mail never names a method used.

## 1. Template `App/app/templates/guest/_fee_pay.html`
Replace each `<details class="g-fee-opt g-summary"...>` ... `</details>` with `<div class="g-fee-opt">`, its `<summary class="g-summary-fold"><span class="g-fee-radio" aria-hidden="true"></span>TEXT</summary>` with `<h4 class="g-fee-opt-h">TEXT</h4>`, and the body `<div class="g-summary-body g-fee-rail">` stays. Remove the `{% if loop.first %} open{% endif %}`. Same for all three rails (iban, revolut, cash). Leave the rest of the file unchanged.

## 2. CSS `App/app/static/guest.css` lines ~1628-1634
Replace the `.g-fee-opt` rules with:
```
.g-fee-opt { background: var(--g-surface); border: 2px solid var(--g-line); border-radius: 14px; margin-top: 12px; padding: 16px; }
.g-fee-opt-h { margin: 0 0 12px; font-weight: 800; font-size: 18px; }
.g-fee-opt .g-fee-rail { padding: 0; }
```
Delete `.g-fee-radio` and the `[open]` rules. Grep the file for other `g-fee-opt` or `g-fee-radio` uses first and keep layout intact.

## 3. Copy `fee_now_body` (App/app/i18n.py en 356, cs 1086, de 1773, es 2278, fr 2783; App/app/guest_uk_i18n.py 319)
- en: "Pay in any one way below. You only pay once for the whole group."
- cs: "Zaplaťte jedním ze způsobů níže. Platíte jen jednou za celou skupinu."
- de: "Zahlen Sie auf einem der Wege unten. Sie zahlen nur einmal für die ganze Gruppe."
- es: "Pague de una de las formas de abajo. Solo paga una vez por todo el grupo."
- fr: "Payez de l'une des façons ci-dessous. Vous ne payez qu'une fois pour tout le groupe."
- uk: "Оплатіть одним зі способів нижче. Ви платите лише раз за всю групу."

## 4. Receipt mail
Add an optional `fee: Optional[Dict]` argument to `mail_notify.build_completion` (`App/app/mail_notify.py` ~1627). `fee` = `{"total": int, "lines": [(days:int, amount:int), ...], "rate": int, "rails": [keys], "vs": str}`. When present, after the stay panel (before the door code) add:
- a heading `mail_completion_fee_heading` ("Local stay fee");
- a paragraph `mail_completion_fee_total` ("%(total)s CZK to pay for your group. It is paid once, to your host.");
- a `_block_panel` titled `mail_completion_fee_calc_title` ("How it is calculated") with one row per line: label `fee_guest_n` (n=index; reuse the guest key, check the guest translator has it) and value `fee_person_line` (days, rate, amount);
- a paragraph `mail_completion_fee_ways` listing the enabled ways by their existing names (`fee_rail_iban`, `fee_rail_revolut`, `fee_rail_cash`) joined with ", " and, when "iban" is enabled, the variable symbol: "Pay by: %(ways)s. Bank transfer: use variable symbol %(vs)s. The payment details are on your stay page."
Same lines go into `text_lines`. Never write which method was used. Add the 5 new keys to en, cs, de, es, fr in `i18n.py` (next to `mail_completion_note`) and to `guest_uk_i18n.py` if that is where uk mail keys live (grep `mail_completion_heading` first; mirror it). You write the translations yourself, short and plain.

In `App/app/claim.py` kind == "completion" (~480) pass `fee=_completion_fee(apartment, reservation)`. Add `_completion_fee` next to `_completion_facts`: returns None unless `apartment["stay_fee_collect"]` and `config.STAY_FEE_GUEST_PAY`; call `stay_fee.charge_for_reservation(apartment, reservation)`; None if no charge or `total_czk <= 0`; lines from `charge["lines"]` where `liable_nights > 0` as `(int(liable_nights), int(amount_czk))`; rate `int(charge["rate_czk"])`; vs `str(int(reservation["id"]))`; rails = the keys of `stay_fee_guest_rails` (comma list; map "qr" to "iban"; keep only "iban","revolut","cash", in that order). Wrap it all in try/except returning None (the receipt must never fail for this). Read-only use of `stay_fee`; do not edit it. Host is copied on this mail already; no recipient change.

## 5. Tests (§6 commands)
Add to `App/tests/test_guest_mail.py` one test: `build_completion(..., fee={...})` text contains the total, one "2 nights" line, the VS, and does not contain "paid by" / "used". Add one without `fee` asserting no fee heading. Update any existing test that asserts `g-fee-radio` or `<details` in the pay box.

## 6. Commands
From `App/`:
`.venv/bin/python -m pytest tests/test_guest_mail.py tests/test_guest_languages.py tests/test_mail_label_case.py tests/test_mail_side_padding.py -q --tb=short -x 2>&1 | tail -30`
Then the test-map row for guest pages (`grep -n guest docs/context/test-map.md`, run that row only; browser/geometry tests with `-rs`, 0 skipped).
Screenshots: the guest hub with the pay box at 390, 768, 1280 into `docs/tasks/screenshots-1030/`. Also render the English receipt (text + html) of a 2-night, 1-guest, all-rails case into `docs/tasks/screenshots-1030/receipt.txt` and `receipt.html`.

## 7. Done when
- [ ] No radio marks; all enabled options visible at once
- [ ] Receipt shows total, per-guest calc, ways, VS; no method claim
- [ ] Tests pass, 0 skipped; screenshots saved
- [ ] Report written to `docs/tasks/1030-report.md`

## 8. Stop and ask if an anchor is not found, or a key is already defined elsewhere.
