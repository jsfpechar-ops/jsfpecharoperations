# 0910b report

Status: review

## 1. Files changed (git diff --stat)
- App/app/guest_uk_i18n.py: -2
- App/app/i18n.py: -10 (fee_message_label, fee_revolut_intro in en, cs, de, es, fr)
- App/app/routes/guest.py: VS plain id, message "Stay fee {vs}", QR rail has no iban, panel dict has no message
- App/app/templates/guest/_fee_pay.html: QR rail is image only, IBAN rail has no Message row, Revolut intro removed
- App/tests/test_guest_browser_e2e.py: new assertions in the fee card test
- App/tests/test_stay_fee_estimate_0910.py: SPAYD/VS unit test
- New, untracked: docs/tasks/screenshots-0910b/ (5 PNG), this report
- Not touched: guest.css (no ?v= bump), payments.py, host files, migrations.

## 2. Commands
- `cd App && .venv/bin/python -m pytest tests/test_stay_fee_estimate_0910.py -q --tb=short -x`: 12 passed, 0 failed, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_stay_fee_estimate_0910.py tests/test_layout_lint_browser.py -q --tb=short -rs -k "fee or layout or stay_fee or lint or 0910"`: 20 passed, 18 deselected, 0 failed, 0 skipped. Ran in the background, took 263 s.
- Temporary screenshot test (file deleted afterwards): 1 passed; all 5 screenshots `scrollWidth <= innerWidth` True.
- `python3 scripts/context_lint.py`: context lint OK (only pre-existing WARN lines).
- Grep `fee_message_label|fee_revolut_intro` in App/app: no hits (outside pycache). Catalogs import cleanly.

## 3. Section 7 acceptance
- [x] Key grep empty; catalogs load.
- [x] SPAYD test passes (X-VS:2, MSG:STAY FEE 2, no 0000000002).
- [~] Command 2 green, 0 skipped, but with a -k filter (see Deviations).
- [x] Rendered card checked in screenshots below.
- [x] No "0000000" in the card (asserted in the e2e test).

Screenshots (SEEN):
- hub-fee-card-320.png: QR open, image fully inside the card, nothing clipped, no horizontal scroll. Revolut/Cash folds visible.
- hub-fee-card-390.png: QR image alone under "QR code", no IBAN/VS/Message text. One card, no clipped text.
- iban-open-390.png: Bank transfer rows IBAN, Amount 150 CZK, "Variable symbol 1" (seed reservation id 1). No Message row.
- revolut-open-390.png: only the coral "Pay 150 CZK with Revolut" button, no intro sentence.
- hub-cs-390.png: Czech labels (Poplatek za pobyt, Bankovni prevod, Hotovost) fit, nothing cut off.

## 4. Deviations
- The browser run used `-k` to select fee, layout and lint tests (20 selected). The full three-file set was not run.
- Panel-level assertion (`_fee_pay_panel` vs/message) was skipped; the SPAYD unit test and the e2e text checks cover it.
- QR left-aligned at 390 px and looked fine, so no CSS change was made.

## 5. Questions
- None.

## 6. Owner steps left
- None.
