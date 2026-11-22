# 2001: Wolt-simple invoice builder; Generate invoice on the stay page; item geometry

Status: review

## Result

- Builder: one 720 px lane of five flat cards; buyer fields two columns from 1024 px; item rows stack as labelled cards — description on its own line, then QTY, UNIT, UNIT PRICE (VAT for a payer), Remove at the card's right edge, `thead` `display:none`, labels from `data-label`. One action row: total, next number, Preview, `Issue invoice`.
- The heading (`.ui-ph`) shares that lane, so its edges line up with `.invoice-workspace`.
- Stay detail: `Generate invoice` / `Open invoice` is a `ghost` header button from 1024 px up, ⋮ carries it via `ph-only` below; `stay_cta()` stays the one primary. The row may wrap at 1024–1199 px.
- Docs: `invoices.md`, `stays.md`. Shots in `docs/tasks/screenshots-2001/after/`.

## Verification

- §6 (six files, `-x -rs`): 15 passed, **0 skipped**. Layout lint alone: 4 passed, 0 skipped, twice.
- Wide geometry 10, invoice items 5, static versions 3, autofill 19, go layout golden 1, `go test ./internal/hostweb/layout/` ok, `context_lint.py` OK.
- `test_invoice_*.py test_stay_fee*.py`: 1013 passed; 3 `test_stay_fee_*` shots fail on the hardcoded `/opt/cursor/artifacts` path, as on base.

## Deviations

1. §2 bullet 3 is a sketch: the form tag also carries `method`, `action`, `data-reservation-id`; all its hooks exist.
2. "Visible on the phone, no `ph-hide`" not honoured: lint rule 4 fires for a second visible action below 1024 px, where `.stay-head-cta` is a fixed bottom bar. Phone keeps it in ⋮.
3. Outside §3, one commented line each: the `base.html` cache key (`app2.css?v=20261121-invoice-2001c`), the 1024–1199 px wrap rule, a `.soft` tint for ≥1024 px on Cleaning (grey comes from `dashboard-calendar.css`, injected inside the body, so the button read as a second primary until it landed — the intermittent lint `double-primary`), `static_versions.json`, and the same key ported to `go/internal/hostweb/layout/shell.html` with its two goldens, as `test_go_layout_golden.py` requires.
4. Buyer fields two columns at ≥1024 px, not six: six broke every label onto two lines.

## Still red, not from this brief

- `test_go_dashboard_golden` renders today's date; the diff is date cells only and `main`'s latest run fails the same job. Regenerating bakes today's date and breaks tomorrow.
- `postgres full shard 1` flaked once on `test_door_code_handover` (8 passed locally; door-code code untouched).

## Owner review

1. Shots are committed and described; the §5/§5b checklist is ticked in the PR body.
2. `test_host_invoice_items_browser.py` is green by conforming to it — hidden `thead`, stacked rows, heading in the lane, the reading `invoices.md` already carried.
3. No merge, nothing to main, PR #1244 untouched.
