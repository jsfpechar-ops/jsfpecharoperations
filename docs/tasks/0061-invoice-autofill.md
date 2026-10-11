# 0061: Invoice fills itself: guest's details, BIC from the bank code, last price hint

Status: todo
Depends on: none | Branch: task/0061-invoice-autofill
Executor: Cursor local agent | Fits one session

## 1. Objective
Writing an invoice for a stay needs almost no typing: one button copies the stay's lead guest into the buyer fields, the BIC fills itself from the Czech bank code, and the stay price shows last time's price as a hint.

## 2. Context
- `App/app/routes/invoices.py`: `_stay_for`, `_form_context` (already copies `guest_email`), `invoice_new`, POST `/invoices/preview`, `_settings_detail_payload` (bic).
- `App/app/templates/invoice_form.html` buyer fields: buyer_name, buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email; `stay_price`.
- `App/app/payments.py` `czech_account_parts(raw)` returns prefix/number/bank/iban.
- `guest` table: reservation_id, first_name, surname, res_street, res_city, res_country, archived_at; `reporting.guest_is_complete(row, reservation)`.
- Bank codes: ČNB list `https://www.cnb.cz/cs/platebni-styk/.galleries/ucty_kody_bank/download/kody_bank_CR.csv` (semicolon CSV, columns code; name; BIC; CERTIS). Checked 2026-10-11 (0800 → GIBACZPX, 2010 → FIOBCZPP).
- Privacy rule 2. This reuses check-in data for that same guest's invoice, only when the host presses the button.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/data/bank_codes.csv | new | the ČNB file saved once in UTF-8 (code;name;bic), with a header comment line giving the source URL and date |
| App/app/payments.py | edit | `bic_for_account(account: str) -> str` (from the bank part of a Czech account, or the IBAN's digits 5–8 for CZ IBANs); "" if unknown |
| App/app/routes/invoices.py | edit | the settings save fills `bic` when blank; preview/new: `fill_from_guest` button handling; the last-price hint |
| App/app/templates/invoice_form.html | edit | `<button name="fill_from_guest" value="1" formnovalidate class="btn-secondary">Use the guest's details</button>` above the buyer block, shown only when the stay has a complete guest; the price `placeholder` = the last price |
| App/app/host_i18n.py | edit | EN + CS keys `invoice.fill_guest.*`, `invoice.price_hint` |
| docs/privacy/ROPA.md | edit | one line: check-in name and address may be copied to that stay's invoice on host request |
| App/tests/test_invoice_autofill.py | new | tests |

## 4. Steps
1. Lead guest = the first (lowest id) non-archived guest on the reservation for which `guest_is_complete` is true and that belongs to the host's apartment.
2. On `fill_from_guest`: re-render the form (no save, no preview) with buyer_name = "first_name surname", buyer_street = res_street, buyer_city = res_city, buyer_country = res_country. **Only fill blank fields.** Keep all other typed values (reuse `_form_state`).
3. BIC: on settings save, when `bic` is blank and the account has a known bank code, store the derived BIC; show it in the form as "Filled from your bank code". Never overwrite a typed BIC.
4. Price hint: the last issued invoice for the same apartment → its stay item unit price as the `placeholder` (not a value).
5. Tests: the button fills blanks only; another host's guest is never used; no complete guest → no button; BIC 0800 → GIBACZPX, unknown → blank; a typed BIC is kept; the hint is a placeholder and empty when there is no earlier invoice; works without JS.

## 5. Do not touch
Invoice numbering, the PDF layout, issue/cancel logic, migrations (none).

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] A stay with a checked-in guest: one click fills the buyer; the preview shows the guest as buyer.
- [ ] Screenshots of the invoice form before and after the fill at 360, 390 and 1280 px.

## 8. Stop and ask
1. The invoice form can't re-render without a preview POST without restructuring the routes.
2. Guest rows are encrypted or not readable from the invoices route without a new access helper.

## 9. Report
Files, test tail, screenshots, the ROPA line.
