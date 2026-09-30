# Invoice Companion — final PDF design

**Status:** selected by the owner on 30 September 2026. This is the single visual treatment for UbyHost's monthly stay-fee report to a municipal office. The [sample PDF](sample-invoice-companion.pdf) uses fictional data and is visibly marked as a sample. The renderer is [`App/app/stay_fee_remittance_pdf.py`](../../../App/app/stay_fee_remittance_pdf.py); [`build_sample.py`](build_sample.py) reproduces the sample.

## Purpose and scope

The document is **Hlášení k místnímu poplatku z pobytu** for one municipality and one completed calendar month. It is prepared at the start of the following month for the host to review and submit. It is not an invoice, proof of payment, guest register, or an automatic filing. UbyHost produces **one PDF type** for this workflow.

The current repository does not yet have a live stay-fee ledger or `/stay-fees` page. The renderer accepts a reviewed report object; wiring it to the page and database is separate implementation work. The sample PDF is design evidence, not a file to send to an office.

## Design anatomy

1. **Top rule:** 1.6 mm coral line across A4, the same restrained document accent as the existing invoice PDF.
2. **Identity header:** host legal name and IČO on the left; document title and reporting month on the right. The host is the issuer. UbyHost is not presented as the payer or the office.
3. **Two cards:** soft neutral recipient card; outlined period and creation date card. The information needed to route the filing is visible before the calculation.
4. **Calculation table:** facility and address, chargeable person-days, rate, and fee. The right-aligned numeric columns make the multiplication and sum easy to check. A property with multiple rates gets one row per rate.
5. **Result:** a soft neutral total box, in the same visual position as the invoice total, labeled “Celkem k odvodu obci”. A separate summary shows the chargeable days and count of non-chargeable people.
6. **Non-chargeable reasons:** aggregate counts only. Full guest identities remain in the separate register export unless a specific municipality requires them in its filing.
7. **Confirmation and footer:** space for the host's name/signature or electronic submission context; shipped UbyHost mark, live `UbyHost` text, and page number in a small footer. No municipal seal or altered logo.

## Visual tokens

| Role | Value |
| --- | --- |
| Page | A4 portrait, 18 mm side margins, white background |
| Ink | `#1B1F25` |
| Secondary text | `#50504C` |
| Muted labels | `#73736E` |
| Rules | `#DEDED9` |
| Soft card | `#F7F7F5` |
| Brand accent | `#D35445`, limited to the top rule and document label |
| Type | Vendored DejaVu Sans regular and bold, for Czech glyph coverage |

The layout stays legible in grayscale. It uses selectable text, not a flattened page image. Property rows and table headers repeat across pages when needed; each page carries the UbyHost credit and number. Long names and addresses wrap inside their cells.

## Report object used by the renderer

```python
report = {
    "payer_name": "Demo ubytování s.r.o.",
    "payer_seat": "Ukázková 1, 110 00 Praha 1",
    "payer_ico": "00000000",
    "payer_contact": "demo@example.test",  # optional
    "recipient_name": "Úřad městské části Praha 1",
    "period_start": "2026-08-01",
    "period_end": "2026-08-31",
    "issued_on": "2026-09-01",
    "rows": [
        {"property_name": "Old Town Loft", "property_address": "Dlouhá 12, Praha 1",
         "chargeable_days": 24, "rate_czk": 50, "amount_czk": 1200},
        {"property_name": "Josefov Studio", "property_address": "Maiselova 9, Praha 1",
         "chargeable_days": 22, "rate_czk": 50, "amount_czk": 1100},
    ],
    "total_days": 46,
    "total_czk": 2300,
    "not_charged": [
        {"reason": "Mladší 18 let", "count": 1},
        {"reason": "Přihlášení k pobytu v obci", "count": 1},
    ],
}
pdf_bytes = stay_fee_remittance_pdf.render(report)
```

The renderer rejects missing payer or recipient identity, incomplete reporting months, negative figures, mismatched row arithmetic, and totals that do not match the rows. It performs **no legal calculation** itself. The caller must derive the rows from reviewed fee records, allocate each chargeable day to the correct calendar month, group them by municipality/property/rate, and verify the municipality's current reporting requirements before offering the final download. The page must not mistake a guest's unpaid status for a reduction in the amount owed to the municipality.

## Build and verify the sample

From the repository root, with the app's Python dependencies installed in `App/.venv`:

```bash
App/.venv/bin/python docs/plans/stay-fee-remittance-design/build_sample.py
cd App && .venv/bin/python -m pytest tests/test_stay_fee_remittance_pdf.py -q
```

The builder writes `sample-invoice-companion.pdf` beside this file. It passes `sample=True`, which adds “NÁHLED · UKÁZKOVÁ DATA” without relaxing identity or arithmetic validation. The sample has one page and uses no real guest data.

## Acceptance checks for the eventual page integration

- The selected completed month and municipality shown on the page match the PDF exactly.
- A stay crossing month end is split between months without double counting.
- Multiple properties and rates reconcile to the displayed total.
- Missing identity or unresolved fee decisions block a final download with a clear explanation.
- The response is owner-scoped, downloaded as one PDF, and does not claim that a filing or bank payment has occurred.
- The destination municipality's current form and deadline are checked before the report is treated as ready to send.
