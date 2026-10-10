# Plans (L2)

Deep designs, one per feature. Open a plan only when you're working on that feature. Finished or on-hold plans live in the [archive](../archive/README.md).

| Plan | State |
|---|---|
| [stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md](stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md) | Built. Host-only, optional per property (rate 0 by default) |
| [PLAN_GUEST_INVOICE_FEATURE.md](PLAN_GUEST_INVOICE_FEATURE.md) | Built. Standalone host-only invoice builder (the filename is historical) |
| [stay-only-invoices.md](stay-only-invoices.md) | Approved 2026-10-08. Invoices only for a stay; briefs 0019, 0020 |
| [posthog-analytics.md](posthog-analytics.md) | Approved 2026-10-10. PostHog Cloud EU replaces Umami and the in-app funnel. Briefs 0033–0036 |
| [invoice-design/](invoice-design/invoice_pdf_reference.py) | Reference for `App/app/invoice_pdf.py`, plus sample PDFs |
| [stay-fee-remittance-design/DESIGN.md](stay-fee-remittance-design/DESIGN.md) | Design for the remittance PDF |

New plans: `docs/plans/<short-name>.md`, written by the orchestrator ([workflow](../context/workflow.md#flow)). They end with an ordered brief list (`docs/tasks/NNNN-*`). Composer runs PostHog briefs 0033–0036 from [posthog-analytics.md](posthog-analytics.md).
