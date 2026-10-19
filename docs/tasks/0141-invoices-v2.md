# 0141: Invoices (list, detail, form, stay picker) and the shared month filter on the v2 template

Status: todo
Depends on: 0140 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0141 step k`. Never push, never open a PR. Page file: `docs/design/pages/invoices.md`.

## 1. Objective

Move the four invoice templates onto `host_page.html` (list, detail, form, stay picker), convert the shared `_list_filter.html` partial (used by Invoices and Stay fees) to the v2 toolbar and controls, and move the invoice-items `<style>` block into `host2.css` with tokens. Invoice numbers, PDF routes, ARES fill, the item grid JS (`data-add-item`, `data-remove-item`, `data-vat-col`) and field names do not change.

## 2. Context

Rules: MASTER 5 (list, detail, form kinds), 5.3 (toolbar), 7.2, 7.4, 7.13, 4. `app.js` keys on `[data-filter-panel]`, `[data-filter-toggle]`, `[data-filter-summary]`, `[data-filter-cancel]`, `[data-month-picker]` and its `data-month-*` hooks, `.clickable-row`, `[data-add-item]`, `[data-remove-item]`, never on `.btn`, `.pill` or `.field`. The month picker buttons (`month-step`, `month-trigger`, `year-step`, `month-choice`, `month-all-dates`) keep their legacy classes; only their `btn` token changes.

Anchor A, `App/app/templates/invoices.html` lines 1 to 8 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import list_page_header, empty_state with context %}
{#- 0099: Invoice settings is the second tab (it was a button here). -#}
{{ list_page_header(t('invoices.title'),
    actions='<a class="btn accent primary" href="/invoices/new">' ~ t('invoice.new') ~ '</a>') }}
```

Anchor B, same file, the pagination block starts with `{% if invoice_pages > 1 %}` followed by `<nav class="action-group" aria-label="{{ t('invoices.title') }}">` and ends with the matching `</nav>` and `{% endif %}` (nine lines).

Anchor C, `App/app/templates/invoice_detail.html` lines 1 to 5 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end with context %}
```

Anchor D, same file (six lines, verbatim):

```
{{ page_header(
  t('invoice.detail.title', number=invoice.number),
  invoice.buyer_name,
  '/invoices',
  t('nav.invoices')
) }}
```

Anchor E, `App/app/templates/invoice_form.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label, help_tip with context %}
{{ page_header(t('invoice.new'), t('invoices.lede'), '/invoices', t('nav.invoices')) }}
```

Anchor F, same file: the block from the line `    <style>` (line 117) to the line `    </style>` (line 193), 77 lines, all rules for `.invoice-items-grid` and `.invoice-other-description-field`.

Anchor G, `App/app/templates/invoice_stay_picker.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, field_label with context %}
{{ page_header(t('invoice.new'), t('invoice.picker.lede'), '/invoices', t('nav.invoices')) }}
```

Anchor H, `App/app/templates/_list_filter.html`, two lines (verbatim):

```
{% from "_components.html" import list_toolbar with context %}
```

and, after the `{% endset %}` that closes `list_summary`:

```
{{ list_toolbar(list_summary, panel_id='list-filter-panel', actions=list_filter_actions | default('')) }}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/invoices.html` | edit | head, pagination, classes |
| `App/app/templates/invoice_detail.html` | edit | head, classes, one style |
| `App/app/templates/invoice_form.html` | edit | head, classes, styles, `<style>` block out |
| `App/app/templates/invoice_stay_picker.html` | edit | head, classes |
| `App/app/templates/_list_filter.html` | edit | toolbar macro, classes |
| `App/app/static/host2.css` | edit | invoice items grid rules (tokens) |
| `docs/design/catalog.json` | edit | enforce the four pages; legacy lists |
| `App/tests/test_invoice_ux.py` | edit | one string (reset link) |
| `App/tests/test_host_invoice_items_browser.py` | edit | one selector |
| `App/tests/test_host_invoice_navigation.py` | edit | one selector |
| `App/tests/test_design_invoices.py` | create | shells, one primary, no styles |

No other file may change.

## 4. Steps

1. `invoices.html`: replace Anchor A with:

```
{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{% block page_title %}{{ t('invoices.title') }}{% endblock %}
{% block primary_action %}{{ ui_button(t('invoice.new'), 'primary', href='/invoices/new', icon_name='plus') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs(t('nav.invoices')) }}{% endblock %}
{% block body %}
{% from "_components.html" import empty_state with context %}
{% from "_ui.html" import ui_button, ui_pagination with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
```

   Replace Anchor B with:

```
{% if invoice_pages > 1 %}
{{ ui_pagination(invoice_page, invoice_pages, prev_url=(page_href ~ (invoice_page - 1)) if invoice_page > 1 else '', next_url=(page_href ~ (invoice_page + 1)) if invoice_page < invoice_pages else '', label=t('invoices.title'), more_label=t('stays.pagination.next'), prev_label=t('stays.pagination.prev'), next_label=t('stays.pagination.next')) }}
{% endif %}
```

   Then, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/invoices.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 1),
 ('class="pill teal"', 'class="ui-badge ui-badge-neutral" data-tone="teal"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 2),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="panel tight scroll-x list-cards lc-invoices"', 'class="list-cards lc-invoices"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="mono small"', 'class="ui-mono"', 1),
 ('class="nowrap small"', 'class="ui-sub nowrap"', 1),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="num"', 'class="ui-num"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and 'class="pill' not in s and "ui-btn-primary" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Compile: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('invoices.html',)]; print('compiled')"`. Expected: `compiled`.

2. `_list_filter.html`: replace the first line of Anchor H with `{% from "_ui_layout.html" import ui_toolbar with context %}` and the second line with:

```
{{ ui_toolbar(filters_id='list-filter-panel', filters_count=filter_active | default(0), actions=list_filter_actions | default('')) }}
<p class="ui-sub" data-filter-summary>{{ list_summary }}</p>
```

   Then, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/_list_filter.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
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
assert 'class="btn' not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then `grep -n "month-step\|month-trigger\|year-step" App/app/static/host.css App/app/static/host-controls.css App/app/static/app.css | head -20`: these rules select by the legacy class (`.month-step` etc.), not by `.btn.month-step`. If a rule uses `.btn.month-step` or `.btn.year-step`, add the same rule with `.ui-btn.month-step` (respectively `.ui-btn.year-step`) under a `/* 0141 month picker */` comment at the end of `App/app/static/host2.css`, copying the declarations verbatim. Expected: the month picker opens and steps exactly as before (checked in step 8).

3. `invoice_detail.html`: replace Anchor C with:

```
{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'detail' %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block page_title %}{{ t('invoice.detail.title', number=invoice.number) }}{% endblock %}
{% block meta %}{{ invoice.buyer_name }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
{% from "_components.html" import row_menu_begin, row_menu_end with context %}
```

   Delete Anchor D (the six lines). Then, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/invoice_detail.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('<div class="field" style="max-width:220px">', '<div class="ui-field invoice-cancel-reason">', 1),
 ('class="btn primary"', 'class="{{ cta }}"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 4),
 ("'<span class=\"pill grey\">'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"grey\">'", 1),
 ("'<span class=\"pill green\">'", "'<span class=\"ui-badge ui-badge-done\" data-tone=\"green\">'", 1),
 ("'<span class=\"pill teal\">'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"teal\">'", 1),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="num"', 'class="ui-num"', 3),
 ('class="field"', 'class="ui-field"', 2),
 ('class="actions"', 'class="ui-form-actions"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="panel tight scroll-x"', 'class="ui-section scroll-x"', 1),
 ('class="panel danger-zone"', 'class="ui-section danger-zone"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'style="' not in s and 'class="btn' not in s and 'class="pill' not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. `class="panel stay-command-panel"` stays (test-asserted). Append to `App/app/static/host2.css`:

```
/* 0141 invoice detail: cancel reason field width */
.invoice-cancel-reason { max-width: 14rem; }
```

4. `invoice_form.html`: replace Anchor E with:

```
{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'form' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block page_title %}{{ t('invoice.new') }}{% endblock %}
{% block meta %}{{ t('invoices.lede') }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
{% from "_components.html" import field_label, help_tip with context %}
```

   Delete Anchor F (the whole `<style>` ... `</style>` block, 77 lines) and append to `App/app/static/host2.css` the same rules rewritten with tokens (copy exactly):

```
/* 0141 invoice items grid (moved from invoice_form.html) */
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
.invoice-items-grid .row-actions [data-remove-item] { min-height: var(--control-h); }
.invoice-items-grid [data-vat-col][hidden] { display: block !important; visibility: hidden; }
.invoice-other-description-field { display: block; margin-top: var(--space-2); }
.invoice-other-description-field > span { display: block; margin-bottom: var(--space-1); color: var(--ink-6); font-size: var(--size-12); font-weight: 600; }
@container (max-width: 850px) {
  .invoice-items-grid thead { display: none; }
  .invoice-items-grid tbody tr { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3) var(--space-4); padding: var(--space-4); border-bottom: 1px solid var(--line); }
  .invoice-items-grid tbody tr:last-child { border-bottom: 0; }
  .invoice-items-grid td { display: block; padding: 0; border: 0; }
  .invoice-items-grid td:first-child,
  .invoice-items-grid td.row-actions { grid-column: 1 / -1; }
  .invoice-items-grid td.row-actions { text-align: left; }
  .invoice-items-grid td.row-actions .ui-btn { margin: 0; }
  .invoice-items-grid td::before { content: attr(data-label); display: block; margin-bottom: var(--space-1); color: var(--ink-6); font-size: var(--size-11); font-weight: 650; letter-spacing: .05em; text-transform: uppercase; }
  .invoice-items-grid td:first-child::before,
  .invoice-items-grid td.row-actions::before { display: none; }
  .invoice-items-grid [data-vat-col][hidden] { display: none !important; }
}
```

   Grid track widths (`220px 84px ...`) are layout tracks the item JS relies on, not spacing; the S2 rule covers margin, padding, gap, border-radius and font-size only, so they pass. If `--control-h` does not exist in `App/app/static/tokens.css` or the 0125 token layer, use `48px` and note it in the report. Then, from `App/` (the five remaining `style=` attributes are on lines 61, 63, 94, 114 and 298 before the edit; the script removes all five):

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/invoice_form.html"); s = p.read_text(encoding="utf-8")
assert "<style>" not in s
s = s.replace('<div class="action-group" style="align-items:flex-end">', '<div class="action-group ui-align-end">')
s = s.replace('<div class="actions" style="margin-bottom:12px">', '<div class="ui-form-actions">')
s = s.replace('<h2 style="margin-top:0">', '<h2>')
assert 'style="' not in s, re.findall(r' style="[^"]*"', s)
PAIRS = [
 ('class="btn accent primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 3),
 ('class="btn-secondary"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 2),
 ('class="banner err"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="table-cards invoice-items-grid"', 'class="ui-table invoice-items-grid"', 1),
 ('class="field"', 'class="ui-field"', 13),
 ('class="actions"', 'class="ui-form-actions"', 2),
 ('class="panel invoice-supplier"', 'class="ui-section invoice-supplier"', 1),
 ('class="panel"', 'class="ui-section"', 3),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="muted small"', 'class="ui-sub"', 1),
 ('class="warn-text small"', 'class="ui-sub warn-text"', 1),
 ('class="small"', 'class="ui-sub"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and s.count("ui-btn-primary") == 1
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. If `class="banner err"` count is 0, check `grep -n banner App/app/templates/invoice_form.html` and replace the actual banner class with `ui-banner ui-banner-attention`. Add to `host2.css`: `.ui-align-end { align-items: flex-end; }` under the `/* 0141 */` comment. Compile check as in step 1 for `invoice_form.html`.

5. `invoice_stay_picker.html`: replace Anchor G with:

```
{% extends "host_page.html" %}
{% set nav = 'invoices' %}
{% set body_kind = 'form' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block page_title %}{{ t('invoice.new') }}{% endblock %}
{% block meta %}{{ t('invoice.picker.lede') }}{% endblock %}
{% block back_url %}/invoices{% endblock %}
{% block back_label %}{{ t('nav.invoices') }}{% endblock %}
{% block body %}
{% from "_components.html" import field_label with context %}
```

   Replacements (each count 1): `class="btn accent primary"` → `class="ui-btn ui-btn-primary"`, `class="panel"` → `class="ui-section"`, `class="field"` → `class="ui-field"`, `class="actions"` → `class="ui-form-actions"`, `class="small muted"` → `class="ui-sub"`. Command: `grep -c 'class="btn\|class="panel"\|class="field"' App/app/templates/invoice_stay_picker.html`. Expected: `0`.

6. Catalog: add the four page templates (`invoices.html`, `invoice_detail.html`, `invoice_form.html`, `invoice_stay_picker.html`, with the `App/app/templates/` prefix) to `enforced_templates`; `_list_filter.html` stays unenforced (it still carries the month picker's legacy classes). For each enforced template run `python3 scripts/design_lint.py 2>&1 | grep <name> | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into that template's `legacy` list. Command: `python3 scripts/design_lint.py`. Expected: OK (S1/S2 pass on host2.css, so no raw colour or bare px slipped into step 4).

7. Tests. `App/tests/test_invoice_ux.py` line 128: `'class="btn ghost list-filter-reset" href="/invoices"'` → `'class="ui-btn ui-btn-quiet list-filter-reset" href="/invoices"'`. `App/tests/test_host_invoice_items_browser.py` line 236: `.page-header` → `.ui-ph`. `App/tests/test_host_invoice_navigation.py` line 157: `.page-actions a, .stay-command-actions a` → `.ui-ph-acts a, .stay-command-actions a`. Create `App/tests/test_design_invoices.py`:

```python
"""0141: invoice pages render on host_page with one primary and no inline styles."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = ("invoices.html", "invoice_detail.html", "invoice_form.html", "invoice_stay_picker.html")


def test_invoice_list_has_the_v2_list_shell(host_with_property):
    page = host_with_property.get("/invoices?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-toolbar"' in page and 'data-filter-summary' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert "list_toolbar" not in page and "page-header" not in page


def test_invoice_form_has_the_v2_form_shell(host_with_property):
    page = host_with_property.get("/invoices/new?lang=en").text
    assert 'data-body-kind="form"' in page and "<style>" not in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and "<style>" not in text, name
```

   If `/invoices/new` redirects to the stay picker for this fixture, change the second test's URL to the redirect target shown by `host_with_property.get("/invoices/new?lang=en", allow_redirects=False).headers.get("location")` and note it in the report. Command: `cd App && .venv/bin/python -m pytest tests/test_design_invoices.py tests/test_invoice*.py tests/test_host_invoice_navigation.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

8. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_host_filter_panels_browser.py tests/test_host_list_page_layout_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped, except the five known pre-existing failures listed in the plan (test_host_invoice_items_browser at 360 px), which must fail with the same message as before this brief; quote it in the report. Attach `invoices-390.png`, `invoices-1280.png`, `invoice-form-390.png`, `invoice-form-1280.png`.

9. Commit: `git add App/app/templates App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0141 step 9: invoices and the shared month filter on host_page"`.

## 5. Do not touch

`routes/invoices.py`, `invoice_pdf.py`, `app.js` month picker code, `app.css`, `host.css`, `_components.html` (its macros are removed in 0146); hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 7 and step 8 commands.

## 7. Acceptance

- [ ] Invoices list: header with one primary New invoice, section tabs, v2 toolbar with the month filter still working (opens, steps, applies), v2 table, v2 pagination.
- [ ] Invoice detail: back link, buyer meta, one primary Download PDF, badges.
- [ ] Invoice form: form shell, items grid works (add, remove, VAT column) at 1280 and 390, no `<style>` in the page.
- [ ] Screenshots attached; lint OK with the four templates enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0141-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/_list_filter.html` (shared with Stay fees; 0142 depends on this exact result), `App/app/static/host2.css` (items grid moved).

## Owner steps

None.
