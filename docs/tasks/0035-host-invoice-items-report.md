# 0035 report — Host invoice items

Status: review

Updated the invoice builder template so headers and item rows share one fixed
column grid, with an always-reserved removal track and equal stay/extra price
widths. Header cells, including the blank removal header, now share a full
height continuous band. The Remove button matches the adjacent controls in
height and aligns with their top edge on desktop. Narrow tables switch to
labelled stacked cards based on their own available width. Other Description
is labelled and toggled per row; switching to Cleaning preserves the enabled
field value for the server's existing row-position mapping. Without
JavaScript, the labelled input stays visible. Cleaning Unit remains blank and
optional.

The existing server item handler remains unchanged. It uses custom text only
for Other and derives labels for other kinds. VAT, quantities, price handling,
the three-extra cap, validation, stay lines, issued snapshots and PDF behavior
remain covered by the existing invoice tests.

Validation from `App/`:

- `.venv/bin/python -m pytest tests/test_invoice_corrections.py tests/test_invoice_entity.py tests/test_invoice_immutability.py tests/test_invoice_numbering.py tests/test_invoice_pdf.py tests/test_invoice_settings.py tests/test_invoice_stay_pages.py tests/test_invoice_stay_rules.py tests/test_invoice_ux.py tests/test_invoice_vat.py tests/test_invoice_workspace.py -q` — **84 passed**.
- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/workspace/jsfpecharoperations/docs/tasks/0035-evidence .venv/bin/python -m pytest tests/test_invoice_stay_browser.py tests/test_host_invoice_items_browser.py -q` — **5 passed, 0 skipped** before the header/Remove sizing correction. After that CSS-only correction, the focused geometry test `tests/test_host_invoice_items_browser.py::test_invoice_item_geometry_and_localized_screenshots` passed (**1 passed, 0 skipped**) and refreshed the localized screenshots. The runs used the pinned Playwright package and system Chromium; sandboxed Chromium could not create its local socket, so browser runs used the approved escalated runtime.
- `git diff --check` — passed.
- `python3 scripts/context_lint.py` — 0035 passes brief recognition; the latest
  overall run remains blocked by parallel task 0037 missing its Status line,
  plus the host_i18n ordering and status freshness warnings. No 0035 lint error
  remains.

The browser run checked Other visibility and retained text through kind
switches, new rows, the no-JavaScript fallback, page overflow at 360/390/1280,
aligned Quantity/Unit/Unit price tops, equal stay/extra price widths, equal
header-cell heights and full removal-header coverage, Remove height/top
alignment, and a 390px embedded item table. Full-page screenshots return to
the top after browser focus moves the page to the item section. Synthetic
fixture screenshots are in
[`0035-evidence`](0035-evidence/):

- English: [360](0035-evidence/invoice-items-en-360.png), [390](0035-evidence/invoice-items-en-390.png), [1280](0035-evidence/invoice-items-en-1280.png), [390px embedded table](0035-evidence/invoice-items-embedded-en-390.png).
- Czech: [360](0035-evidence/invoice-items-cs-360.png), [390](0035-evidence/invoice-items-cs-390.png), [1280](0035-evidence/invoice-items-cs-1280.png), [390px embedded table](0035-evidence/invoice-items-embedded-cs-390.png).

No handler, shared stylesheet/script, translation, schema, PDF or production
file was changed for this task.
