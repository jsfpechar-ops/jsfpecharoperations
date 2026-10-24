# 0301: Invoice stay row: labels on one line again

Status: todo
Depends on: 0300 | Base commit: HEAD of claude/project-thread-1am307 | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 10 tool calls, 20k tokens

## 1. Objective

0295 set `align-items: end` on stacked invoice item rows so Remove lines up with the inputs. On the Accommodation (stay) row the price has a hint under it, so QTY and UNIT now sit lower than UNIT PRICE (orchestrator screenshot `/mnt/project-files/button-states/review-0300/payer-items-1280.png`). The stay row has no Remove, so it should align to the top.

## 2. Context

host2.css 0295 block, inside `@container (max-width: 850px) {`, the line starting `  .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)) auto;` ends with `align-items: end; }`. The stay row is `<tr data-item-row data-stay-row>`.

## 3. Files

| Path | Action |
|---|---|
| App/app/static/host2.css | add one line inside that container block |
| App/app/templates/base.html | host2 key `?v=20261024-0301` |
| App/tests/static_versions.json | `--write` |

## 4. Steps

1. Directly after that line add `  .invoice-items-grid tbody tr[data-stay-row] { align-items: start; }`.
2. Bump the key, regenerate the manifest.

## 5. Do not touch

Everything outside §3.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -10`

## 7. Acceptance

- [ ] The §6 commands pass, or the failure is in the report.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0301-report.md` (100 tokens), `Status: review`. One commit `0301: stay row aligns to top`.
