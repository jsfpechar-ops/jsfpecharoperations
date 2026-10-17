# Host design: actual browser evidence

These unmodified Playwright/Chromium images use fictional records. The baseline
reproduces the owner's staging geometry defect. Corrected captures use the
application's runtime CSS, without screenshot-only layout overrides. Corrected
fixtures also include mixed reporting states and a persisted date warning to
exercise action containment and alert placement.

| Page, English at 1920 CSS pixels | Before | Corrected |
|---|---|---|
| Dashboard | [Before](before-dashboard-en-1920.png) | [Corrected](after-dashboard-en-1920.png) |
| Stays | [Before](before-stays-en-1920.png) | [Corrected](after-stays-en-1920.png) |
| Properties | [Before](before-properties-en-1920.png) | [Corrected](after-properties-en-1920.png) |
| Invoices | [Before](before-invoices-en-1920.png) | [Corrected](after-invoices-en-1920.png) |
| Stay fees, not set up | [Before](before-fees-unset-en-1920.png) | [Corrected](after-fees-unset-en-1920.png) |

Additional states:

- [Dashboard with calendar controls and the five-stay cap](after-dashboard-controls-en-1920.png).
- [Czech Stays at 1280: dates and adjacent actions](after-stays-actions-cs-1280.png).
- [Dashboard at 760 with a real persistent warning](after-dashboard-en-760.png).
- [Invoice items: shared price column](after-invoice-items-en-1440.png).
- [Focused mobile postcode: Save no longer covers the field](after-property-new-cs-360-focused.png).

The [validation report](../0040-luna_validation-report.md) records exact route,
width, language and interaction coverage. The portable review gallery includes
the complete capture manifest and SHA-256 hashes; this folder contains a small
reviewable selection. Local captures do not identify the deployed staging SHA.

See [approved designs and the gallery](../../plans/host-design-application-review.md)
and [PR #338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338).
