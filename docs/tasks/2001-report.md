# 2001: Wolt-simple invoice builder; Generate invoice on the stay page; item geometry

Status: review

## Result

- Builder: one 720 px lane of five flat cards (supplier, customer, items, payment, language folded). Buyer fields two columns from 1024 px. Item rows stack as labelled cards at every width — description on its own line, then QTY, UNIT, UNIT PRICE (VAT for a payer) with Remove at the card's right edge; `thead` stays `display:none`, each cell prints its label from `data-label`. One action row: total, next number, Preview, `Issue invoice`.
- The heading (`.ui-ph`) shares that lane, so its edges line up with `.invoice-workspace`.
- Stay detail: `Generate invoice` / `Open invoice` is a `ghost` header button from 1024 px up, the ⋮ menu carries it via `ph-only` below; `stay_cta()` stays the one primary. The header row may wrap at 1024–1199 px.
- Docs: `invoices.md`, `stays.md`.

## Verification

- §6 (six files, `-x -rs`): 15 passed, **0 skipped**. `test_layout_lint_browser.py`: 4 passed, 0 skipped, twice.
- `test_host_wide_geometry_browser.py` 10, `test_host_invoice_items_browser.py` 5, `test_static_versions.py` 3, `test_invoice_autofill.py` 19 passed; `context_lint.py` OK.
- `test_invoice_*.py test_stay_fee*.py`: 1013 passed, 3 `test_stay_fee_*` shots fail on the hardcoded `/opt/cursor/artifacts` path, as on the base commit.

## Deviations

1. §2 bullet 3 is a sketch: the form tag also carries `method`, `action`, `data-reservation-id`. All its hooks exist.
2. "Visible on the phone, no `ph-hide`" not honoured: lint rule 4 fires for a second visible action below 1024 px, where `.stay-head-cta` is a fixed bottom bar. Header shows it from 1024 px, the phone keeps it in ⋮.
3. Outside §3, one commented line each: `base.html` cache key (`app2.css?v=20261121-invoice-2001c`), the 1024–1199 px wrap rule, a `.soft` tint for ≥1024 px on Cleaning (its grey lives in `dashboard-calendar.css`, injected from inside the body by the calendar partial, so the button read as a second primary until it landed — the intermittent lint `double-primary`), and `static_versions.json` regenerated.
4. Buyer fields two columns at ≥1024 px, not six: six broke every label onto two lines.

## Owner review

1. Shots in `docs/tasks/screenshots-2001/after/` are committed and described, and the design-system §5/§5b checklist is ticked in the PR body.
2. `test_host_invoice_items_browser.py` is green by conforming to it: hidden `thead`, stacked rows, heading in the lane — the reading `invoices.md` already carried.
3. No merge, nothing to main, PR #1244 untouched.
