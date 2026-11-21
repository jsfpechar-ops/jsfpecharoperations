# 2001: Invoice builder Wolt-simple; Generate invoice on the stay page; items-row geometry fix

Status: todo
Depends on: none | Base commit: fa85ae1a | Branch: task/2001-invoice-wolt-simple
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner finds the invoice builder (`/invoices/new`, `invoice_form.html`) ugly and wants it simple, Wolt-style (see `docs/design/design-system.md` "Look: Wolt style"). Three concrete asks: (a) simplify the builder page, (b) put the Generate invoice button on the stay page header, not in the ⋮ overflow menu, (c) fix the items rows whose numeric cells sit at the far right with a big white gap after the description.

## 2. Context

Rules: `docs/design/design-system.md` (read it first; rules 1, 4, 5, 7, 9, 10 and §5b apply), `docs/design/MASTER.md`, add-ons `docs/design/pages/invoices.md` and `docs/design/pages/stays.md`. AGENTS.md rules 6, 7, 10 (UX gate: run `test_layout_lint_browser.py` green, open 390/768/1280 screenshots of each touched page, describe per page in the PR, tick the design-system checklist).

Exact excerpts (verify verbatim; if not found, STOP §8):

- Stay detail, invoice hidden in the ⋮ menu — `App/app/templates/reservation_detail.html:79`:
  `{% if stay_invoice %}<a class="row-menu-item" href="/invoices/{{ stay_invoice.id }}" role="menuitem">{{ t('invoice.stay.open', number=stay_invoice.number) }}</a>{% else %}<a class="row-menu-item" href="/invoices/new?reservation_id={{ reservation.id }}" role="menuitem">{{ t('invoice.new') }}</a>{% endif %}`
  The header action row is `.stay-head-actions` / `.stay-head-cta` at ~line 72-75; the page's one primary stays `stay_cta()`.
- Items-row geometry — `App/app/static/app2.css` (0831H block):
  `body.v2 .invoice-items-grid tbody tr { display: grid; grid-template-columns: minmax(220px, 1fr) 84px 124px 148px 78px 126px; align-items: start; }`
  and `body.v2 #item-rows.invoice-items-grid { max-width: 850px; }`
  The fixed trailing columns (84+124+148+78+126 px) pin QTY/UNIT/PRICE/VAT/actions to the right edge; the `minmax(220px,1fr)` description column stretches, leaving the whitespace gap the owner sees in the screenshot.
- Builder structure — `App/app/templates/invoice_form.html`: `<form class="invoice-form">` > `.invoice-workspace` > `.invoice-document` with `.ui-section` blocks (`.invoice-supplier`, `.invoice-customer`, items `table#item-rows.invoice-items-grid`, payment) and a closing `.invoice-actions` bar with `.invoice-total`, `[data-next-number]`, Preview (`secondary`) and Issue (`primary`).
- Copy keys: `invoice.new` = "Issue invoice" (`App/app/host_i18n.py:1884` en, `:4091` cs) and "Generate invoice" (`App/app/host_design_i18n.py:43` en, `:84` cs). Reuse existing keys; if a new key is needed, add CS and EN together in both files, no em dash.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/invoice_form.html` | edit | simplify builder markup per §4.2 |
| `App/app/static/app2.css` | edit | only the `body.v2 .invoice-*` / `#item-rows` blocks (0831H region); fix items-row grid |
| `App/app/templates/reservation_detail.html` | edit | invoice action into header, out of ⋮ |
| `App/app/host_i18n.py`, `App/app/host_design_i18n.py` | edit only if a new key is unavoidable | CS+EN together |
| `docs/design/pages/invoices.md`, `docs/design/pages/stays.md` | edit | reflect the new builder layout and the stay header button |
| Tests (read/run only): `App/tests/test_design_invoices.py`, `test_0293_invoice_form.py`, `test_design_stays.py`, `test_host_geometry.py`, `test_host_controls_browser.py`, `test_layout_lint_browser.py` | run | per §6 |

No other file may change.

## 4. Steps

1. **Stay page button.** In `reservation_detail.html`, add a visible secondary button in `.stay-head-actions` (next to the existing copy-link button): when `stay_invoice` exists it links to `/invoices/{{ stay_invoice.id }}` with `t('invoice.stay.open', number=...)`; otherwise to `/invoices/new?reservation_id={{ reservation.id }}` with `t('invoice.new')`. Use the same button class as the neighbouring copy-link button (`btn ghost`/`btn` as appropriate). Remove the invoice line from the ⋮ `row_menu` (line 79). Owner decision 2026-11-21: the button stays visible on phone too (do not add `ph-hide`); it is a secondary, so the page still has exactly one primary (`stay_cta`). Update `docs/design/pages/stays.md` Stay detail bullet: secondary actions become `Edit stay`, `Invoice` (header), menu drops Invoice.
2. **Builder simplification (Wolt style).** In `invoice_form.html` + the `body.v2 .invoice-*` CSS: one narrow form lane (720 px, reuse the existing `ui-page-narrow`/lane rules — do not invent widths), each section one flat card (`ui-section` as today is fine; no card-in-card), single column of fields on phone, `field_pair`-style two-column only from 768 px (the existing `invoice-buyer-fields` media queries already do this — keep them). Keep exactly one action row at the bottom of the form: live total + next number + Preview (`secondary`) + Issue invoice (the one `primary`). No floating bar, no Save-per-section. Move any hint/description lines under the label's help "?" (rule 7); add no new copy.
3. **Items-row geometry.** Replace the fixed 6-column grid on `#item-rows.invoice-items-grid` tbody rows. Desktop (≥1024 px): `grid-template-columns: minmax(0,1fr) repeat(4, minmax(0,auto)) auto` with the qty/unit/price/vat inputs at their natural small widths (keep `input-qty`/`input-unit`/`input-vat`/`input-price` max-widths) and the remove button last — description takes the remaining width, numerics sit right after it, no trailing whitespace gap. Remove the `max-width: 850px` cap on `#item-rows`. Below 768 px keep/extend the stacked card layout (rule 10): description full width, then the numeric fields and Remove in a wrap row, labels via the existing `data-label` ::before. Keep the VAT column hidden logic (`[data-vat-col][hidden]`) working. Do not touch the `<script>` behaviour (add/remove item, live total) — class hooks (`data-item-row`, `data-remove-item`, `data-add-item`, `.input-qty` etc.) must keep working; `test_0293_invoice_form.py` covers them.
4. **Docs.** Update `docs/design/pages/invoices.md` builder bullet to describe the simplified single-lane card layout and stacked item rows.
5. **Verify.** Run the tests in §6, then produce and open 390/768/1280 px screenshots of `/invoices/new` and `/reservations/{id}` (existing screenshot tooling in `docs/tasks/screenshots-*` or the browser test harness — find how previous briefs did it, e.g. `docs/tasks/ux-remediation-handoff.md`), inspect them, and write per page in the PR what you saw (AGENTS.md rule 10). Tick the design-system checklist in the PR body.

## 5. Do not touch

`App/app/routes/invoices.py` logic, `invoice_pdf.py`, payments, guest/public pages, `App/app/static/app.css` (legacy; v2 rules live in `app2.css`), no new dependencies, light mode only, no `<style>`/`style=""`/raw hex in templates (design-system rule 2), never push to main.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_design_invoices.py tests/test_0293_invoice_form.py tests/test_design_stays.py tests/test_host_geometry.py tests/test_host_controls_browser.py tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30` (read the "Invoices, stay fee" and geometry rows of `docs/context/test-map.md` first; add a row file only if the test-map names one). From repo root: `python3 scripts/context_lint.py 2>&1 | tail -20`.

## 7. Acceptance

- [ ] Stay detail header shows the Invoice button (secondary) at 390/768/1280; ⋮ menu no longer has an invoice item; still exactly one primary on the page.
- [ ] `/invoices/new` is a single narrow lane of flat section cards; items rows show description + numeric cluster with no trailing whitespace gap; below 768 px rows stack as cards.
- [ ] One action row at the form end: total, next number, Preview (secondary), Issue invoice (primary).
- [ ] `test_layout_lint_browser.py` green with 0 skipped; listed tests pass; 390/768/1280 screenshots of both pages inspected and described in the PR; design-system checklist ticked.

## 8. Stop and ask

Stop and write the report if: an excerpt above is not found verbatim; a test fails twice; you reach 25 tool calls or ~50k tokens; a file outside §3 seems needed; §5 would be touched; a step is unclear; you need push/merge/deploy (owner).

## 9. Report

Write `docs/tasks/2001-report.md` (≤600 tokens), set `Status: review`, open one PR. Report: `git diff --stat`, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps.

## Risk list (for the reviewer)

`App/app/templates/invoice_form.html`, `App/app/static/app2.css` (0831H invoice blocks), `App/app/templates/reservation_detail.html`.

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh` once CI is green.
2. Open a stay, check the Invoice button sits in the header (not ⋮), open `/invoices/new`, check the rows at 390 and 1280 px.
