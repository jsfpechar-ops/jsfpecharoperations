# 0376: Phone row cards: Open on its own line, no grey strip over the content

Status: todo
Depends on: 0375 (merged) | Base commit: HEAD of origin/main | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Owner phone screenshot (Properties, 390 px, 2026-10-25): on a row card, the text "Open" button sits on top of the "Setup readiness" pill. The card's actions cell also lies over the right side of the card with its own grey background, which clips the property name ("Cozy Modern Apartment • Ba…") and the "SETUP READINES" label. When the card is pressed, the cells show as grey blocks.
Cause: 0200/0252 make `td.row-actions` an absolute column at the card's top-right, with `bottom: 0`, so it holds the ⋮ menu and the Open cue. This worked for the old 28 px circle, but Open is now a wider text button. The cell also inherits the card's background.
Wanted, on card lists below 1024 px:
- Open sits bottom-right on its own line, below every field.
- The actions cell has no background and does not block taps or clip anything.
- Cells never carry their own background.

## 2. Context

- `App/app/static/host.css` (~line 1558): `@media (max-width: 1023px) { .table-cards tr.clickable-row { position: relative; } .table-cards tr.clickable-row .row-open { position: absolute; right: 12px; bottom: 12px; } ... }`
- `App/app/static/host2.css` block starting `/* 0200: card lists (.table-cards, card layout below 720 px) with a row menu put the menu at the card's top-right corner */` (~line 604). `td.row-actions` is `position: absolute; top: 0; right: 0;` and, with `.row-open`, `bottom: 0`.
- Card rows have `padding: 14px 16px` (host.css `.lc-properties tr`, similar for other `lc-*` lists).
- Reproduce: from `App/`, `/mnt/project-files/design-reset/tools/seed.py` is used by `/tmp/claude-0/probe/press.py` (the orchestrator's probe). Run `App/.venv/bin/python /tmp/claude-0/probe/press.py /tmp/claude-0/probe/out` from the repo root to save `row-390.png` and `row-820.png` of the first Properties card.

## 3. Files

| Path | Action |
|---|---|
| App/app/static/host2.css | append one block |
| App/app/templates/base.html | host2 key `?v=20261025-0376` |
| App/tests/static_versions.json | `--write` |
| App/tests/test_0376_phone_card_open_browser.py | new |

## 4. Steps

1. Append to host2.css:
```css
/* 0376: on phone/tablet row cards the text "Open" gets its own line at the
   bottom right; the actions cell is see-through and never covers the fields;
   cells carry no surface of their own (owner 2026-10-25). */
@media (max-width: 1023px) {
  .host-workspace .table-cards tbody tr.clickable-row > td { background: transparent; }
  .host-workspace .table-cards tr.clickable-row > td.row-actions { pointer-events: none; }
  .host-workspace .table-cards tr.clickable-row > td.row-actions > * { pointer-events: auto; }
  .host-workspace .table-cards tr.clickable-row:has(.row-open) { padding-bottom: calc(var(--control-h-compact) + 24px); }
}
```
2. Bump the host2 key and run `.venv/bin/python tests/test_static_versions.py --write` from `App/`.
3. Write `tests/test_0376_phone_card_open_browser.py`. Model it on how `tests/test_0285_rows_browser.py` starts a live server, signs in and gets a browser (reuse its fixtures and imports). For widths 390 and 820, in `en` and `cs`, open `/apartments`. For each visible `table.properties-table tbody tr.clickable-row` in card layout (its `thead` is `display: none`), assert:
   - (a) the visible `.row-open` box does not intersect the box of any other visible `td` child's content (`strong, a, span, .pill, .ui-badge` inside the other tds). Use a 1 px tolerance.
   - (b) the `.row-open` top is ≥ the bottom of every other td (except `td.row-actions`) minus 1.
   - (c) `getComputedStyle(td).backgroundColor` is `rgba(0, 0, 0, 0)` for every td.
4. Run §6. Save `row-390.png` and `row-820.png` with the probe command from §2 and list their paths in the report.

## 5. Do not touch

Everything outside §3. No template changes.

## 6. Commands

From `App/`:
```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0376_phone_card_open_browser.py tests/test_0285_rows_browser.py tests/test_0252_touch_sweep_browser.py tests/test_host_controls_browser.py tests/test_host_ux_acceptance.py tests/test_properties_inline_controls_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -3
```
If a test fails, put its first assertion line in the report and stop (do not try other CSS).

## 7. Acceptance

- [ ] The §6 commands pass, or the failure is in the report.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0376-report.md` (200 tokens), `Status: review`. One commit `0376: phone row cards keep Open on its own line`, including this brief. Do not push.
