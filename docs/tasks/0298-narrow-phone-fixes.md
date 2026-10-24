# 0298: 360 px fixes: property cards with "Otevřít", invoice items stacking

Status: todo
Depends on: 0297 | Base commit: e960908 | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective

The orchestrator's full run found two 360 px faults from 0291/0295: (a) on the property Overview in Czech the cards are 5 px wider than the screen, because the card's "Otevřít" button now shows its text and the card row cannot shrink; (b) in the invoice items, the 0295 rule `tbody tr > td:last-child { grid-column: 4 }` still applies inside the ≤420 px container rule, adding a fourth column and misaligning qty/unit/price.

## 2. Context

- Failing: `tests/test_host_controls_browser.py`, `tests/test_host_ux_acceptance.py`, `tests/test_host_wide_geometry_browser.py` (property overview cs 360: scrollWidth 365), `tests/test_host_invoice_items_browser.py` (misaligned controls at 360 px).
- `App/app/static/host2.css` lines ~865-868 (verbatim):
  ```css
  @container (max-width: 420px) {
    .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .invoice-items-grid td.row-actions { grid-column: 1 / -1; text-align: left; }
  }
  ```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit + append | steps 1-2 |
| App/app/templates/base.html | edit | host2 key `?v=20261024-0298` |
| App/tests/static_versions.json | regenerate | `--write` |

## 4. Steps

1. Replace the second line inside that `@container (max-width: 420px)` block with:
   `  .invoice-items-grid td.row-actions, .invoice-items-grid tbody tr > td:last-child { grid-column: 1 / -1; text-align: left; }`
2. Append:
   ```css
   /* 0298: on narrow phones a card's Open drops under the text instead of widening the card. */
   @media (max-width: 639px) {
     .host-workspace .host-property-card { flex-wrap: wrap; min-width: 0; max-width: 100%; box-sizing: border-box; }
     .host-workspace .host-property-card > div { min-width: 0; flex: 1 1 10rem; }
     .host-workspace .host-property-card-open { margin-left: auto; }
   }
   ```
3. Bump the key, `--write` the manifest.

## 5. Do not touch

Everything outside §3.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_host_controls_browser.py tests/test_host_invoice_items_browser.py tests/test_host_ux_acceptance.py tests/test_host_wide_geometry_browser.py tests/test_static_versions.py tests/test_0252_touch_sweep_browser.py -q --tb=short 2>&1 | tail -30
```
If a test still fails, give the first assertion line in the report and stop (do not try other CSS).

## 7. Acceptance

- [ ] The §6 commands pass, or the failure is in the report.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0298-report.md` (200 tokens max), `Status: review`. One commit `0298: 360 px fixes`.
