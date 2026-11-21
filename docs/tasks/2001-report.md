# 2001: Invoice builder Wolt-simple; Generate invoice on the stay page; items-row geometry

Status: review

## Result

- Builder: one 720 px lane of five section cards (supplier, customer, items, payment, language folded). Buyer fields are `field_pair`, two columns from 768 px. Item rows are one line from 480 px up, column labels above their own columns, Remove last; below 480 px labelled cards. One action row: total, next number, Preview, `Issue invoice`. No floating bar, no per-section Save.
- Stay detail: `Generate invoice` / `Open invoice` is a `ghost` button in the header row from 768 px up; the ⋮ menu keeps the same item via `ph-only` on a phone. `stay_cta()` is still the page's one primary.
- Docs: `invoices.md`, `stays.md`. No new i18n key. Shots in `docs/tasks/screenshots-2001/after/`.

## Verification

- §6 command (six files, `-x -rs`): 15 passed, **0 skipped**.
- `test_layout_lint_browser.py` alone: 4 passed, 0 skipped.
- `scripts/context_lint.py`: OK (warnings only).
- `test_invoice_*.py test_stay_fee*.py`: 1013 passed; 3 `test_stay_fee_*` shot cases fail on the hardcoded `/opt/cursor/artifacts` path (same on this branch's base commit).
- `test_invoice_autofill.py`: 19 passed. Its 320/390 px inset guardrail caught the flat supplier/customer sections; fixed by keeping the standard card.

## Deviations

1. §2 bullet 3 is a sketch, not a literal line: the form tag carries `method`, `action`, `data-reservation-id`. All its class hooks exist; none removed.
2. "Visible on the phone, no `ph-hide`" not honoured: layout lint rule 4 (`action-row-orphan`) fires for a second visible action in `.stay-head-actions` below 1024 px, where `.stay-head-cta` is a fixed bottom bar, and the fix is outside §3. Header shows it from 768 px, the phone keeps it in ⋮.
3. Item columns are fixed widths (72/88/110/76/82) plus `display:contents`, not `repeat(4,minmax(0,auto)) auto`: the prescribed template collapsed the description to 38 px in the 720 px lane and pushed Remove out of its cell.
4. Buyer fields are two columns at ≥1024 px, not six: six put every label on two lines.

## Red checks needing an owner decision

- `test_host_invoice_items_browser.py` fails twice: it wants `thead` `display:none` at 1024 px (the brief shows the labels) and heading and workspace to share both edges (the lane is 720 px). Green on base; the file is outside §3.
- `test_design_guardrails_browser.py`: `guest-new` 390 Cancel 43×44 — fails on base too.

## Owner review

1. Open the PR; the 390/768/1280 shots are committed and the design-system §5/§5b checklist is ticked in the body.
2. Decide the two stale geometry assertions in `test_host_invoice_items_browser.py`.
3. No merge, nothing to main, PR #1244 untouched.
