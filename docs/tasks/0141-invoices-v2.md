# 0141: Invoices (list, detail, form, stay picker) and the shared month filter on the v2 template

Status: todo
Depends on: 0140 | Base commit: 79252fd (refreshed 2026-10-19 against 0130-0137 and 0147-0152; every anchor count below was asserted on a scratch copy of this head and the result compiled and tested) | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0141 step k`. Never push, never open a PR. Page file: `docs/design/pages/invoices.md`.

**How to run this brief.** Every step is one command, run from `App/` (`cd App` first; the scripts use paths relative to `App/`). Each script asserts the count of every anchor before it writes anything and prints `ok` at the end; if it prints an `AssertionError` tuple instead (the anchor text and the count it found), nothing was written: stop and put the tuple in the report. Do not retype the scripts and do not edit the files by hand. Known-failing tests are named per step; a failure not named there is yours to report, not to fix by weakening the test.

## 1. Objective

Move the four invoice templates onto `host_page.html` (list, detail, form, stay picker), convert the shared `_list_filter.html` partial (used by Invoices and Stay fees) to the v2 toolbar and controls, and move the invoice-items `<style>` block into `host2.css` with tokens. Invoice numbers, PDF routes, ARES fill, the item grid JS (`data-add-item`, `data-remove-item`, `data-vat-col`) and field names do not change.

## 2. Context

Rules: MASTER 4, 5 (list, detail, form kinds), 5.3 (toolbar), 7.2, 7.3, 7.4, 7.13, `docs/design/pages/invoices.md`. `app.js` keys on `[data-filter-panel]`, `[data-filter-toggle]`, `[data-filter-summary]`, `[data-filter-cancel]`, `[data-month-picker]` and its `data-month-*` hooks, `.clickable-row`, `[data-add-item]`, `[data-remove-item]`, never on `.btn`, `.pill` or `.field`. Settled since the first version:

- Invoice list roles: customer `primary`, number `secondary` (`ui-mono`), date (`date_short`) and total (`ui-num ui-cell-r`) `meta`, kind `hide`, status `badge`, the PDF link `actions` in a `row-action-form`. Pagination is `ui_pagination`. One coral per page: the header's New invoice renders only when there are invoices or an active filter; otherwise the empty state's New invoice is the coral.
- `_list_filter.html` renders `ui_toolbar(...)` plus a `<p class="ui-sub" data-filter-summary>` summary line; the month picker buttons keep their legacy hook classes and get `ui-btn ui-btn-secondary`. host.css sizes them at 42/44 px, so script 2 appends a `/* 0141 month picker */` block to `host2.css` that sets them to `var(--control-h)` (40) at 1024 and above and `var(--control-h-phone)` (44) below; `test_host_geometry.py` moves from `44 if width <= 600 else 42` to `44 if width < 1024 else 40` (script 6).
- The invoice items grid is **not** `ui-table`: host2's table rules would override the grid tracks the item JS relies on. It keeps `invoice-items-grid` only; its rules move to `host2.css` in tokens.
- Action rows are `ui-btn-group`; the danger zone is `ui-section ui-card`; the cancel-reason field width is a class (`invoice-cancel-reason`) in `host2.css`.
- Tests reading the old markup move to v2 with the same assertion: `test_invoice_ux.py` (reset link class), `test_invoice_workspace.py` (one primary in the builder), `test_invoice_stay_browser.py` (Issue button selector), `test_host_invoice_items_browser.py` (`.ui-ph`), `test_host_invoice_navigation.py` (`.ui-ph-acts`), `test_host_geometry.py` (empty-state lane, heights), the wide-lane capture (`.lc-invoices`, `.ui-section`).
- Known failures before this brief, not yours: `test_host_invoice_items_browser.py` at 360 px ("Remove height differs from the first control at 360px (en)"); `test_host_list_page_layout_browser.py` tab/toolbar rhythm until 0142 makes Stay fees v2 (this brief gives the fees page the v2 filter partial but not the v2 header).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/invoices.html` | edit | head, roles, badges, pagination (script 1) |
| `App/app/templates/_list_filter.html` | edit | toolbar macro, controls, fields (script 2) |
| `App/app/templates/invoice_detail.html` | edit | head, badges, action row, items roles, danger zone (script 3) |
| `App/app/templates/invoice_form.html` | edit | head, `<style>` block out, sections, controls, fields (script 4) |
| `App/app/templates/invoice_stay_picker.html` | edit | head, classes (script 4) |
| `App/app/static/host2.css` | edit | month picker heights (2), cancel-reason width (3), items grid (4) |
| `docs/design/catalog.json` | edit | enforce the five templates; legacy lists (script 5) |
| `App/tests/test_invoice_ux.py`, `App/tests/test_invoice_workspace.py`, `App/tests/test_invoice_stay_browser.py`, `App/tests/test_host_invoice_items_browser.py`, `App/tests/test_host_invoice_navigation.py`, `App/tests/test_host_geometry.py`, `App/tests/test_host_wide_geometry_browser.py` | edit | one or two strings each (script 6) |
| `App/tests/test_design_invoices.py` | create | list shell, picker shell, no legacy control |

No other file may change.

## 4. Steps

1. `invoices.html`:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
CPT = 'class="ui-btn ui-btn-secondary ui-btn-compact"'
patch("app/templates/invoices.html", [
 ("""{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import list_page_header, empty_state with context %}
{#- 0099: Invoice settings is the second tab (it was a button here). -#}
{{ list_page_header(t('invoices.title'),
    actions='<a class="btn accent primary" href="/invoices/new">' ~ t('invoice.new') ~ '</a>') }}
""", """{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'list' %}
{% from "_components.html" import empty_state with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{#- one coral per page: with no invoice at all the empty state carries New invoice. -#}
{% block primary_action %}{% if invoices or filter_active %}{{ ui_button(t('invoice.new'), 'primary', href='/invoices/new', icon_name='plus') }}{% endif %}{% endblock %}
{#- 0099: Invoice settings is the second tab. -#}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
"""),
 ('<div class="panel tight scroll-x list-cards lc-invoices">', '<div class="list-cards lc-invoices">'),
 ('<table class="table-cards">', '<table class="ui-table ui-table-stack">'),
 ("        <th>{{ t('invoices.col.total') }}</th>", "        <th class=\"ui-cell-r\">{{ t('invoices.col.total') }}</th>"),
 # one DOM (MASTER 7.3): customer leads the card, number under it, date and total as the meta pair, status badge
 ("<td class=\"mono small\" data-label=\"{{ t('invoices.col.number') }}\">", "<td class=\"ui-mono\" data-card=\"secondary\" data-label=\"{{ t('invoices.col.number') }}\">"),
 ("<td class=\"nowrap small\" data-label=\"{{ t('invoices.col.date') }}\">{{ inv.issue_date | date_cz }}</td>", "<td class=\"nowrap\" data-card=\"meta\" data-label=\"{{ t('invoices.col.date') }}\">{{ inv.issue_date | date_short }}</td>"),
 ("<td class=\"col-name\" data-label=\"{{ t('invoices.col.customer') }}\">", "<td class=\"ui-cell-first col-name\" data-card=\"primary\" data-label=\"{{ t('invoices.col.customer') }}\">"),
 ("<td class=\"small\" data-label=\"{{ t('invoices.col.kind') }}\">", "<td data-card=\"hide\" data-label=\"{{ t('invoices.col.kind') }}\">"),
 ("<td class=\"num\" data-label=\"{{ t('invoices.col.total') }}\">", "<td class=\"ui-num ui-cell-r\" data-card=\"meta\" data-label=\"{{ t('invoices.col.total') }}\">"),
 ("<td data-label=\"{{ t('filter.status') }}\">", "<td data-card=\"badge\" data-label=\"{{ t('filter.status') }}\">"),
 ('<td class="row-actions" data-label=""><a class="btn small" href="/invoices/{{ inv.id }}.pdf">{{ t(\'host.invoice_pdf\') }}</a></td>',
  '<td class="ui-cell-acts row-actions" data-card="actions" data-label=""><span class="row-action-form"><a ' + CPT + ' href="/invoices/{{ inv.id }}.pdf">{{ t(\'host.invoice_pdf\') }}</a></span></td>'),
 ('<span class="pill green">', '<span class="ui-badge ui-badge-done" data-tone="green">'),
 ('<span class="pill teal">', '<span class="ui-badge ui-badge-neutral" data-tone="teal">'),
 ("""{% elif inv.state == 'cancelled' %}<span class="pill grey">{{ t('invoice.state.cancelled') }}</span>{% else %}<span class="pill grey">""",
  """{% elif inv.state == 'cancelled' %}<span class="ui-badge ui-badge-neutral" data-tone="grey">{{ t('invoice.state.cancelled') }}</span>{% else %}<span class="ui-badge ui-badge-neutral" data-tone="grey">"""),
 ("""{% if invoice_pages > 1 %}
<nav class="action-group" aria-label="{{ t('invoices.title') }}">
  {% if invoice_page > 1 %}
  <a class="btn" href="{{ page_href }}{{ invoice_page - 1 }}" aria-label="{{ invoice_page - 1 }}">‹</a>
  {% endif %}
  {% if invoice_page < invoice_pages %}
  <a class="btn" href="{{ page_href }}{{ invoice_page + 1 }}" aria-label="{{ invoice_page + 1 }}">›</a>
  {% endif %}
</nav>
{% endif %}
""", """{% if invoice_pages > 1 %}
{{ ui_pagination(invoice_page, invoice_pages, prev_url=(page_href ~ (invoice_page - 1)) if invoice_page > 1 else '', next_url=(page_href ~ (invoice_page + 1)) if invoice_page < invoice_pages else '', label=t('invoices.title'), more_label=t('stays.pagination.next'), prev_label=t('stays.pagination.prev'), next_label=t('stays.pagination.next')) }}
{% endif %}
"""),
])
s = pathlib.Path("app/templates/invoices.html").read_text(encoding="utf-8")
for f in ('class="btn', 'class="pill', 'class="small', 'class="num"', 'class="mono', 'class="panel', 'ui-btn-primary'):
    assert f not in s, f
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('invoices.html'); print('compiled')"`. Expected: `compiled`. Commit `0141 step 1`.

2. `_list_filter.html` and the month picker heights:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/_list_filter.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('{% from "_components.html" import list_toolbar with context %}', '{% from "_ui_layout.html" import ui_toolbar with context %}', 1),
 ("{{ list_toolbar(list_summary, panel_id='list-filter-panel', actions=list_filter_actions | default('')) }}",
  "{{ ui_toolbar(filters_id='list-filter-panel', filters_count=filter_active | default(0), actions=list_filter_actions | default('')) }}\n<p class=\"ui-sub\" data-filter-summary>{{ list_summary }}</p>", 1),
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
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and s.count("ui-btn-primary") == 1 and "list_toolbar" not in s
p.write_text(s, encoding="utf-8")
# host2.css: the month picker's legacy rules size its buttons at 42/44 px; v2 controls are 40 px at 1024+ and 44 below.
p = pathlib.Path("app/static/host2.css"); s = p.read_text(encoding="utf-8")
assert "0141 month picker" not in s
s = s.rstrip("\n") + """

/* 0141 month picker: v2 control heights over the legacy host.css sizes */
.host-workspace .list-filter .ui-btn.month-step, .host-workspace .ui-btn.year-step { width: var(--control-h); min-width: var(--control-h); height: var(--control-h); min-height: var(--control-h); }
.host-workspace .ui-btn.month-trigger, .host-workspace .ui-btn.month-all-dates { min-height: var(--control-h); height: auto; }
@media (max-width: 1023px) {
  .host-workspace .list-filter .ui-btn.month-step, .host-workspace .ui-btn.year-step { width: var(--control-h-phone); min-width: var(--control-h-phone); height: var(--control-h-phone); min-height: var(--control-h-phone); }
  .host-workspace .ui-btn.month-trigger, .host-workspace .ui-btn.month-all-dates { min-height: var(--control-h-phone); }
}
"""
p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('_list_filter.html'); templates.env.get_template('invoices.html'); templates.env.get_template('stay_fees.html'); print('compiled')"`. Expected: `compiled`. Commit `0141 step 2`.

3. `invoice_detail.html`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/invoice_detail.html"); s = p.read_text(encoding="utf-8")
SEC = 'class="ui-btn ui-btn-secondary"'
PAIRS = [
 ("""{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end with context %}
""", """{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import row_menu_begin, row_menu_end with context %}
{% block title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block meta %}{{ invoice.buyer_name }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
""", 1),
 ("""{{ page_header(
  t('invoice.detail.title', number=invoice.number),
  invoice.buyer_name,
  '/invoices',
  t('nav.invoices')
) }}
""", "", 1),
 ("'<span class=\"pill grey\">'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"grey\">'", 1),
 ("'<span class=\"pill green\">'", "'<span class=\"ui-badge ui-badge-done\" data-tone=\"green\">'", 1),
 ("'<span class=\"pill teal\">'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"teal\">'", 1),
 ('<div class="actions">', '<div class="ui-btn-group">', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 1),
 ('class="btn"', SEC, 4),
 ('<div class="panel tight scroll-x">', '<div class="ui-section scroll-x">', 1),
 ('<table class="table-cards">', '<table class="ui-table ui-table-stack">', 1),
 ("<th>{{ t('invoice.col.total') }}</th>", "<th class=\"ui-cell-r\">{{ t('invoice.col.total') }}</th>", 2),
 # items: one DOM; the description leads the card, quantity under it, the line total at the right
 ("<td data-label=\"{{ t('invoice.col.description') }}\">", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('invoice.col.description') }}\">", 2),
 ("<td data-label=\"{{ t('invoice.col.qty') }}\">", "<td data-card=\"secondary\" data-label=\"{{ t('invoice.col.qty') }}\">", 2),
 ("<td data-label=\"{{ t('invoice.detail.unit_excl_vat') }}\">", "<td data-card=\"hide\" data-label=\"{{ t('invoice.detail.unit_excl_vat') }}\">", 1),
 ("<td data-label=\"{{ t('invoice.col.vat') }}\">", "<td data-card=\"hide\" data-label=\"{{ t('invoice.col.vat') }}\">", 1),
 ("<td data-label=\"{{ t('invoice.detail.vat_col') }}\">", "<td data-card=\"hide\" data-label=\"{{ t('invoice.detail.vat_col') }}\">", 1),
 ("<td data-label=\"{{ t('invoice.col.unit_price') }}\">", "<td data-card=\"hide\" data-label=\"{{ t('invoice.col.unit_price') }}\">", 1),
 ("<td data-label=\"{{ t('invoice.col.total') }}\">", "<td class=\"ui-num ui-cell-r\" data-card=\"meta\" data-label=\"{{ t('invoice.col.total') }}\">", 2),
 ('<td colspan="6" class="small muted">', '<td colspan="6">', 1),
 ('<td class="num">', '<td class="ui-num ui-cell-r">', 3),
 ('<p class="small muted">', '<p class="ui-sub">', 2),
 ('<details class="panel danger-zone" id="cancel">', '<details class="ui-section ui-card danger-zone" id="cancel">', 1),
 ('<div class="field" style="max-width:220px">', '<div class="ui-field invoice-cancel-reason">', 1),
 ('<div class="field">', '<div class="ui-field">', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:70], s.count(old)); s = s.replace(old, new)
for f in ('style="', 'class="btn', 'class="pill', 'class="small', 'class="num"', 'class="actions"', 'class="field"', 'page_header'):
    assert f not in s, f
assert s.count("ui-btn-primary") == 1 and 'class="panel stay-command-panel"' in s
p.write_text(s, encoding="utf-8")
p = pathlib.Path("app/static/host2.css"); s = p.read_text(encoding="utf-8")
assert "invoice-cancel-reason" not in s
p.write_text(s.rstrip("\n") + "\n\n/* 0141 invoice detail: cancel reason field width */\n.host-workspace .invoice-cancel-reason { max-width: 14rem; }\n", encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('invoice_detail.html'); print('compiled')"`. Expected: `compiled`. Commit `0141 step 3`.

4. `invoice_form.html`, `invoice_stay_picker.html`, the items grid in `host2.css`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/invoice_form.html"); s = p.read_text(encoding="utf-8")
blocks = re.findall(r"\n    <style>.*?</style>", s, re.S); assert len(blocks) == 1 and "invoice-items-grid" in blocks[0], len(blocks)
s = s.replace(blocks[0], "")
SEC = 'class="ui-btn ui-btn-secondary"'
CPT = 'class="ui-btn ui-btn-secondary ui-btn-compact"'
PAIRS = [
 ("""{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label, help_tip with context %}
{{ page_header(t('invoice.new'), t('invoices.lede'), '/invoices', t('nav.invoices')) }}
""", """{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'form' %}
{% from "_components.html" import field_label, help_tip with context %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block meta %}{{ t('invoices.lede') }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
""", 1),
 ('<div class="banner err">', '<div class="ui-banner ui-banner-attention">', 1),
 ('<div class="panel invoice-supplier">', '<div class="ui-section invoice-supplier">', 1),
 ('<div class="field invoice-supplier-picker">', '<div class="ui-field invoice-supplier-picker">', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('<div class="panel">', '<div class="ui-section">', 3),
 ('<h2 style="margin-top:0">', '<h2>', 3),
 ('<div class="actions" style="margin-bottom:12px">', '<div class="ui-btn-group">', 1),
 ('class="btn-secondary"', SEC, 1),
 ('<div class="action-group" style="align-items:flex-end">', '<div class="ui-btn-group">', 1),
 ('class="btn"', SEC, 2),
 ('class="table-cards invoice-items-grid"', 'class="invoice-items-grid"', 1),
 ('class="btn small"', CPT, 3),
 ('<div class="actions">', '<div class="ui-btn-group">', 1),
 ('<div class="field invoice-paid-duzp-clone" hidden>', '<div class="ui-field invoice-paid-duzp-clone" hidden>', 1),
 ('<div class="field">', '<div class="ui-field">', 13),
 ('<p class="warn-text small"', '<p class="ui-sub warn-text"', 1),
 ('class="btn accent primary"', 'class="ui-btn ui-btn-primary"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old[:70], s.count(old)); s = s.replace(old, new)
for f in ('<style', 'style="', 'class="btn', 'class="panel', 'class="actions', 'class="field"', 'class="field ', 'page_header'):
    assert f not in s, f
assert s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8")

p = pathlib.Path("app/templates/invoice_stay_picker.html"); s = p.read_text(encoding="utf-8")
for old, new in [
 ("""{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label with context %}
{{ page_header(t('invoice.new'), t('invoice.picker.lede'), '/invoices', t('nav.invoices')) }}
""", """{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'form' %}
{% from "_components.html" import field_label with context %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block meta %}{{ t('invoice.picker.lede') }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
"""),
 ('<div class="panel">', '<div class="ui-section">'),
 ('<div class="field">', '<div class="ui-field">'),
 ('<div class="actions">', '<div class="ui-btn-group">'),
 ('class="btn accent primary"', 'class="ui-btn ui-btn-primary"'),
 ('<p class="small muted">', '<p class="ui-sub">'),
]:
    assert s.count(old) == 1, (old[:60], s.count(old)); s = s.replace(old, new)
for f in ('style="', 'class="btn', 'class="panel', 'class="actions', 'class="field', 'page_header'):
    assert f not in s, f
p.write_text(s, encoding="utf-8")

# host2.css: the items grid rules, in tokens (track widths are layout the item JS relies on, not spacing)
p = pathlib.Path("app/static/host2.css"); s = p.read_text(encoding="utf-8")
assert "0141 invoice items grid" not in s
s = s.rstrip("\n") + """

/* 0141 invoice items grid (moved from invoice_form.html) */
#item-rows.invoice-items-grid { display: block; width: 100%; table-layout: fixed; container-type: inline-size; }
.invoice-items-grid thead, .invoice-items-grid tbody { display: block; width: 100%; }
.invoice-items-grid thead tr, .invoice-items-grid tbody tr { display: grid; grid-template-columns: minmax(220px, 1fr) 84px 124px 148px 78px 126px; align-items: start; }
.invoice-items-grid thead tr { align-items: stretch; background: var(--surface-2); }
.invoice-items-grid thead th { display: flex; align-items: center; background: transparent; }
.invoice-items-grid th, .invoice-items-grid td { box-sizing: border-box; min-width: 0; }
.invoice-items-grid td { vertical-align: top; }
.invoice-items-grid input:not([type=hidden]), .invoice-items-grid select { box-sizing: border-box; width: 100%; min-width: 0; }
.invoice-items-grid .row-actions [data-remove-item] { min-height: var(--control-h); }
.invoice-items-grid [data-vat-col][hidden] { display: block !important; visibility: hidden; }
.invoice-other-description-field { display: block; margin-top: var(--space-2); }
.invoice-other-description-field > span { display: block; margin-bottom: var(--space-1); color: var(--ink-3); font-size: var(--size-12); font-weight: 600; }
@container (max-width: 850px) {
  .invoice-items-grid thead { display: none; }
  .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3) var(--space-4); padding: var(--space-4); border-bottom: 1px solid var(--line); }
  .invoice-items-grid tbody tr:last-child { border-bottom: 0; }
  .invoice-items-grid td { display: block; padding: 0; border: 0; }
  .invoice-items-grid td:first-child, .invoice-items-grid td.row-actions { grid-column: 1 / -1; }
  .invoice-items-grid td.row-actions { text-align: left; }
  .invoice-items-grid td.row-actions .ui-btn { margin: 0; }
  .invoice-items-grid td::before { content: attr(data-label); display: block; margin-bottom: var(--space-1); color: var(--ink-3); font-size: var(--size-11); font-weight: 650; letter-spacing: .05em; text-transform: uppercase; }
  .invoice-items-grid td:first-child::before, .invoice-items-grid td.row-actions::before { display: none; }
  .invoice-items-grid [data-vat-col][hidden] { display: none !important; }
}
"""
p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('invoice_form.html'); templates.env.get_template('invoice_stay_picker.html'); print('compiled')"`. Expected: `compiled`. Commit `0141 step 4`.

5. Catalog:

```
.venv/bin/python - <<'EOF'
import json, pathlib
p = pathlib.Path("../docs/design/catalog.json"); s = p.read_text(encoding="utf-8")
LEGACY = {
 "invoices.html": ["col-name", "lc-invoices", "list-cards", "nowrap", "row-actions"],
 "invoice_detail.html": ["col-name", "danger-zone", "detail-hero", "detail-metric", "eyebrow", "invoice-cancel-reason", "invoice-document", "invoice-workspace", "metric-label", "metric-value", "panel", "scroll-x", "small-value", "stay-command-actions", "stay-command-main", "stay-command-note", "stay-command-panel", "stay-metrics"],
 "invoice_form.html": ["alert", "banner-list", "checkline", "col-name", "field-label-row", "grid", "hint", "input-kind", "input-price", "input-qty", "input-unit", "input-vat", "invoice-actions", "invoice-buyer-grid", "invoice-document", "invoice-form", "invoice-items-grid", "invoice-items-heading", "invoice-more", "invoice-more-body", "invoice-other-description-field", "invoice-paid-choice", "invoice-paid-duzp-clone", "invoice-paid-grid", "invoice-stay-context", "invoice-supplier", "invoice-supplier-meta", "invoice-supplier-name", "invoice-supplier-picker", "invoice-supplier-row", "invoice-total", "invoice-total-label", "invoice-total-value", "invoice-workspace", "medium", "muted", "opt", "row-actions", "short", "skeleton", "skeleton-line", "small", "warn-text"],
 "invoice_stay_picker.html": [],
 "_list_filter.html": ["filter-apply", "filter-fields", "filter-panel-actions", "filters", "host-filter-panel", "is-empty", "list-filter", "list-filter-count", "list-filter-period", "list-filter-reset", "list-filter-search", "month-all-dates", "month-choice", "month-control", "month-control-face", "month-grid", "month-grid-panel", "month-row", "month-step", "month-trigger", "month-year-row", "selected", "year-step"],
}
old = '"App/app/templates/entities.html"],\n  "legacy": {\n'
assert s.count(old) == 1, s.count(old)
new = ('"App/app/templates/entities.html", ' + ", ".join(f'"App/app/templates/{n}"' for n in LEGACY) + '],\n  "legacy": {\n'
       + "".join(f'    "App/app/templates/{n}": {json.dumps(t)},\n' for n, t in LEGACY.items()))
s = s.replace(old, new); json.loads(s); p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then `cd .. && python3 scripts/design_lint.py && cd App`. Expected: `design lint: OK`. Commit `0141 step 5`.

6. Tests:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
# tests that read the old markup move to v2 and keep their assertion
patch("tests/test_invoice_ux.py", [
 ("""    assert 'class="btn ghost list-filter-reset" href="/invoices"' in august.text""",
  """    assert 'class="ui-btn ui-btn-quiet list-filter-reset" href="/invoices"' in august.text"""),
])
patch("tests/test_invoice_workspace.py", [
 ("""    assert page.count("btn accent primary") == 1  # Issue invoice""",
  """    assert page.count('class="ui-btn ui-btn-primary"') == 1  # Issue invoice"""),
])
patch("tests/test_host_invoice_items_browser.py", [
 ("""            heading = page.locator(".page-header").bounding_box()""", """            heading = page.locator(".ui-ph").bounding_box()"""),
])
patch("tests/test_host_invoice_navigation.py", [
 ("""                        for link in page.locator(".page-actions a, .stay-command-actions a").all():""",
  """                        for link in page.locator(".ui-ph-acts a, .stay-command-actions a").all():"""),
])
# v2 controls: 40 px at 1024 and above, 44 below (MASTER 4); the month stepper follows host2.css now
patch("tests/test_host_geometry.py", [
 ("""        expected_height = 44 if width <= 600 else 42""", """        expected_height = 44 if width < 1024 else 40"""),
 ("""                    table: edges('.panel, table'),""", """                    table: edges('.panel, table, .ui-empty'),"""),
])
patch("tests/test_invoice_stay_browser.py", [
 ('        page.click(".invoice-actions button.accent.primary")', '        page.click(".invoice-actions button.ui-btn-primary")'),
])
patch("tests/test_host_wide_geometry_browser.py", [
 ('    "invoices": ("/invoices", ".panel.tight.scroll-x, .panel.empty"),', '    "invoices": ("/invoices", ".lc-invoices, .ui-empty"),'),
 ('    "invoice-new-picker": ("/invoices/new", ".panel"),', '    "invoice-new-picker": ("/invoices/new", ".ui-section"),'),
])
pathlib.Path("tests/test_design_invoices.py").write_text('''"""0141: invoice list, detail, builder and picker render on host_page."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_invoice_list_has_the_v2_header_tabs_and_toolbar(host_with_property):
    page = host_with_property.get("/invoices?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-tabs" data-sub-tabs' in page and "data-list-toolbar" in page
    assert 'class="page-header' not in page and 'class="sub-tabs' not in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1  # one coral: New invoice (header, or the empty state)


def test_invoice_picker_is_a_form_page(host_with_property):
    page = host_with_property.get("/invoices/new?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page and "ui-ph-back" in page


def test_no_raw_style_or_legacy_control_in_the_invoice_templates():
    for name in ("invoices.html", "invoice_detail.html", "invoice_form.html", "invoice_stay_picker.html", "_list_filter.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "<style" not in text and 'style="' not in text, name
        assert 'class="btn' not in text and 'class="pill' not in text and "page_header(" not in text, name
        assert text.count("ui-btn-primary") <= 1, name
    for name in ("invoices.html", "invoice_detail.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        # one DOM per list: the rows carry MASTER 7.3 roles instead of a second phone markup
        assert 'data-card="primary"' in text, name
''', encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -m pytest tests/test_design_invoices.py tests/test_invoice*.py tests/test_stay_fee_list.py tests/test_reporting_help_0097.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -30`. Expected: all passed (`test_invoice_stay_browser.py` and `test_host_invoice_navigation.py` need the browser env of step 7 to run; a skip here is fine, step 7 runs them). Commit `0141 step 6`.

7. Browser: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_invoice_stay_browser.py tests/test_host_invoice_navigation.py tests/test_host_invoice_items_browser.py tests/test_host_filter_panels_browser.py tests/test_host_list_cards_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_wide_geometry_browser.py -q --tb=line 2>&1 | tail -30`. Expected: passed, 0 skipped, except the two known failures in section 2 (quote their messages; the items test must fail with the same 360 px message as before, nothing else).

8. Screenshots: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers SHOT_TASK=0141 SHOT_PAGES="invoices invoice-form invoice-detail" .venv/bin/python -m pytest -p tests.conftest /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shoot_pages.py -q -s 2>&1 | tail -8`. The fixture seeds no invoice, so `invoice-detail` prints "nothing to show"; if it does, rerun with `SHOT_PAGES="invoices invoice-form"` and say so in the report. Check in `invoices-390.png` that the month filter toolbar and the empty state share the lane, and in `invoice-form-1280.png` that the stay picker is a boxed form. Then `git status --short | head -20`: the only changes must be the files in section 3. If a tracked evidence folder changed (for example `docs/tasks/0087-evidence/`), `git checkout -- <that folder>` before committing.

9. Commit: `git add App/app/templates App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0141 step 9: invoices and the shared month filter on host_page"`.

## 5. Do not touch

`routes/invoices.py`, `invoice_pdf.py`, `app.js` month picker code, `app.css`, `host.css`, `_components.html` (its macros are removed in 0146); hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 6 and step 7 commands; only the known failures named in section 2.

## 7. Acceptance

- [ ] Invoices list: header with one primary New invoice (or the empty state's), section tabs, v2 toolbar with the month filter still working (opens, steps, applies), v2 table with roles, v2 pagination.
- [ ] Invoice detail: back link, buyer meta, one primary Download PDF, badges, items table with roles.
- [ ] Invoice form: form shell, items grid works (add, remove, VAT column) at 1280 and 390, no `<style>` in the page; stay picker as a boxed form.
- [ ] Screenshots attached; lint OK with the five templates enforced; month stepper 40 px at 1024 and above, 44 below.

## 8. Stop and ask

Stop, and write the report, if: a script prints an `AssertionError` instead of `ok`; a test not named as known-failing fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0141-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, the known failures seen (one line each, with the message), deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/_list_filter.html` (shared with Stay fees; 0142 depends on this exact result), `App/app/static/host2.css` (items grid moved, month picker heights), `App/tests/test_host_geometry.py` (42 to 40).

## Owner steps

None.
