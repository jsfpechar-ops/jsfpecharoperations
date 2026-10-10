# 0035 — Align host invoice items and show Other description conditionally

Status: review
Report: docs/tasks/0035-host-invoice-items-report.md

## 1. Objective

Align the item headers, optional stay line and every extra row in the existing
invoice builder. Show the custom Description field for Other only and retain
its value when switching kinds. Keep Cleaning Unit optional and blank by
default. Preserve the existing item names/order, extra cap, VAT behavior,
totals, validation, issued snapshots and PDF behavior.

## 2. Context

Read [repository instructions](../../AGENTS.md) and
[current status](../context/status.md), then the approved design anchors:

- [Action geometry](../DESIGN.md#action-geometry) and
  [Invoice items](../DESIGN.md#invoice-items-retain-the-simple-layout).
- [Host app invoices](../HOST_APP_DESIGN.md#7-invoices).
- [Host control polish §6](../plans/host-control-polish.md#6-invoice-generator-requested-fix-and-layout-discussion)
  and [§12](../plans/host-control-polish.md#12-revised-geometry-copy-and-notification-review).

The standalone `invoice-new` page in `docs/plans/host-control-review.html` is
a visual reference only. Existing application behavior and server rules remain
authoritative.

## 3. Files

- `App/app/templates/invoice_form.html`: item markup, template-local styles and
  the existing inline script.
- `App/tests/test_invoice_stay_browser.py` only if needed for the shared
  browser launch fixture.
- `App/tests/test_host_invoice_items_browser.py`: focused item behavior and
  geometry coverage.
- `docs/tasks/0035-host-invoice-items.md` and `docs/tasks/0035-host-invoice-items-report.md`.
- `docs/tasks/0035-evidence/`: synthetic browser screenshots.

## 4. Steps

1. Use one shared column grid for headers and every line, reserve the removal
   track, align Quantity/Unit/Unit price control tops, and give stay and extra
   Unit price controls equal widths.
2. Stack the controls into readable cards based on available table width, with
   no horizontal overflow at narrow viewport or embedded widths.
3. Add a labelled Other Description field. Toggle it locally per row after
   JavaScript initializes; preserve its value and keep the input enabled.
   Leave it visible in the no-JavaScript fallback so the existing server
   mapping remains usable.
4. Preserve blank Cleaning Unit and the current stay line, three-extra limit,
   VAT, quantity/price, validation, snapshots and PDF behavior.
5. Run the commands below and record outcomes and screenshots in the report.

## 5. Do not touch

Do not modify shared styles/scripts, invoice handlers or validation, invoice
data mapping, translations, database/schema or PDF code. Do not add a
dependency or change invoice defaults, row order, VAT, limits or issued
snapshots. Do not use real customer data in screenshots.

## 6. Commands

From `App/`, run the relevant invoice functional tests:

```sh
.venv/bin/python -m pytest tests/test_invoice_corrections.py tests/test_invoice_entity.py tests/test_invoice_immutability.py tests/test_invoice_numbering.py tests/test_invoice_pdf.py tests/test_invoice_settings.py tests/test_invoice_stay_pages.py tests/test_invoice_stay_rules.py tests/test_invoice_ux.py tests/test_invoice_vat.py tests/test_invoice_workspace.py -q
```

Run browser acceptance with required Chromium enabled and save screenshots:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/workspace/jsfpecharoperations/docs/tasks/0035-evidence .venv/bin/python -m pytest tests/test_invoice_stay_browser.py tests/test_host_invoice_items_browser.py -q
```

From the repository root, run `python3 scripts/context_lint.py` and
`git diff --check`.

## 7. Acceptance

- Headers and line rows share one column layout with a reserved removal track.
  Header cells, including the blank removal cell, share one height and form a
  continuous band. Stay and extra Unit price widths match; Quantity, Unit and
  Unit price controls start at the same vertical position. Remove matches the
  adjacent control height and aligns at the same top on desktop.
- Narrow viewport and embedded table layouts are readable and do not overflow.
- Other Description appears for restored and new Other rows, hides for other
  kinds, and retains text through Other → Cleaning → Other. Hidden inputs stay
  enabled and in their original row mapping.
- No-JavaScript fallback keeps a labelled description available, and the
  server continues to decide which description becomes the invoice item.
- Cleaning Unit remains blank and optional. Existing extra cap, VAT,
  quantities, prices, validation, stay line, issued snapshots and PDF behavior
  remain intact.
- Relevant functional and browser tests pass with zero skips. Capture English
  and Czech screenshots at 360, 390 and 1280 CSS px, plus embedded mobile
  width; record actual commands and results in `0035-host-invoice-items-report.md`.

## 8. Stop and ask

Stop only if implementation requires changing a file outside §3, changing
server/data mapping or validation, adding a dependency, or revising an approved
invoice rule. Report the exact blocker and affected file; do not broaden scope.

## 9. Report

Write `docs/tasks/0035-host-invoice-items-report.md` with the changed behavior, actual test
commands and counts, screenshots, and any unresolved failures. Keep the report
limited to this task's files and results.
