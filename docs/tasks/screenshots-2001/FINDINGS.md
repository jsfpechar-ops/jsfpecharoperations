# 2001 design-test run (2026-11-21, Chromium headless shell 159 via Playwright)

Baseline = current main (fa85ae1a + brief 2001). Purpose: rigorous design tests and
screenshots for the invoice builder and the stay page, per owner request.

## Commands (all green, 0 skipped)

- `test_layout_lint_browser.py` — 4 passed (every host page x 7 widths 320-1920; report: `host: []`, zero findings; only pre-existing report-only public-login language-switch findings). Screenshots 390/768/1280 of every host page.
- `test_design_invoices.py test_0293_invoice_form.py` — 5 passed.
- `test_host_stay_detail_layout_browser.py test_design_stays.py test_host_geometry.py` — 7 passed.
- `test_host_wide_geometry_browser.py test_host_controls_browser.py test_design_guardrails_browser.py` — 22 passed.

## What the screenshots show

Files: `invoice-*`, `stay-detail-*`, `stays-*` (layout-lint set) and `custom/` (builder with a
stay that has no invoice yet, plus the stay ⋮ menu opened).

- `custom/invoice-builder-1280.png` — the builder at desktop: single column, sections Supplier / Customer / Items / Payment / Language. **Items row geometry confirmed bad**: description on the left, then a wide empty white gap, then QTY / UNIT / UNIT PRICE inputs pinned to the right edge, Remove at the far right. Cause: `app2.css` 0831H fixed grid `minmax(220px,1fr) 84px 124px 148px 78px 126px` + `#item-rows` `max-width:850px`. Bottom bar: total `0 Kč`, next number, Preview (secondary), Issue invoice (one primary).
- `custom/invoice-builder-768.png` / `-390.png` — rows stack as cards on phone; no sideways scroll, no truncation; action bar wraps full width. Geometry acceptable on phone; the desktop gap is the offender.
- `custom/stay-detail-1280.png` — header action row has only `Send to UbyPort` (primary) + `Copy guest form link`; **no invoice button**.
- `custom/stay-detail-menu-open-1280.png` — the ⋮ menu contains `Add a guest`, `Invoice 2026-0918-cd17`, `Open guest form`, `Delete`, `Guest links & templates`: invoice is buried in the overflow menu, exactly the owner's complaint.
- `invoice-new-selected-*` in the lint set redirects to the invoice detail (the seeded stay already has an invoice) — that is why `custom/invoice-builder-*` used the second reservation.

## Conclusion for the brief

All three owner complaints are reproduced and measured: cluttered builder, right-pinned item
rows with a whitespace gap at >=1024 px, invoice action hidden in the stay ⋮ menu. Brief 2001
fixes all three; after the fix these same screenshots must be re-taken at 390/768/1280.
