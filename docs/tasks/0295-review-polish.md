# 0295: Review polish: invoice item rows, IČO button height, visible Open border

Status: todo
Depends on: 0294 | Base commit: the 0294 commit | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three small fixes from the orchestrator's screenshot review of 0291-0293: (a) invoice item rows below 850 px container width leave "Remove" alone on its own line with a large empty band; put it on the same line as qty/unit/price. (b) The "Fill from register" button is shorter than the IČO input next to it; match the input height. (c) The soft-coral Open button's border (`--coral-200`) is invisible on its `--accent-soft` fill; the owner wants visible borders, so use `--coral-500`.

## 2. Context

- `App/app/static/host2.css`, the 0293 block at the end contains:
  ```css
  @container (max-width: 850px) {
    .invoice-items-grid tbody tr { gap: var(--space-2) var(--space-4); padding: var(--space-3) 0; }
    .invoice-items-grid td.row-actions { grid-column: auto / -1; text-align: right; }
  }
  ```
- The 0291 block contains the rule starting `.ui-btn-open,` … with `border: 1px solid var(--coral-200);`, and the 0284 hover line ends `{ background: var(--coral-200); border-color: var(--accent); }` (keep that one).
- The 0293 block has `.host-workspace .invoice-lookup-row .ui-btn { flex: 0 0 auto; }`.
- The stay row's last `<td></td>` in the items table has no class; it must not create an extra line either.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit | steps 1-3 |
| App/app/templates/base.html | edit | host2 key `?v=20261024-0295` |
| App/tests/static_versions.json | regenerate | `--write` |

No other file may change.

## 4. Steps

1. Replace the 0293 `@container` block above with:
   ```css
   @container (max-width: 850px) {
     .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)) auto; gap: var(--space-2) var(--space-3); padding: var(--space-3) 0; align-items: end; }
     .invoice-items-grid tbody tr > td:first-child { grid-column: 1 / -1; }
     .invoice-items-grid td.row-actions,
     .invoice-items-grid tbody tr > td:last-child { grid-column: 4; text-align: right; }
     .invoice-items-grid tbody tr > td:last-child:empty { display: none; }
   }
   @container (max-width: 420px) {
     .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)); }
     .invoice-items-grid td.row-actions { grid-column: 1 / -1; text-align: left; }
   }
   ```
2. Change `.host-workspace .invoice-lookup-row .ui-btn { flex: 0 0 auto; }` to `.host-workspace .invoice-lookup-row .ui-btn { flex: 0 0 auto; min-height: 0; height: auto; align-self: stretch; }` and add `.host-workspace .invoice-lookup-row { align-items: stretch; }`.
3. In the 0291 `.ui-btn-open, …` rule change `border: 1px solid var(--coral-200);` to `border: 1px solid var(--coral-500);`.
4. Bump the key, regenerate the manifest.

## 5. Do not touch

Templates, Python, other CSS blocks.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_0293_invoice_form.py tests/test_0291_open_buttons.py tests/test_static_versions.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Steps 1-4 done; tests pass or failures listed.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0295-report.md` (300 tokens max), `Status: review`. One commit `0295: review polish`.

## Risk list (for the reviewer)

The container rules.

## Owner steps

None.
