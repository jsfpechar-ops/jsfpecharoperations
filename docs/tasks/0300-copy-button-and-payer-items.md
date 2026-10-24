# 0300: One copy button (the tick replaces the icon); VAT-payer item rows keep Remove on the line

Status: todo
Depends on: 0299 | Base commit: 8e15a05 | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

(a) Owner, 2026-10-24 (screenshots from Settings › Guest experience): after copying, a coral tick badge sits **on top of** the still-visible copy icon, and copy buttons differ (some borderless, some bordered). Every icon copy button becomes one bordered component, and on success the copy icon is **replaced** by a green tick in the same place (same size, nothing moves), then returns after 1.6 s (app.js timer, unchanged). (b) For a VAT-payer operator the invoice item row has a 4th control (VAT), so 0295's fixed `grid-column: 4` pushes Remove to its own line (`tests/test_host_invoice_items_browser.py` fails at 760 px: Remove 85 px below the controls).

## 2. Context

- `App/app/templates/_components.html` lines ~290-294 (verbatim):
```jinja
{% macro copy_button(target_id) %}
  <button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact" type="button" data-copy="{{ target_id }}"
          data-copy-label="{{ t('common.copy') }}" data-copied-label="{{ t('common.copied') }}"
          aria-label="{{ t('common.copy') }}">{{ icon('copy', 16) }}<span class="btn-icon-label" data-copy-label-slot hidden></span></button>
{% endmacro %}
```
- `App/app/templates/apartments.html` lines ~91-92 and ~102-103: two hand-written `<button class="btn-icon" type="button" data-copy="guest-url-…">{{ copy_icon() }}<span class="sr-only">…</span></button>` and `data-copy="guest-pin-…"` (the PIN one inside `{% if apartment.permalink_pin %}…{% endif %}`).
- app.js `prepareCopyControl` appends `<span class="copy-state-icon" data-copy-state-icon aria-hidden="true"><svg>…</svg></span>` to every `[data-copy]` button and toggles class `copied` for 1.6 s. host.css lines ~385-406 style it as a 20 px coral badge at top-right (`#ef6b58`) and turn the button coral. Do not edit app.js or host.css; override in host2.css.
- host2.css, the 0295 block: `@container (max-width: 850px) { … .invoice-items-grid td.row-actions,\n  .invoice-items-grid tbody tr > td:last-child { grid-column: 4; text-align: right; } … }`. JS adds `is-payer` on `.invoice-workspace` for a VAT payer; then the VAT `<td data-vat-col>` is visible.
- Tokens: `--green-700`, `--green-100`, `--line-strong`, `--surface`, `--ink-2`, `--radius-md`, `--control-h-compact`. Lint: no raw colours, no bare px except 0 and 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | step 1 |
| App/app/templates/apartments.html | edit | step 2 |
| App/app/static/host2.css | edit + append | steps 3-4 |
| App/app/templates/base.html | edit | host2 key `?v=20261024-0300` |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0300_copy_button.py | new | step 5 |

## 4. Steps

1. Macro becomes (label param optional; class secondary so it has a border):
```jinja
{% macro copy_button(target_id, label='') %}
  <button class="ui-btn ui-btn-secondary ui-btn-icon ui-btn-compact copy-btn" type="button" data-copy="{{ target_id }}"
          data-copy-label="{{ label or t('common.copy') }}" data-copied-label="{{ t('common.copied') }}"
          aria-label="{{ label or t('common.copy') }}">{{ icon('copy', 16) }}<span class="btn-icon-label" data-copy-label-slot hidden></span></button>
{% endmacro %}
```
2. apartments.html: replace the two hand-written copy buttons with `{{ copy_button('guest-url-' ~ apartment.id, t('common.copy_link')) }}` and `{{ copy_button('guest-pin-' ~ apartment.id, t('properties.inline.copy_pin')) }}` (keep the PIN one inside its `{% if %}`). Check that `copy_button` is in the template's `{% from "_components.html" import … %}` line; add it if missing.
3. host2.css 0295 block: change `grid-column: 4;` to `grid-column: -2 / -1;` and add, inside the same `@container (max-width: 850px)` block:
   `  .invoice-workspace.is-payer .invoice-items-grid tbody tr { grid-template-columns: repeat(4, minmax(0, 1fr)) auto; }`
   (the ≤420 px block already sends Remove to its own line; leave it).
4. Append to host2.css:
```css
/* 0300: one copy button (owner 2026-10-24). Bordered, 32 px; on success the
   copy icon is replaced in place by a green tick, then comes back. */
.host-workspace .copy-btn { position: relative; width: var(--control-h-compact); min-width: var(--control-h-compact); height: var(--control-h-compact); padding: 0; border: 1px solid var(--line-strong); border-radius: var(--radius-md); background: var(--surface); color: var(--ink-2); }
.host-workspace .copy-btn [data-copy-label-slot] { display: none; }
.host-workspace .copy-btn [data-copy-state-icon] { inset: 0; top: 0; right: 0; width: auto; height: auto; border: 0; border-radius: inherit; background: transparent; color: var(--green-700); transform: none; }
.host-workspace .copy-btn [data-copy-state-icon] svg { width: 16px; height: 16px; }
.host-workspace .copy-btn.copied { color: var(--green-700); border-color: var(--green-700); background: var(--green-100); }
.host-workspace .copy-btn.copied > svg { visibility: hidden; }
```
   If the S2 lint flags `16px` in `width/height`, use `1rem`.
5. New `App/tests/test_0300_copy_button.py`: with the `host_with_property` fixture (as in `tests/test_design_dashboard.py`), GET `/apartments?lang=en`: `page.count('class="btn-icon" type="button" data-copy=') == 0` and `'copy-btn' in page`; and read `App/app/templates/_components.html` text: `'ui-btn-quiet ui-btn-icon ui-btn-compact" type="button" data-copy' not in text`.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_0300_copy_button.py tests/test_host_invoice_items_browser.py tests/test_host_controls_browser.py tests/test_static_versions.py tests/test_design_lint.py tests/test_0285_rows_browser.py -q --tb=short 2>&1 | tail -30
.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -3
```
A test that pins the old coral copy badge: report it with its assertion line, do not loosen it.

## 7. Acceptance

- [ ] Every icon copy button renders through `copy_button`; copied state shows only the green tick.
- [ ] Invoice items browser test passes.

## 9. Report

`docs/tasks/0300-report.md` (300 tokens max), `Status: review`. One commit `0300: one copy button, payer item rows`.
