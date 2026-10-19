# 0141: Invoices (list, detail, form, stay picker) and the shared month filter on the v2 template

Status: todo
Depends on: 0140 | Base commit: 6c51d3f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit once, at step 10, as `0141: invoices and the shared month filter on host_page`. Never push, never open a PR. Page file: `docs/design/pages/invoices.md`.

Reconciled 2026-10-19 against the current code: every script below was dry-run on a copy of the tree at the base commit and printed `ok`; the tests in steps 7 and 8 were run on that copy. Run each script exactly as written; do not retype the strings.

## 1. Objective

Move the four invoice templates onto `host_page.html` (list, detail, form, stay picker), convert the shared `_list_filter.html` partial (used by Invoices and Stay fees) to the v2 toolbar, and move the invoice-items `<style>` block into `host2.css` with tokens. Invoice numbers, PDF routes, ARES fill, the item grid JS (`data-add-item`, `data-remove-item`, `data-vat-col`, `#item-rows`) and field names do not change.

## 2. Context

Rules: MASTER 5 (list, detail, form kinds), 5.3 (toolbar), 7.2, 7.4, 7.13, 4. `app.js` keys on `[data-filter-panel]`, `[data-filter-toggle]`, `[data-filter-summary]`, `[data-filter-cancel]`, `[data-month-picker]` and its `data-month-*` hooks, `.clickable-row`, `[data-add-item]`, `[data-remove-item]`, never on `.btn`, `.pill` or `.field`. The month picker buttons (`month-step`, `month-trigger`, `year-step`, `month-choice`, `month-all-dates`) keep their legacy classes; `host.css` styles them through those classes (`.host-workspace .list-filter .month-step`, `.host-workspace .month-trigger`, `.host-workspace .year-step`), not through `.btn`, so only the `btn` token changes.

How the migrated pages do it (copy this, nothing else): `reservations.html` and `reservation_detail.html` extend `host_page.html`, set `nav` and `body_kind`, and put every `{% from ... import ... %}` at the top level **before** the first block (an import inside `{% block body %}` is invisible to `primary_action` and `tabs`). Blocks available in `host_page.html`: `title`, `page_title` (defaults to `title`), `back_url`, `back_label`, `meta`, `primary_action`, `secondary_actions`, `tabs`, `toolbar`, `body`. Tabs use `{{ ui_section_tabs() }}`; the detail page sets `{% set cta = 'ui-btn ui-btn-primary' %}`; badges are `ui-badge ui-badge-done|neutral` with `data-tone`; the filter summary is `<p class="ui-sub" data-filter-summary>` under `ui_toolbar(...)`; tables are `ui-table ui-table-stack` inside `ui-table-wrap`.

Decisions taken while reconciling (do not undo):
- The invoice items table keeps `class="table-cards invoice-items-grid"`: the `ui-table` phone rules in `host2.css` (specificity 0,2,x) would override the moved grid rules (0,1,x). `table-cards` is added to the form's `legacy` list by step 6.
- The moved CSS keeps the original selectors (no `.host-workspace` prefix), so it wins exactly where the inline `<style>` won; `host2.css` loads after `app.css` and `host.css` in `base.html`. The remove button keeps `min-height: 48px` (min-height is not an S2 property; `--control-h` is 40px and would change the 360 px geometry).
- `--ink-6` does not exist; muted text is `var(--ink-3)` (as in `.ui-sub`).
- The empty state's New invoice link becomes secondary (`primary=false`): the header already carries the one coral New invoice.
- The filter panel's Apply button stays `ui-btn-primary`, as on `reservations.html`.
- The list's `_list_filter.html` include moves into `{% block toolbar %}` (DOM order title, tabs, toolbar, body, as `test_host_list_page_layout_browser.py` requires).
- The detail command panel's `class="actions"` becomes `ui-btn-group` (it wraps), not `ui-form-actions` (no wrap: the links leave the viewport at 360 px).
- Stay fees still extends `base.html` until 0142 but shares `_list_filter.html`: the appended CSS re-centres `.ui-toolbar`, the summary and `.list-filter` when they are direct children of the legacy `.wrap.with-sidebar` lane.
- `test_host_list_cards_browser.py` drops `invoices` (its `.list-cards`/`a.btn`/container-switch contract is the legacy card layout; v2 lists use `ui-table-stack`, and Stays was never in it). `test_host_geometry.py` measures the filter panel by `.ui-section` as well as `.panel`.
- `/invoices/new` without `reservation_id` renders the stay picker; the form shell is covered by `test_invoice_workspace.py` (it opens the builder with a stay).

The anchors (each is matched inside the scripts with an exact count; if a script fails its assert, STOP, §8):
- `App/app/templates/invoices.html` lines 1 to 8 (the `base.html` head with `list_page_header`) and lines 39 to 48 (the `{% if invoice_pages > 1 %}` pager with two `class="btn"` links).
- `App/app/templates/invoice_detail.html` lines 1 to 5 (head) and lines 21 to 27 (the six-line `{{ page_header(` call plus the blank line after it).
- `App/app/templates/invoice_form.html` lines 1 to 6 (head) and lines 117 to 193 (`    <style>` to `    </style>`, 77 lines); five `style="` attributes on lines 61, 63, 94, 114 and 298.
- `App/app/templates/invoice_stay_picker.html` lines 1 to 6 (head).
- `App/app/templates/_list_filter.html` line 16 (`{% from "_components.html" import list_toolbar with context %}`) and line 25 (`{{ list_toolbar(list_summary, panel_id='list-filter-panel', actions=list_filter_actions | default('')) }}`).

Shared-file note: `_list_filter.html` is also included by `stay_fees.html` and `stay_fee_detail.html` (still on `base.html`; brief 0142 moves them). `ui_toolbar` works there too; the stay fee tests in step 7 cover it. Brief 0142 depends on this exact result. `base.html`, `host2.css` and `catalog.json` are also changed by 0138 to 0140; the steps below append to `host2.css`, edit `catalog.json` by JSON keys and bump `base.html` by regex, so they apply after those briefs.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/invoices.html` | edit | head, pagination, classes (step 1) |
| `App/app/templates/_list_filter.html` | edit | `ui_toolbar`, classes (step 2) |
| `App/app/templates/invoice_detail.html` | edit | head, classes, one style (step 3) |
| `App/app/templates/invoice_form.html` | edit | head, classes, styles, `<style>` block out (step 4) |
| `App/app/templates/invoice_stay_picker.html` | edit | head, classes (step 5) |
| `App/app/static/host2.css` | edit | append the 0141 block (step 4) |
| `docs/design/catalog.json` | edit | enforce the four pages; legacy lists (step 6) |
| `App/tests/test_invoice_ux.py` | edit | reset link class (step 7) |
| `App/tests/test_invoice_workspace.py` | edit | primary count (step 7) |
| `App/tests/test_host_invoice_items_browser.py` | edit | `.page-header` to `.ui-ph` (step 7) |
| `App/tests/test_host_invoice_navigation.py` | edit | `.page-actions a` to `.ui-ph-acts a` (step 7) |
| `App/tests/test_host_list_cards_browser.py` | edit | drop the `invoices` list (step 7) |
| `App/tests/test_host_geometry.py` | edit | filter panel selector (step 7) |
| `App/tests/test_design_invoices.py` | create | shells, one primary, no styles (step 7) |
| `App/app/templates/base.html` | edit | `host2.css?v=` key (step 9) |
| `App/tests/static_versions.json` | edit | regenerated (step 9) |
| `docs/tasks/0141-report.md` | create | report |

No other file may change.

## 4. Steps

1. `invoices.html` (head, pager, classes, empty state). Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/invoices.html"); s = p.read_text(encoding="utf-8")
HEAD_OLD = '''{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import list_page_header, empty_state with context %}
{#- 0099: Invoice settings is the second tab (it was a button here). -#}
{{ list_page_header(t('invoices.title'),
    actions='<a class="btn accent primary" href="/invoices/new">' ~ t('invoice.new') ~ '</a>') }}
{% include "_list_filter.html" %}
'''
HEAD_NEW = '''{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'list' %}
{% from "_components.html" import empty_state with context %}
{% from "_ui.html" import ui_button, ui_pagination with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{% block primary_action %}{{ ui_button(t('invoice.new'), 'primary', href='/invoices/new', icon_name='plus') }}{% endblock %}
{#- 0099: Invoice settings is the second tab (it was a button here). -#}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block toolbar %}{% include "_list_filter.html" %}{% endblock %}
{% block body %}
'''
PAGER_OLD = '''{% if invoice_pages > 1 %}
<nav class="action-group" aria-label="{{ t('invoices.title') }}">
  {% if invoice_page > 1 %}
  <a class="btn" href="{{ page_href }}{{ invoice_page - 1 }}" aria-label="{{ invoice_page - 1 }}">‹</a>
  {% endif %}
  {% if invoice_page < invoice_pages %}
  <a class="btn" href="{{ page_href }}{{ invoice_page + 1 }}" aria-label="{{ invoice_page + 1 }}">›</a>
  {% endif %}
</nav>
{% endif %}
'''
PAGER_NEW = '''{% if invoice_pages > 1 %}
{{ ui_pagination(invoice_page, invoice_pages, prev_url=(page_href ~ (invoice_page - 1)) if invoice_page > 1 else '', next_url=(page_href ~ (invoice_page + 1)) if invoice_page < invoice_pages else '', label=t('invoices.title'), more_label=t('stays.pagination.next'), prev_label=t('stays.pagination.prev'), next_label=t('stays.pagination.next')) }}
{% endif %}
'''
PAIRS = [
 (HEAD_OLD, HEAD_NEW, 1),
 (PAGER_OLD, PAGER_NEW, 1),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 1),
 ('class="pill teal"', 'class="ui-badge ui-badge-neutral" data-tone="teal"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 2),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="panel tight scroll-x list-cards lc-invoices"', 'class="ui-table-wrap lc-invoices"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="mono small"', 'class="ui-mono"', 1),
 ('class="nowrap small"', 'class="ui-sub nowrap"', 1),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="num"', 'class="ui-num"', 1),
 ("{{ empty_state(t('invoices.empty_title'), t('invoices.empty'), '/invoices/new', t('invoice.new')) }}", "{{ empty_state(t('invoices.empty_title'), t('invoices.empty'), '/invoices/new', t('invoice.new'), primary=false) }}", 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and 'class="pill' not in s and 'class="panel' not in s and "ui-btn-primary" not in s and "{% block content %}" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then compile: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('invoices.html',)]; print('compiled')" 2>&1 | tail -3`. Expected: `compiled`.

2. `_list_filter.html` (toolbar macro and classes). Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/_list_filter.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('{% from "_components.html" import list_toolbar with context %}\n', '{% from "_ui_layout.html" import ui_toolbar with context %}\n', 1),
 ("{{ list_toolbar(list_summary, panel_id='list-filter-panel', actions=list_filter_actions | default('')) }}\n",
  "{{ ui_toolbar(filters_id='list-filter-panel', filters_count=filter_active | default(0), actions=list_filter_actions | default('')) }}\n<p class=\"ui-sub\" data-filter-summary>{{ list_summary }}</p>\n", 1),
 ('class="btn primary filter-apply"', 'class="ui-btn ui-btn-primary filter-apply"', 1),
 ('class="btn ghost list-filter-reset"', 'class="ui-btn ui-btn-quiet list-filter-reset"', 1),
 ('class="btn ghost month-all-dates"', 'class="ui-btn ui-btn-quiet month-all-dates"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 1),
 ('class="btn month-step"', 'class="ui-btn ui-btn-secondary month-step"', 2),
 ('class="btn month-trigger"', 'class="ui-btn ui-btn-secondary month-trigger"', 1),
 ('class="btn year-step"', 'class="ui-btn ui-btn-secondary year-step"', 2),
 ('class="filters panel list-filter host-filter-panel"', 'class="filters ui-section list-filter host-filter-panel"', 1),
 ('class="field list-filter-period"', 'class="ui-field list-filter-period"', 1),
 ('class="field list-filter-search"', 'class="ui-field list-filter-search"', 1),
 ('class="field"', 'class="ui-field"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and "list_toolbar" not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`.

3. `invoice_detail.html` (head, page header out, classes, the one inline style). Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/invoice_detail.html"); s = p.read_text(encoding="utf-8")
HEAD_OLD = '''{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end with context %}
'''
HEAD_NEW = '''{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import row_menu_begin, row_menu_end with context %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block meta %}{{ invoice.buyer_name }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
'''
PH_OLD = '''{{ page_header(
  t('invoice.detail.title', number=invoice.number),
  invoice.buyer_name,
  '/invoices',
  t('nav.invoices')
) }}

'''
PAIRS = [
 (HEAD_OLD, HEAD_NEW, 1),
 (PH_OLD, '', 1),
 ('<div class="field" style="max-width:220px">', '<div class="ui-field invoice-cancel-reason">', 1),
 ('class="btn primary"', 'class="{{ cta }}"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 4),
 ("'<span class=\"pill grey\">'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"grey\">'", 1),
 ("'<span class=\"pill green\">'", "'<span class=\"ui-badge ui-badge-done\" data-tone=\"green\">'", 1),
 ("'<span class=\"pill teal\">'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"teal\">'", 1),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="num"', 'class="ui-num"', 3),
 ('class="field"', 'class="ui-field"', 1),
 ('class="actions"', 'class="ui-btn-group"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="panel tight scroll-x"', 'class="ui-table-wrap"', 1),
 ('class="panel danger-zone"', 'class="ui-section danger-zone"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert 'style="' not in s and 'class="btn' not in s and 'class="pill' not in s and "page_header" not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. `class="panel stay-command-panel"` and the `stay-command-*`, `detail-metric` classes stay (test-asserted; step 6 lists them as legacy).

4. `invoice_form.html` (head, `<style>` block out, five inline styles, classes). Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/invoice_form.html"); s = p.read_text(encoding="utf-8")
HEAD_OLD = '''{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label, help_tip with context %}
{{ page_header(t('invoice.new'), t('invoices.lede'), '/invoices', t('nav.invoices')) }}
'''
HEAD_NEW = '''{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'form' %}
{% from "_components.html" import field_label, help_tip with context %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block meta %}{{ t('invoices.lede') }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
'''
assert s.count(HEAD_OLD) == 1; s = s.replace(HEAD_OLD, HEAD_NEW)
a = s.index("    <style>\n"); b = s.index("    </style>\n") + len("    </style>\n")
assert s.count("<style>") == 1 and s[a:b].count("\n") == 77, s[a:b].count("\n")
s = s[:a] + s[b:]
PAIRS = [
 ('<div class="action-group" style="align-items:flex-end">', '<div class="action-group invoice-ico-row">', 1),
 ('<div class="actions" style="margin-bottom:12px">', '<div class="ui-form-actions">', 1),
 ('<h2 style="margin-top:0">', '<h2>', 3),
 ('class="btn accent primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 3),
 ('class="btn-secondary"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 2),
 ('class="banner err"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="field"', 'class="ui-field"', 13),
 ('class="actions"', 'class="ui-form-actions"', 1),
 ('class="panel invoice-supplier"', 'class="ui-section invoice-supplier"', 1),
 ('class="panel"', 'class="ui-section"', 3),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="muted small"', 'class="ui-sub"', 1),
 ('class="warn-text small"', 'class="ui-sub warn-text"', 1),
 ('class="small"', 'class="ui-sub"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert 'style="' not in s, re.findall(r' style="[^"]*"', s)
assert 'class="btn' not in s and "<style>" not in s and "page_header" not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then append this block to the **end** of `App/app/static/host2.css` (copy exactly, starting with the blank line; it holds the rules the script removed, with tokens, plus the two replacements for inline styles):

```
/* 0141 invoices: moved from invoice_form.html <style> and two inline styles */
.host-workspace .action-group.invoice-ico-row { align-items: flex-end; }
.invoice-cancel-reason { max-width: 14rem; }
#item-rows.invoice-items-grid { display: block; width: 100%; table-layout: fixed; container-type: inline-size; }
.invoice-items-grid thead,
.invoice-items-grid tbody { display: block; width: 100%; }
.invoice-items-grid thead tr,
.invoice-items-grid tbody tr { display: grid; grid-template-columns: minmax(220px, 1fr) 84px 124px 148px 78px 126px; align-items: start; }
.invoice-items-grid thead tr { align-items: stretch; background: var(--surface-2); }
.invoice-items-grid thead th { display: flex; align-items: center; background: transparent; }
.invoice-items-grid th,
.invoice-items-grid td { box-sizing: border-box; min-width: 0; }
.invoice-items-grid td { vertical-align: top; }
.invoice-items-grid input:not([type=hidden]),
.invoice-items-grid select { box-sizing: border-box; width: 100%; min-width: 0; }
.invoice-items-grid .row-actions [data-remove-item] { min-height: 48px; }
.invoice-items-grid [data-vat-col][hidden] { display: block !important; visibility: hidden; }
.invoice-other-description-field { display: block; margin-top: var(--space-2); }
.invoice-other-description-field > span { display: block; margin-bottom: var(--space-1); color: var(--ink-3); font-size: var(--size-12); font-weight: 600; }
@container (max-width: 850px) {
  .invoice-items-grid thead { display: none; }
  .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3) var(--space-4); padding: var(--space-4); border-bottom: 1px solid var(--line); }
  .invoice-items-grid tbody tr:last-child { border-bottom: 0; }
  .invoice-items-grid td { display: block; padding: 0; border: 0; }
  .invoice-items-grid td:first-child,
  .invoice-items-grid td.row-actions { grid-column: 1 / -1; }
  .invoice-items-grid td.row-actions { text-align: left; }
  .invoice-items-grid td.row-actions .ui-btn { margin: 0; }
  .invoice-items-grid td::before { content: attr(data-label); display: block; margin-bottom: var(--space-1); color: var(--ink-3); font-size: var(--size-11); font-weight: 650; letter-spacing: .05em; text-transform: uppercase; }
  .invoice-items-grid td:first-child::before,
  .invoice-items-grid td.row-actions::before { display: none; }
  .invoice-items-grid [data-vat-col][hidden] { display: none !important; }
}
/* 0141: Stay fees still extends base.html until 0142; keep the shared filter's v2 toolbar, summary and panel on the legacy centred lane there */
.host-workspace .wrap.with-sidebar > .ui-toolbar,
.host-workspace .wrap.with-sidebar > .ui-sub[data-filter-summary],
.host-workspace .wrap.with-sidebar > .list-filter { margin-left: auto; margin-right: auto; }
```

   Command: `tail -3 App/app/static/host2.css`. Expected: the last line is `}`.

5. `invoice_stay_picker.html` (head, classes). Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/invoice_stay_picker.html"); s = p.read_text(encoding="utf-8")
HEAD_OLD = '''{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label with context %}
{{ page_header(t('invoice.new'), t('invoice.picker.lede'), '/invoices', t('nav.invoices')) }}
'''
HEAD_NEW = '''{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'form' %}
{% from "_components.html" import field_label with context %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block meta %}{{ t('invoice.picker.lede') }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
'''
PAIRS = [
 (HEAD_OLD, HEAD_NEW, 1),
 ('class="btn accent primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="panel"', 'class="ui-section"', 1),
 ('class="field"', 'class="ui-field"', 1),
 ('class="actions"', 'class="ui-form-actions"', 1),
 ('class="small muted"', 'class="ui-sub"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and 'class="panel' not in s and "page_header" not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then compile all five: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('invoices.html', 'invoice_detail.html', 'invoice_form.html', 'invoice_stay_picker.html', '_list_filter.html')]; print('compiled')" 2>&1 | tail -3`. Expected: `compiled`.

6. Catalog: enforce the four page templates and record the legacy classes they still use (`_list_filter.html` stays unenforced: it still carries the month picker's legacy classes). Run from the repo root:

```
python3 - <<'EOF'
import json, pathlib, re, subprocess, sys
cat_path = pathlib.Path("docs/design/catalog.json")
NAMES = ["invoices.html", "invoice_detail.html", "invoice_form.html", "invoice_stay_picker.html"]
cat = json.loads(cat_path.read_text(encoding="utf-8"))
for n in NAMES:
    rel = "App/app/templates/" + n
    if rel not in cat["enforced_templates"]:
        cat["enforced_templates"].append(rel)
cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
out = subprocess.run([sys.executable, "scripts/design_lint.py"], capture_output=True, text=True).stdout
for n in NAMES:
    rel = "App/app/templates/" + n
    toks = sorted(set(re.findall(re.escape(rel) + r": T3 class not in catalog: (\S+)", out)))
    if toks:
        cat["legacy"][rel] = sorted(set(cat["legacy"].get(rel, [])) | set(toks))
cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print({n: len(cat["legacy"].get("App/app/templates/" + n, [])) for n in NAMES})
EOF
```

   Expected: `{'invoices.html': 4, 'invoice_detail.html': 17, 'invoice_form.html': 45, 'invoice_stay_picker.html': 0}` (other numbers are fine if 0138 to 0140 changed the catalog; zero for every page means the lint did not run: STOP). Then `python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: `design lint: OK` (S1/S2 also pass on the appended `host2.css` block). The script rewrites `catalog.json` with `json.dumps(indent=2)`; the formatting change is expected.

7. Tests. Edit the six existing tests (one script): Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
EDITS = [
 ("tests/test_invoice_ux.py", 'class="btn ghost list-filter-reset" href="/invoices"', 'class="ui-btn ui-btn-quiet list-filter-reset" href="/invoices"'),
 ("tests/test_host_invoice_items_browser.py", 'page.locator(".page-header")', 'page.locator(".ui-ph")'),
 ("tests/test_invoice_workspace.py", 'page.count("btn accent primary") == 1', 'page.count("ui-btn ui-btn-primary") == 1'),
 ("tests/test_host_list_cards_browser.py", '    "invoices": "/invoices",\n', ''),
 ("tests/test_host_list_cards_browser.py", '"invoices": 830, ', ''),
 ("tests/test_host_geometry.py", "table: edges('.panel, table'),", "table: edges('.panel, .ui-section, table'),"),
 ("tests/test_host_invoice_navigation.py", '".page-actions a, .stay-command-actions a"', '".ui-ph-acts a, .stay-command-actions a"'),
]
for name, old, new in EDITS:
    p = pathlib.Path(name); s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (name, s.count(old)); p.write_text(s.replace(old, new), encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Create `App/tests/test_design_invoices.py` with exactly:

```python
"""0141: invoice pages render on host_page with one primary and no inline styles."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = ("invoices.html", "invoice_detail.html", "invoice_form.html", "invoice_stay_picker.html")
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_invoice_list_has_the_v2_list_shell(host_with_property):
    page = host_with_property.get("/invoices?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-toolbar"' in page and "data-filter-summary" in page
    # One coral New invoice in the header; the empty state repeats it as secondary.
    assert page.count('<a class="ui-btn ui-btn-primary" href="/invoices/new">') == 1
    assert "filter-toolbar list-toolbar" not in page and "page-header" not in page


def test_invoice_stay_picker_has_the_v2_form_shell(host_with_property):
    # Without reservation_id, /invoices/new renders the stay picker.
    page = host_with_property.get("/invoices/new?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page and "<style>" not in page
    assert 'class="ui-ph-back" href="/invoices"' in page


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert 'style="' not in text and 'class="btn' not in text and "<style>" not in text, name
```

   Command (from `App/`): `.venv/bin/python -m pytest tests/test_design_invoices.py tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_list_filter.py tests/test_host_invoice_navigation.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected on the reconcile copy: `1 failed, 223 passed, 4 skipped`, the one failure being `test_stay_fee_send_panel.py::test_send_panel_geometry_and_screenshots` (a browser test without the step 8 environment variables: "Executable doesn't exist"; step 8 runs it properly). Any other failure: STOP.

8. Browser (from `App/`): `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_host_filter_panels_browser.py tests/test_host_list_page_layout_browser.py tests/test_shell_lane_browser.py tests/test_host_geometry.py tests/test_host_invoice_navigation.py tests/test_host_list_cards_browser.py tests/test_stay_fee_send_panel.py tests/test_entity_editor_fields.py -q --tb=line 2>&1 | grep -E 'FAILED|Error|passed|failed|skipped' | tail -30` (about 3 minutes; give the command a 600000 ms timeout). Without `UBYHOST_BROWSER_EXECUTABLE` Playwright looks for a headless shell that is not installed and every browser test errors. Expected: 0 skipped; every test passes except these two, which fail the same way on the base commit before this brief (quote their lines in the report): `test_host_invoice_items_browser.py::test_invoice_item_geometry_and_localized_screenshots` with `Remove height differs from the first control at 360px (en)`, and `test_host_list_page_layout_browser.py::test_list_pages_share_order_edges_and_rhythm` with `[('rhythm', 'tabs', [0, 8, 16]), ('rhythm', 'toolbar', [20, 24])]`. Any other failure, or a different message for those two: STOP (§8). No screenshots: the orchestrator takes them.

9. Static version, last change before the commit (`host2.css` changed in step 4). Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
KEY = "20261019-0141"
hits = 0
for p in sorted(pathlib.Path("app/templates").rglob("*.html")):
    s = p.read_text(encoding="utf-8")
    new, n = re.subn(r'/static/host2\.css\?v=[^"\']+', "/static/host2.css?v=" + KEY, s)
    if n:
        hits += n; p.write_text(new, encoding="utf-8"); print(p, n)
assert hits >= 1, hits
print("ok")
EOF
```

   Expected: `app/templates/base.html 1` and `ok`. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -5`. Expected: passed.

10. Commit: `git add App/app/templates App/app/static/host2.css App/tests docs/design/catalog.json && git commit -m "0141: invoices and the shared month filter on host_page"`. Then `git status --short | head`. Expected: nothing left but the report.

## 5. Do not touch

`routes/invoices.py`, `invoice_pdf.py`, `app.js`, `app.css`, `host.css`, `host-controls.css`, `_components.html` (its macros are removed in 0146), `stay_fees.html`, `stay_fee_detail.html`; hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: `design lint: OK`.
- Step 7, step 8 and step 9 commands.

## 7. Acceptance

- [ ] Steps 1 to 7 scripts printed `ok`; lint OK with the four templates enforced.
- [ ] Step 7 tests passed; step 8 browser run 0 skipped with only the two known failures, same messages.
- [ ] Step 9 static versions test passed.
- [ ] No screenshots needed from the executor (the orchestrator takes them).

## 8. Stop and ask

Stop, and write the report, if: a script's assert fails (an excerpt is not found or a count differs); a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0141-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/_list_filter.html` (shared with Stay fees; 0142 depends on this exact result), `App/app/static/host2.css` (items grid moved), `App/app/templates/invoice_form.html` (item grid markup), the two test edits that drop or widen browser checks (`test_host_list_cards_browser.py`, `test_host_geometry.py`).

## Owner steps

None.
