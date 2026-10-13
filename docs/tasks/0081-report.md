# 0081 report: invoice navigation

Base 4dd10e0 (coordinator branch merged fast-forward). Layout/navigation only; no route, schema, numbering, VAT, rounding or snapshot change. Brief §2 anchors (`reservation_id` query, `active_invoice_for_stay`) untouched.

## Changes
- `invoices.html`: Invoice settings link next to Generate invoice (list, filters, PDF, period control unchanged).
- `invoice_stay_picker.html`: `?` help (shared `field_label`, `aria-describedby="reservation_id-help"`), Invoice settings link beside "add stay".
- `invoice_form.html`: stay context line with "Open stay" link; items hint moved into a `?` tip (`help_tip`); Language/Note no longer folded in `<details>` (same names `lang`, `note`). Supplier select, Edit invoice details link (entity + safe `next`), item grid, ARES, CSRF, Preview/Issue unchanged.
- `invoice_detail.html`: Open stay and Invoice settings (returns to the invoice) in the command actions; "Paid on" fact only when a payment was manually recorded (`paid_on`/`marked_paid_at`); download/send/mark-paid/cancel unchanged (cancel stays the existing confirmation `<details>`).
- `host.css`: one `/* 0081 */` block. `host_i18n.py`: `# 0081` keys, EN+CS. `_components.html`, `_host_navigation.html`: untouched.

## Tests (staging/mock/REQUIRE_BROWSER)
- New `tests/test_host_invoice_navigation.py`: 4 pass (links, no folded options, field names, paid fact, 360/390/1280 EN/CS no overflow, actions inside viewport).
- `tests/test_invoice*.py tests/test_host_invoice*.py test_host_i18n test_privacy_first`: 116 passed, 1 skipped (`test_invoice_autofill`, env-gated UBYHOST_SHOTS_DIR screenshot, pre-existing). ruff selected rules clean.
- Not run: full suite/coverage.

## Deviations
- `tests/test_invoice_workspace.py` (outside §3): `test_language_and_note_hide_behind_more_options` asserted the folded `<details>`; updated to assert visible (combined plan §4.2 wins).
- Key `invoice.more_options` now unused (left in catalog).

## Evidence
`docs/tasks/0081-evidence/{list,picker,builder,detail}-{en,cs}-{360,390,1280}.png` (synthetic data, UBYHOST_CAPTURE_0081=1). Not measured: widths to 2048, collapsed rail.
