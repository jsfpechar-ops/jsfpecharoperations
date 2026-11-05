# 0959 report (executor: Haiku 5.5)

Status: review. Done: steps 1 to 5 of the brief, plus the 0958 browser check and screenshots.

Files: App/app/routes/stay_fees.py, App/app/templates/_stay_fee_fields.html, App/app/static/stay-fee-guest-pay.js, App/app/host_i18n.py, App/tests/test_stay_fee_guest_pay_0897.py, App/tests/test_stay_fee_guest_pay_browser.py, App/tests/test_guest_browser_e2e.py (screenshot hook only), App/tests/static_versions.json.

Commands (last lines):
- `pytest tests/test_stay_fee_guest_pay_0897.py`: 44 passed
- `pytest test_stay_fee_guest_pay_browser.py test_property_navigation_browser.py test_layout_lint_browser.py -rs` (finish-card test deselected): 20 passed, 0 skipped
- `pytest test_guest_browser_e2e.py -k fee -rs`: 8 passed, 0 skipped
- 390 screenshot run for the two 0958 cards: 2 passed

§7 UX gate (Settings > Stay fee, 390/768/1280): layout lint green. Screenshots in docs/tasks/screenshots-0959/. At 390 I saw: "How guests can pay" with Bank transfer (IBAN), Revolut, Cash; no Automatic option; the "Show first" select is hidden because no method is ticked.

0958 check, what I saw at 390 px (docs/tasks/screenshots-0958/):
- guest-hub-fee-card-390.png: Stay fee card, 150 CZK, "Bank transfer" open with QR, recipient, IBAN, amount, VS; Revolut and Cash collapsed. Three rails, merged IBAN with QR, as intended.
- form-estimate-390.png: "150 CZK for you (3 counted nights x 50 CZK)" line renders under the form's Stay fee card.

Deviations: all steps in one commit (8ca3f9d) instead of one per step. Brief §4: derive_missing_bic not reused (stay_fees saves no BIC); apply_account_payload reused. Revolut-free guests: ordinary. operator_invoice_note text replaced with the brief's sentence (en/vi/cs). Vietnamese help text left in English as before.

Questions: none.
Owner steps left: review and merge via scripts/merge-pr-on-green.sh (no PR opened, per brief). Production deploy is manual.
