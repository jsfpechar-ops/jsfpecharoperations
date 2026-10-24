# 0294: "Open" at the row's right edge; give the last button groups their one primary

Status: todo
Depends on: 0293 | Base commit: the 0293 commit | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The 0291 review found the soft-coral "Open" sitting right after the name in some tables, so it looks like a badge and does not line up from row to row. Like "Send the guest link" on the dashboard, Open belongs at the row's right edge, in the actions cell (as Stays already does). The review also found three button groups with no highlighted button.

## 2. Context

Review findings (tool `/mnt/project-files/button-states/tools/review_0291.py`):
- `/stay-fees` table and `/apartments` property-summary table: `{{ row_open() }}` follows the name link inside the first `<td>`, so it is not aligned.
- `/entities`: rows show Open after the name **and** `Edit | Invoice settings` buttons with no highlighted one. Edit opens the same page as the row, so Edit becomes the highlighted one and the extra Open goes.
- `/reservations/<id>`: `stay-command-actions` shows `Edit count | New invoice` with no primary when the page has no send/fix/report CTA; the guests block `ui-form-actions` shows `Edit count | + Add a guest` with no primary.

Exact lines (verify each before editing; if one is not found verbatim, STOP):
- `App/app/templates/stay_fees.html` line ~123: `<a class="row-primary-link" href="{{ fee_settings_url(apartment.id, fee_return) }}">{{ apartment.internal_name }}</a> {{ row_open() }}` and line ~141 `… {{ apartment.internal_name }}</a> {{ row_open() }}`; their rows' last cell is `<td class="nowrap row-actions" data-label="">` (lines ~130, ~137 hold a "Set up" button; line ~171 holds `{{ row_menu_begin() }}`).
- `App/app/templates/apartments.html` line ~84: `<a class="row-primary-link" href="{{ base_url }}">{{ property_identity(apartment.id, apartment.internal_name) }}</a> {{ row_open() }}` (property-summary table). Find that row's `row-actions` cell (grep `row-actions` after line 84; if the row has no actions cell, STOP and report).
- `App/app/templates/entities.html` line ~83 and ~128: `<a class="row-primary-link" href="/entities?edit={{ entity.id }}">{{ entity.name }}</a> {{ row_open() }}`; line ~93: `<a class="ui-btn ui-btn-secondary ui-btn-compact" href="/entities?edit={{ entity.id }}">{{ t('common.edit') }}</a>`.
- `App/app/templates/reservation_detail.html` line 7 `{% set cta = 'ui-btn ui-btn-primary' %}`; lines ~129-131 the two `ui-btn ui-btn-secondary` invoice links inside `stay-command-actions`; line ~182 `<div class="ui-form-actions"><a class="ui-btn ui-btn-secondary ui-btn-compact" href="#stay-quick-edit" data-open-details>…</a><a class="ui-btn ui-btn-secondary ui-btn-compact" href="/reservations/{{ reservation.id }}/guests/new">+ …`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/stay_fees.html | edit | step 1 |
| App/app/templates/apartments.html | edit | step 2 |
| App/app/templates/entities.html | edit | step 3 |
| App/app/templates/reservation_detail.html | edit | step 4 |
| App/app/static/host2.css | edit/append | step 5 |
| App/app/templates/base.html | edit | host2 key `?v=20261024-0294` |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0285_rows_browser.py | edit | step 6 |
| App/tests/test_0291_open_buttons.py | append | step 6 |

No other file may change, except a test that pinned Open inside the name cell (report each).

## 4. Steps

1. stay_fees.html: in both name cells delete ` {{ row_open() }}` (keep the link). In each of those rows' `row-actions` cell put `{{ row_open() }}` as the first thing inside the `<td>`; where the cell already has a "Set up" `ui-btn` link, do **not** add row_open (that link is the row's action) but change its class from `ui-btn-secondary` to `ui-btn-open`.
2. apartments.html line ~84 (property-summary table): delete ` {{ row_open() }}` after the link and add nothing (orchestrator 2026-10-24: that table is the guest link / PIN / timing settings list; the Properties table above already has Open in its actions cell, and this row has no actions cell). In step 6, drop the property-summary `gap`/`sameLine` check from test_0285 instead of rewriting it.
3. entities.html: delete ` {{ row_open() }}` in both places (~83, ~128). Change the Edit link at ~93 from `ui-btn ui-btn-secondary ui-btn-compact` to `ui-btn ui-btn-open ui-btn-compact`. In the archived table (~128) add `{{ row_open() }}` as the first thing in its `row-actions` cell.
4. reservation_detail.html:
   - Directly before `<div class="stay-command-actions">` add `{% set cmd_primary = send_controls.send_enabled or progress.status == 'failed' or (progress.status == 'reported' and submissions) %}`.
   - In the two invoice links inside that div, replace `class="ui-btn ui-btn-secondary"` with `class="{{ 'ui-btn ui-btn-secondary' if cmd_primary else cta }}"`.
   - Line ~182: change the "+ Add a guest" link class to `ui-btn ui-btn-open ui-btn-compact`.
5. host2.css: delete the two rules that only placed Open after the name, if present: `.host-workspace .property-summary-table td:first-child .row-primary-link + .row-open { margin-left: var(--space-3); }` and `.host-workspace .lc-entities tbody td.col-name .row-primary-link + .row-open { margin-left: var(--space-3); }`; and set the `max-width` of `.property-summary-table td:first-child .row-primary-link` and `.lc-entities tbody td.col-name .row-primary-link` back to `none`. Append:
   ```css
   /* 0294: Open sits at the row's right edge, before the ⋮ menu. */
   .host-workspace td.row-actions > .row-open { vertical-align: middle; }
   .host-workspace td.row-actions > .row-open + .row-menu,
   .host-workspace td.row-actions > .row-open + .ui-btn { margin-left: var(--space-2); }
   ```
6. Tests:
   - `test_0285_rows_browser.py`: the two blocks that measure `gap`/`sameLine` between `.row-primary-link` and `.row-open` (property-summary and entities) now check instead that every visible `.row-open` / `.ui-btn-open` in those tables lies inside `td.row-actions` (`o.closest('td.row-actions') !== null`). Keep the `contact` table-cell check for entities.
   - Append to `test_0291_open_buttons.py`: `/entities?lang=en` contains `ui-btn ui-btn-open ui-btn-compact` and the text between `class="row-primary-link"` and the next `</td>` never contains `row-open`; same "never in the name cell" check for `/stay-fees?lang=en`.

## 5. Do not touch

Routes, i18n, the Stays list (`reservations.html`), the fee step cards (0292).

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_0291_open_buttons.py tests/test_0285_rows_browser.py tests/test_0252_touch_sweep_browser.py tests/test_host_list_layouts_browser.py tests/test_design_*.py tests/test_host_stay*.py tests/test_stay_fee*.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
```

## 7. Acceptance

- [ ] No `row-open` inside a name cell on /stay-fees, /apartments, /entities.
- [ ] Entities Edit is `ui-btn-open`; stay page invoice link is primary only when no other CTA; Add a guest is `ui-btn-open`.
- [ ] Key bumped; tests run, failures listed.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0294-report.md` (600 tokens max), `Status: review`. One commit: `0294: Open at the row edge, missing primaries`.

## Risk list (for the reviewer)

reservation_detail.html condition; host2.css removals.

## Owner steps

None.
