# 0040 invoice presentation report

Status: review

## Scope and findings

Reviewed the invoice generator (`invoice_form.html`), stay picker
(`invoice_stay_picker.html`), settings (`invoice_settings.html`), saved detail
(`invoice_detail.html`), and list shell (`invoices.html`). The list filter partial
remained read-only under the filter owner. `/invoices/preview` returns an inline
PDF from the existing renderer; no PDF or calculation code was changed.

The generator’s heading and 1050px workspace align exactly at 1280, 1440,
1680, 1920, and 2048 CSS pixels. Its item header and rows share one grid with a
reserved removal track; Quantity, Unit, Unit price, VAT, and Remove controls
remain aligned. At narrower table widths, labeled item cards keep the price
controls full-width and readable. EN/CS screenshots at 360, 390, 1440, 1680,
1920, and 2048 show no page overflow. Other description remains conditional,
retains its value across kind changes, and is labeled without JavaScript.
Cleaning Unit remains blank and enabled.

The live 390px browser check found the sticky action bar covering the focused
Other description by 35.1px. Shared CSS now keeps the builder action bar in
normal flow after the form, so it no longer covers customer or item fields;
Preview and Issue remain available at the form end. The initial header-edge
assertion accidentally measured the wider outer form wrapper. The corrected
assertion compares the visible 1050px workspace: at 1440, heading and workspace
are both x=303, width=1050, while the outer wrapper is x=288, width=1080; at
1680, 1920, and 2048, both heading and workspace remain x=423, 543, and 607
respectively with width 1050. At 1280, heading and workspace are both x=250,
width 996.

## Validation and evidence

`UBYHOST_REQUIRE_BROWSER=1` with system Chromium ran
`tests/test_host_invoice_items_browser.py`: **5 passed, 0 skipped** across EN/CS
and widths 360, 390, 760, 1024, 1280, 1440, 1680, 1920, and 2048. Coverage
checks overflow, control tops and widths, header/removal tracks, Other value
retention, the no-JavaScript fallback, and action-bar overlap. Ruff passes for
the owned test file.

Actual full-page, unmodified-layout screenshots (scroll reset to page top) are
in `/workspace/generated_images/host-wide-audit/invoice-items/`. They include
EN/CS Other states at 360, 390, and 1440–2048; EN/CS Cleaning states with no
custom-description field at 390 and 1440; and EN/CS non-VAT-payer states at
1440 with the VAT column absent. The cross-page list/settings/detail/picker
captures and geometry checks are owned by validation and are recorded in its
0040 evidence report.

No invoice presentation templates, calculations, validation, endpoint behavior,
or PDF renderer were changed in this scope. No commit or push was made.
