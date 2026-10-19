# 0129: host_page.html: page header, four body kinds, one skeleton per kind

Status: blocked
Depends on: 0128 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0129 step k`. Never push, never open a PR. Runs after 0128 (both touch `host2.css`).

## 1. Objective

Create the one page layout `App/app/templates/host_page.html` with fixed slots (title, meta, primary action, secondary actions, tabs, toolbar, body, empty) and four body kinds, plus the layout macros and the second half of `host2.css`. The template renders the skeleton that matches its body kind at full lane width, replacing the one small generic card for every page that extends it (MASTER 5). No page extends it yet.

## 2. Context

Rules: MASTER 3 (type and spacing), 5 (template, body kinds, skeletons), 7.3, 7.4, 7.6, 7.7, 7.14, 10. Tokens only in CSS. The old skeleton stays for pages that still extend `base.html` directly.

Anchor A, `App/app/templates/base.html` (the skeleton placeholder inside `<main>`):

```
  {% block content %}{% endblock %}
  <div class="page-skeleton" data-page-skeleton role="status" hidden>
    <span class="sr-only">{{ t('a11y.loading') }}</span>
    <div class="c05-skel" aria-hidden="true">
```

Anchor B, `App/app/templates/base.html`:

```
      <span class="c05-skel__bone c05-skel__block c05-skel__block--w60"></span>
    </div>
  </div>
</main>
```

Anchor C, `App/app/static/skeleton.js`:

```
  var DELAY_MS = 400;
  var SAFETY_MS = 15000;
```

Anchor D, `App/app/static/skeleton.js`:

```
  function hide() {
    window.clearTimeout(timer);
    window.clearTimeout(safety);
    timer = null;
    safety = null;
    var el = placeholder();
```

Anchor E, `App/app/static/skeleton.js`:

```
    el.parentElement.setAttribute("aria-busy", "true");
    el.hidden = false;
```

Anchor F, `docs/design/catalog.json`:

```
    "ui-icon", "ui-input", "ui-select", "ui-textarea"
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/host_page.html` | create | the layout |
| `App/app/templates/_ui_layout.html` | create | `ui_tabs`, `ui_toolbar`, `ui_section`, `ui_facts`, `ui_stats`, `ui_banner`, `ui_table_begin`, `ui_table_end`, `ui_card`, `ui_skeleton` |
| `App/app/static/host2.css` | edit | append part 2 (page, header, tabs, toolbar, body kinds, table, cards, facts, stats, banner, skeleton) |
| `App/app/templates/base.html` | edit | wrap the old skeleton in `{% block page_skeleton %}` |
| `App/app/static/skeleton.js` | edit | 300 ms delay, 400 ms minimum visible |
| `docs/design/catalog.json` | edit | skeleton width classes |
| `App/tests/test_design_page_template.py` | create | renders a sample page per kind; skeleton matches kind; one h1; slots |
| `App/tests/test_host_list_page_layout_browser.py` | edit | selectors accept v2 and v1 markup (step 8) |
| `App/tests/test_host_wide_geometry_browser.py` | edit | selectors accept v2 and v1 markup (step 8) |
| `App/tests/test_host_geometry.py` | edit | title selector (step 8) |
| `App/tests/test_host_list_cards_browser.py` | edit | panel selector (step 8) |
| `App/tests/test_reporting_help_0097.py` | edit | panel selector (step 8) |

No other file may change.

## 4. Steps

1. In `docs/design/catalog.json`, replace Anchor F with:

```
    "ui-icon", "ui-input", "ui-select", "ui-textarea",
    "ui-bone-title", "ui-bone-meta", "ui-bone-btn", "ui-bone-toolbar", "ui-bone-label", "ui-bone-control", "ui-bone-badge", "ui-bone-line",
    "ui-w10", "ui-w14", "ui-w18", "ui-w30", "ui-w40", "ui-w60", "ui-skel-detail", "ui-skel-side", "ui-cards-stack"
```

   Command: `python3 -c "import json;json.load(open('docs/design/catalog.json'));print('json ok')"`. Expected: `json ok`.

2. Create `App/app/templates/_ui_layout.html`:

```
{#- Design v2 layout macros (docs/design/MASTER.md 5, 7.3, 7.4, 7.6, 7.7, 7.14). -#}
{% from "_icons.html" import icon with context %}
{% from "_ui.html" import ui_button, ui_icon_button, ui_chip with context %}

{#- 5.2 tabs: items = list of (href, label, current). Position, not action: ink underline. -#}
{% macro ui_tabs(items, label='') -%}
{% if items %}<nav class="ui-tabs" data-sub-tabs aria-label="{{ label or t('host.section_navigation') }}">{% for href, text, current in items %}<a class="ui-tab" href="{{ href }}"{% if current %} aria-current="page"{% endif %}>{{ text }}</a>{% endfor %}</nav>{% endif %}
{%- endmacro %}

{#- the section's own sub-page tabs (page_tabs() from the request context), translated. -#}
{% macro ui_section_tabs(label='') -%}
{% set items = [] %}{% for href, key, current in page_tabs() %}{% set _ = items.append((href, t(key), current)) %}{% endfor %}{{ ui_tabs(items, label) }}
{%- endmacro %}

{#- 5.3 toolbar. search: (name, placeholder, value) or none. chips: list of (href, label, selected).
    filters_id: id of the filter <form> that opens as a sheet on phone (hidden by app.js like today).
    actions: raw html of quiet buttons for the right side. -#}
{% macro ui_toolbar(search=none, chips=[], filters_id='', filters_count=0, actions='', filters_label='') -%}
<div class="ui-toolbar" data-filter-toolbar data-list-toolbar>
  {% if search %}<label class="ui-toolbar-search">{{ icon('search', 16) }}<input class="ui-input" type="search" name="{{ search[0] }}" placeholder="{{ search[1] }}" value="{{ search[2] }}" aria-label="{{ search[1] }}"></label>{% endif %}
  {% if chips %}<div class="ui-chips">{% for href, text, selected in chips %}{{ ui_chip(text, href=href, selected=selected) }}{% endfor %}</div>{% endif %}
  {% if filters_id %}<button class="ui-btn ui-btn-secondary" type="button" data-filter-toggle aria-expanded="true" aria-controls="{{ filters_id }}" hidden>{{ icon('sliders-horizontal', 16) }}<span>{{ filters_label or t('host.filter.filters') }}</span>{% if filters_count %}<span class="ui-badge ui-badge-neutral">{{ filters_count }}</span>{% endif %}</button>{% endif %}
  {% if actions | trim %}<div class="ui-toolbar-right">{{ actions | safe }}</div>{% endif %}
</div>
{%- endmacro %}

{#- 7.14 section with a title row; call-block holds the content. -#}
{% macro ui_section(title, actions='', id='') -%}
<section class="ui-section"{% if id %} id="{{ id }}"{% endif %}>
  <div class="ui-section-h"><h2>{{ title }}</h2>{% if actions | trim %}<div class="ui-btn-group">{{ actions | safe }}</div>{% endif %}</div>
  {{ caller() }}
</section>
{%- endmacro %}

{#- facts: list of (key, value_html). -#}
{% macro ui_facts(pairs) -%}
<dl class="ui-facts">{% for key, value in pairs %}<div><dt>{{ key }}</dt><dd>{{ value | safe }}</dd></div>{% endfor %}</dl>
{%- endmacro %}

{#- stat row: list of (href, number, label). Numbers stay ink. -#}
{% macro ui_stats(items, label='') -%}
<nav class="ui-stats" aria-label="{{ label }}">{% for href, number, text in items %}<a class="ui-stat" href="{{ href }}"><strong class="ui-num">{{ number }}</strong><span>{{ text }}</span></a>{% endfor %}</nav>
{%- endmacro %}

{#- banner: kind attention | neutral; one optional secondary action (label, href). -#}
{% macro ui_banner(kind, text, action_label='', action_href='') -%}
<div class="ui-banner ui-banner-{{ kind }}" role="status">{{ icon('triangle-alert' if kind == 'attention' else 'info', 20) }}<div class="grow">{{ text | safe }}</div>{% if action_href %}{{ ui_button(action_label, 'secondary', href=action_href, size='compact') }}{% endif %}</div>
{%- endmacro %}

{#- 7.4 table: columns = list of (label, align) with align '' or 'r'. Rows go in the call block as <tr class="ui-row"> ...
    Below 1024 the page also renders ui_card rows inside <div class="ui-cards">; the CSS shows one of the two. -#}
{% macro ui_table_begin(columns, label='') -%}
<table class="ui-table" aria-label="{{ label }}"><thead><tr>{% for text, align in columns %}<th scope="col"{% if align == 'r' %} class="ui-cell-r"{% endif %}>{{ text }}</th>{% endfor %}</tr></thead><tbody>
{%- endmacro %}
{% macro ui_table_end() -%}</tbody></table>{%- endmacro %}

{#- 7.3 card row for phone: three lines and a badge; whole card is the link. -#}
{% macro ui_card(href, l1, l2='', l3='', badge='', label='') -%}
<a class="ui-card" href="{{ href }}"{% if label %} aria-label="{{ label }}"{% endif %}><span class="ui-card-l1"><span>{{ l1 | safe }}</span>{{ badge | safe }}</span>{% if l2 %}<span class="ui-card-l2">{{ l2 | safe }}</span>{% endif %}{% if l3 %}<span class="ui-card-l3">{{ l3 | safe }}</span>{% endif %}</a>
{%- endmacro %}

{#- 5.5 skeleton per body kind, same heights as the real components, no inline styles. -#}
{% macro ui_skeleton(kind) -%}
<div class="ui-skel" aria-hidden="true" data-skeleton-kind="{{ kind }}">
  <div class="ui-skel-h"><div><span class="ui-bone ui-bone-title"></span><span class="ui-bone ui-bone-meta"></span></div><span class="ui-bone ui-bone-btn"></span></div>
  {% if kind == 'list' %}
  <span class="ui-bone ui-bone-toolbar"></span>
  <div class="ui-skel-rows">{% for i in range(6) %}<div class="ui-skel-row"><span class="ui-bone ui-w30"></span><span class="ui-bone ui-w18"></span><span class="ui-bone ui-w18"></span><span class="ui-bone ui-w14"></span><span class="ui-bone ui-bone-badge"></span></div>{% endfor %}</div>
  <div class="ui-skel-cards">{% for i in range(6) %}<div class="ui-skel-card"><span class="ui-bone ui-w40"></span><span class="ui-bone ui-w60"></span><span class="ui-bone ui-w30"></span></div>{% endfor %}</div>
  {% elif kind == 'detail' %}
  <div class="ui-skel-detail">
    <div class="ui-skel-group">{% for i in range(2) %}<span class="ui-bone ui-bone-label"></span><div class="ui-skel-rows">{% for j in range(3) %}<div class="ui-skel-row"><span class="ui-bone ui-w40"></span></div>{% endfor %}</div>{% endfor %}</div>
    <div class="ui-skel-side ui-skel-rows">{% for i in range(4) %}<div class="ui-skel-row"><span class="ui-bone ui-w30"></span><span class="ui-bone ui-w30"></span></div>{% endfor %}</div>
  </div>
  {% elif kind == 'form' %}
  <div class="ui-skel-group">{% for i in range(6) %}<span class="ui-bone ui-bone-label"></span><span class="ui-bone ui-bone-control"></span>{% endfor %}<span class="ui-bone ui-bone-btn"></span></div>
  {% else %}
  <div class="ui-skel-group">{% for i in range(2) %}<span class="ui-bone ui-bone-label"></span><div class="ui-skel-rows">{% for j in range(3) %}<div class="ui-skel-row ui-skel-row-setting"><span class="ui-bone ui-w40"></span><span class="ui-bone ui-bone-btn"></span></div>{% endfor %}</div>{% endfor %}</div>
  {% endif %}
</div>
{%- endmacro %}
```

   Note: a page whose `page_title` block renders empty (the dashboard zero state) gets no header at all, so the page keeps one h1. `ui-skel-row-setting` is one more class; add it to the catalog array in step 1 if the lint complains (it is allowed to extend that array). Command: `python3 scripts/design_lint.py`. Expected: OK.

3. Create `App/app/templates/host_page.html`:

```
{#- Design v2 page layout (docs/design/MASTER.md section 5). A page extends
    this, sets `nav` and `body_kind` (list | detail | form | settings) and fills
    only the blocks below with catalog macros. No layout HTML outside blocks. -#}
{% extends "base.html" %}
{% from "_ui.html" import ui_button, ui_icon_button, ui_badge, ui_chip, ui_field, ui_select, ui_textarea, ui_check, ui_toggle, ui_menu_begin, ui_menu_end, ui_menu_item, ui_dialog_begin, ui_dialog_end, ui_empty, ui_tip, ui_pagination, ui_pdot with context %}
{% from "_ui_layout.html" import ui_tabs, ui_toolbar, ui_section, ui_facts, ui_stats, ui_banner, ui_table_begin, ui_table_end, ui_card, ui_skeleton with context %}
{% from "_icons.html" import icon with context %}
{% set body_kind = body_kind | default('list') %}
{% set wrap_class = 'ui-lane-narrow' if body_kind in ('form', 'settings') else '' %}
{% block content %}
{% set page_back = self.back_url() | trim %}
{% set page_meta = self.meta() | trim %}
{% set page_primary = self.primary_action() | trim %}
{% set page_secondary = self.secondary_actions() | trim %}
{% set page_title_html = self.page_title() | trim %}
<div class="ui-page" data-body-kind="{{ body_kind }}">
  {% if page_title_html %}
  <header class="ui-ph" data-list-title-row>
    <div class="ui-ph-main">
      {% if page_back %}<a class="ui-ph-back" href="{{ page_back }}">{{ icon('arrow-left', 16) }}<span>{{ self.back_label() | trim or t('common.back') }}</span></a>{% endif %}
      <h1>{{ page_title_html }}</h1>
      {% if page_meta %}<p class="ui-ph-meta" data-list-meta>{{ page_meta }}</p>{% endif %}
    </div>
    {% if page_primary or page_secondary %}
    <div class="ui-ph-acts" data-list-actions>{{ page_secondary }}{{ page_primary }}</div>
    {% endif %}
  </header>
  {% endif %}
  {% block tabs %}{% endblock %}
  {% block toolbar %}{% endblock %}
  <div class="ui-body ui-body-{{ body_kind }}">{% block body %}{% endblock %}</div>
</div>
{% if false %}{# slot defaults: rendered through self.<name>() above #}
{% block page_title %}{{ self.title() }}{% endblock %}
{% block back_url %}{% endblock %}{% block back_label %}{% endblock %}{% block meta %}{% endblock %}
{% block primary_action %}{% endblock %}{% block secondary_actions %}{% endblock %}
{% endif %}
{% endblock %}
{% block page_skeleton %}
  <div class="page-skeleton" data-page-skeleton role="status" hidden>
    <span class="sr-only">{{ t('a11y.loading') }}</span>
    {{ ui_skeleton(body_kind) }}
  </div>
{% endblock %}
```

   Command: `cd App && .venv/bin/python -c "
import jinja2;env=jinja2.Environment(loader=jinja2.FileSystemLoader('app/templates'));env.globals.update(t=lambda k,**kw:k, show_nav=False)
src='''{% extends \"host_page.html\" %}{% set body_kind = \"form\" %}{% block title %}Hello{% endblock %}{% block meta %}Meta line{% endblock %}{% block primary_action %}{{ ui_button(\"Save\",\"primary\",type=\"submit\") }}{% endblock %}{% block body %}<p>body</p>{% endblock %}'''
html=env.from_string(src).render(csrf_token='x', lang='en', request=None, ubyport_env='mock', current_user=None, workspace_user=None, flash=None, flash_error=None, celebration_milestone=None, operator=lambda: None, security_prompt=None, passkeys_enabled=lambda: False)
print('<h1>Hello</h1>' in html, 'ui-ph-meta' in html, html.count('ui-btn-primary'), 'data-skeleton-kind=\"form\"' in html)"`. Expected: `True True 1 True`. If base.html needs more globals than listed to render in this bare environment, use the FastAPI test client in step 7 instead and skip this command.

4. In `App/app/templates/base.html`, replace Anchor A with:

```
  {% block content %}{% endblock %}
  {% block page_skeleton %}
  <div class="page-skeleton" data-page-skeleton role="status" hidden>
    <span class="sr-only">{{ t('a11y.loading') }}</span>
    <div class="c05-skel" aria-hidden="true">
```

   and replace Anchor B with:

```
      <span class="c05-skel__bone c05-skel__block c05-skel__block--w60"></span>
    </div>
  </div>
  {% endblock %}
</main>
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_skeleton_loaders.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. In `App/app/static/skeleton.js`: replace Anchor C with

```
  var DELAY_MS = 300;
  var MIN_VISIBLE_MS = 400;
  var SAFETY_MS = 15000;
  var shownAt = 0;
```

   replace Anchor E with

```
    el.parentElement.setAttribute("aria-busy", "true");
    el.hidden = false;
    shownAt = Date.now();
```

   and replace Anchor D with

```
  function hide() {
    // A skeleton that flashes for less than MIN_VISIBLE_MS reads as a glitch;
    // keep it up until the minimum has passed (MASTER 5.5).
    var el0 = placeholder();
    if (el0 && !el0.hidden && shownAt && Date.now() - shownAt < MIN_VISIBLE_MS) {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { shownAt = 0; hide(); }, MIN_VISIBLE_MS - (Date.now() - shownAt));
      return;
    }
    window.clearTimeout(timer);
    window.clearTimeout(safety);
    timer = null;
    safety = null;
    shownAt = 0;
    var el = placeholder();
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_skeleton_loaders.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed (the DOWNLOAD_RE test still finds its line).

6. Append to `App/app/static/host2.css`:

```

/* ---- 5 page, header, tabs, toolbar ---- */
.host-workspace .wrap.with-sidebar > .ui-page { max-width: var(--lane); }
.host-workspace .wrap.ui-lane-narrow > .ui-page { max-width: var(--lane-narrow); }
.host-workspace .ui-page { font-size: var(--body-size); line-height: 1.5; color: var(--ink); }
.host-workspace .ui-ph { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-4); padding: 0 0 var(--space-5); border-bottom: 1px solid var(--line); margin: 0 0 var(--space-6); }
.host-workspace .ui-ph h1 { margin: 0; font-size: var(--size-26); font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; }
.host-workspace .ui-ph-meta { margin: var(--space-1) 0 0; color: var(--ink-3); font-size: var(--size-14); }
.host-workspace .ui-ph-back { display: inline-flex; align-items: center; gap: var(--space-1); color: var(--ink-2); text-decoration: none; font-size: var(--size-14); margin: 0 0 var(--space-2); min-height: var(--space-6); }
.host-workspace .ui-ph-acts { display: flex; gap: var(--space-2); align-items: center; flex: none; flex-wrap: wrap; justify-content: flex-end; }
.host-workspace .ui-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line); margin: calc(-1 * var(--space-2)) 0 var(--space-6); overflow-x: auto; scrollbar-width: none; }
.host-workspace .ui-tab { display: flex; align-items: center; height: var(--control-h-phone); padding: 0 var(--space-3); color: var(--ink-2); text-decoration: none; font-size: var(--size-14); font-weight: 600; border-bottom: 2px solid transparent; white-space: nowrap; }
.host-workspace .ui-tab[aria-current="page"] { color: var(--ink); border-color: var(--ink); }
.host-workspace .ui-toolbar { display: flex; align-items: center; gap: var(--space-3); margin: 0 0 var(--space-4); flex-wrap: wrap; }
.host-workspace .ui-toolbar-search { display: flex; align-items: center; gap: var(--space-2); height: var(--control-h); width: calc(var(--space-12) * 5 + var(--space-10)); padding: 0 var(--input-px); border: 1px solid var(--input-border); border-radius: var(--input-radius); background: var(--surface); color: var(--ink-3); }
.host-workspace .ui-toolbar-search .ui-input { border: 0; outline: 0; font: inherit; font-size: var(--size-14); color: var(--ink); background: transparent; width: 100%; min-height: 0; height: auto; padding: 0; box-shadow: none; }
.host-workspace .ui-toolbar-right { margin-left: auto; display: flex; gap: var(--space-2); }

/* ---- 5.4 body kinds, 7.4 table, 7.3 cards ---- */
.host-workspace .ui-body-detail .ui-detail { display: grid; grid-template-columns: 2fr 1fr; gap: var(--space-6); align-items: start; }
.host-workspace .ui-detail-side { position: sticky; top: var(--space-6); }
.host-workspace .ui-section { margin-top: var(--section-gap); }
.host-workspace .ui-section:first-child, .host-workspace .ui-body > .ui-section:first-child { margin-top: 0; }
.host-workspace .ui-section-h { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin: 0 0 var(--space-3); }
.host-workspace .ui-section-h h2 { margin: 0; font-size: var(--size-18); font-weight: 600; }
.host-workspace .ui-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); }
.host-workspace .ui-stat { display: block; text-decoration: none; color: inherit; background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--card-p); }
.host-workspace .ui-stat strong { display: block; font-size: var(--size-26); font-weight: 600; line-height: 1.1; color: var(--ink); }
.host-workspace .ui-stat span { color: var(--ink-2); font-size: var(--size-14); }
.host-workspace .ui-table { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); overflow: hidden; }
.host-workspace .ui-table th { text-align: left; font-size: var(--size-13); font-weight: 500; color: var(--ink-3); height: var(--control-h); padding: 0 var(--row-px); border-bottom: 1px solid var(--line); }
.host-workspace .ui-table td { height: var(--row-h); padding: 0 var(--row-px); border-bottom: 1px solid var(--line); vertical-align: middle; color: var(--ink-2); font-size: var(--body-size); }
.host-workspace .ui-table tr:last-child td { border-bottom: 0; }
.host-workspace .ui-table .ui-row:hover td, .host-workspace .ui-table .ui-row:focus-within td { background: var(--surface-2); }
.host-workspace .ui-table .ui-cell-first, .host-workspace .ui-table .ui-cell-first a { color: var(--ink); font-weight: 600; text-decoration: none; }
.host-workspace .ui-sub { display: block; font-size: var(--size-13); color: var(--ink-3); font-weight: 400; }
.host-workspace .ui-table .ui-cell-r { text-align: right; }
.host-workspace .ui-table .ui-cell-acts { text-align: right; white-space: nowrap; }
.host-workspace .ui-cards { display: none; }
.host-workspace .ui-card { display: block; background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--row-py) var(--row-px); min-height: calc(var(--row-h) + var(--space-6) + var(--space-1)); text-decoration: none; color: inherit; position: relative; }
.host-workspace .ui-card-l1 { display: flex; justify-content: space-between; align-items: center; gap: var(--space-2); font-weight: 600; font-size: var(--size-16); color: var(--ink); }
.host-workspace .ui-card-l2 { display: block; color: var(--ink-2); margin-top: calc(var(--space-1) / 2); }
.host-workspace .ui-card-l3 { display: block; color: var(--ink-3); font-size: var(--size-13); margin-top: calc(var(--space-1) / 2); }
.host-workspace .ui-card-menu { position: absolute; right: var(--space-1); bottom: var(--space-1); }
.host-workspace .ui-facts { background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--space-1) var(--row-px); margin: 0; }
.host-workspace .ui-facts div { display: flex; justify-content: space-between; gap: var(--space-4); min-height: var(--control-h-phone); align-items: center; border-bottom: 1px solid var(--line); }
.host-workspace .ui-facts div:last-child { border-bottom: 0; }
.host-workspace .ui-facts dt { color: var(--ink-3); font-size: var(--size-13); margin: 0; }
.host-workspace .ui-facts dd { margin: 0; color: var(--ink); text-align: right; }
.host-workspace .ui-banner { display: flex; gap: var(--space-3); align-items: center; padding: var(--space-3) var(--row-px); border-radius: var(--card-radius); background: var(--surface); border: 1px solid var(--line); margin: 0 0 var(--space-6); color: var(--ink); }
.host-workspace .ui-banner-attention { background: var(--st-attention-bg); border-color: transparent; color: var(--st-attention-ink); }
.host-workspace .ui-gcard { background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--card-p); margin: 0 0 var(--space-2); }
.host-workspace .ui-body-settings .ui-section { max-width: var(--lane-narrow); }

/* ---- 5.5 skeleton ---- */
.host-workspace .ui-skel { max-width: var(--lane); }
.host-workspace .ui-bone { display: block; background: var(--surface-2); border-radius: var(--radius-1); animation: ui-pulse 1.6s ease-in-out infinite; height: var(--size-14); }
@keyframes ui-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
.host-workspace .ui-skel-h { display: flex; justify-content: space-between; align-items: flex-end; padding: 0 0 var(--space-5); border-bottom: 1px solid var(--line); margin: 0 0 var(--space-6); }
.host-workspace .ui-bone-title { width: calc(var(--space-12) * 5); height: var(--size-26); }
.host-workspace .ui-bone-meta { width: calc(var(--space-12) * 3 + var(--space-4)); height: var(--size-14); margin-top: var(--space-2); }
.host-workspace .ui-bone-btn { width: calc(var(--space-12) * 3); height: var(--control-h); border-radius: var(--control-radius); }
.host-workspace .ui-bone-toolbar { width: calc(var(--space-12) * 5 + var(--space-10)); height: var(--control-h); margin: 0 0 var(--space-4); border-radius: var(--control-radius); }
.host-workspace .ui-bone-label { width: calc(var(--space-12) * 2 + var(--space-1)); height: var(--size-14); margin: 0 0 var(--space-1); }
.host-workspace .ui-bone-control { width: 100%; height: var(--control-h); border-radius: var(--control-radius); margin: 0 0 var(--space-4); }
.host-workspace .ui-bone-badge { width: calc(var(--space-12) + var(--space-8)); height: var(--badge-h); border-radius: var(--radius-pill); margin-left: auto; }
.host-workspace .ui-w10 { width: 10%; } .host-workspace .ui-w14 { width: 14%; } .host-workspace .ui-w18 { width: 18%; } .host-workspace .ui-w30 { width: 30%; } .host-workspace .ui-w40 { width: 40%; } .host-workspace .ui-w60 { width: 60%; }
.host-workspace .ui-skel-rows { background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); overflow: hidden; }
.host-workspace .ui-skel-row { display: flex; gap: var(--row-px); align-items: center; height: var(--row-h); padding: 0 var(--row-px); border-bottom: 1px solid var(--line); }
.host-workspace .ui-skel-row:last-child { border-bottom: 0; }
.host-workspace .ui-skel-row-setting { height: calc(var(--row-h) + var(--space-2)); justify-content: space-between; }
.host-workspace .ui-skel-cards { display: none; flex-direction: column; gap: var(--space-2); }
.host-workspace .ui-skel-card { height: calc(var(--row-h) + var(--space-6) + var(--space-1)); border: 1px solid var(--line); border-radius: var(--card-radius); background: var(--surface); padding: var(--row-py) var(--row-px); display: flex; flex-direction: column; gap: var(--space-2); box-sizing: border-box; }
.host-workspace .ui-skel-group { display: flex; flex-direction: column; gap: var(--space-3); }
.host-workspace .ui-skel-detail { display: grid; grid-template-columns: 2fr 1fr; gap: var(--space-6); align-items: start; }
.host-workspace .page-skeleton[hidden] { display: none; }
.host-workspace .page-skeleton:not([hidden]) ~ *, .host-workspace main[aria-busy="true"] > .ui-page { display: none; }

/* ---- phone ---- */
@media (max-width: 1023px) {
  .host-workspace .ui-ph { flex-direction: column; align-items: stretch; padding-bottom: var(--space-4); margin-bottom: var(--space-4); }
  .host-workspace .ui-ph h1 { font-size: var(--size-22); }
  .host-workspace .ui-ph-acts { flex-direction: column; align-items: stretch; }
  .host-workspace .ui-ph-acts .ui-btn-secondary, .host-workspace .ui-ph-acts .ui-btn-quiet { display: none; }
  .host-workspace .ui-ph-acts .ui-ph-menu { display: inline-flex; }
  .host-workspace .ui-ph-acts .ui-btn-primary { width: 100%; }
  .host-workspace .ui-toolbar-search { width: auto; flex: 1; }
  .host-workspace .ui-toolbar-right { display: none; }
  .host-workspace .ui-toolbar .ui-chips { width: 100%; }
  .host-workspace .ui-table { display: none; }
  .host-workspace .ui-cards { display: flex; flex-direction: column; gap: var(--space-2); }
  .host-workspace .ui-stats { gap: var(--space-2); }
  .host-workspace .ui-stat { padding: var(--space-3); }
  .host-workspace .ui-stat strong { font-size: var(--size-22); }
  .host-workspace .ui-body-detail .ui-detail, .host-workspace .ui-skel-detail { grid-template-columns: 1fr; }
  .host-workspace .ui-detail-side { position: static; order: -1; }
  .host-workspace .ui-banner { flex-wrap: wrap; align-items: flex-start; }
  .host-workspace .ui-banner .grow { flex: 1 1 calc(var(--space-12) * 4); }
  .host-workspace .ui-skel-rows { display: none; }
  .host-workspace .ui-skel-cards { display: flex; }
  .host-workspace .ui-skel-side.ui-skel-rows { display: block; }
}
@media (min-width: 1024px) { .host-workspace .ui-ph-menu { display: none; } }
@media (prefers-reduced-motion: reduce) { .host-workspace .ui-bone { animation: none; } }
```

   Command: `python3 scripts/design_lint.py`. Expected: OK.

7. Create `App/tests/test_design_page_template.py`:

```python
"""host_page.html: slots, body kinds and the matching skeleton (MASTER 5)."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import templating
from app.main import app

TEMPLATES = Path(templating.__file__).resolve().parent / "templates"

SAMPLE = (
    '{% extends "host_page.html" %}{% set nav = "reservations" %}{% set body_kind = KIND %}'
    '{% block title %}Sample{% endblock %}{% block meta %}Meta line{% endblock %}'
    '{% block primary_action %}{{ ui_button("Do it", "primary", href="/x") }}{% endblock %}'
    '{% block secondary_actions %}{{ ui_button("Other", "secondary", href="/y") }}{% endblock %}'
    '{% block tabs %}{{ ui_tabs([("/a", "A", true), ("/b", "B", false)]) }}{% endblock %}'
    '{% block body %}<p class="ui-sub">body</p>{% endblock %}'
)


@pytest.fixture
def sample_route():
    def make(kind):
        name = f"_sample_{kind}.html"
        (TEMPLATES / name).write_text(SAMPLE.replace("KIND", repr(kind)), encoding="utf-8")
        path = f"/__design_sample_{kind}"

        @app.get(path)
        def _view(request):  # pragma: no cover - test only
            return templating.render(request, name, {"nav": "reservations"})
        return path, TEMPLATES / name
    created = []
    yield lambda kind: created.append(make(kind)) or created[-1][0]
    for _, p in created:
        p.unlink(missing_ok=True)


@pytest.mark.parametrize("kind", ["list", "detail", "form", "settings"])
def test_each_body_kind_renders_header_slots_and_its_own_skeleton(sample_route, kind):
    path = sample_route(kind)
    html = TestClient(app).get(path + "?lang=en").text
    assert html.count("<h1") == 1 and "<h1>Sample</h1>" in html
    assert '<p class="ui-ph-meta">Meta line</p>' in html
    assert html.count("ui-btn-primary") == 1
    assert 'class="ui-tab" href="/a" aria-current="page"' in html
    assert f'class="ui-body ui-body-{kind}"' in html
    assert f'data-skeleton-kind="{kind}"' in html
    assert "c05-skel" not in html
    assert 'data-page-skeleton role="status" hidden' in html


def test_pages_that_still_extend_base_keep_the_old_skeleton():
    html = TestClient(app).get("/login?lang=en").text
    assert "data-page-skeleton" in html


def test_skeleton_script_waits_300ms_and_stays_400ms():
    script = (TEMPLATES.parent / "static" / "skeleton.js").read_text(encoding="utf-8")
    assert "var DELAY_MS = 300;" in script and "var MIN_VISIBLE_MS = 400;" in script
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_page_template.py -q --tb=short -x 2>&1 | tail -30`. Expected: `6 passed`. If the sample route needs login (a 303 to `/login`), render the sample through `templating.templates.get_template(name).render(...)` with the `request` of a logged-in test client from `tests.conftest.login_as` instead; keep the same assertions.

8. Widen the cross-page geometry selectors so pages on either layout pass while the pages migrate one brief at a time (the data hooks `data-list-title-row`, `data-list-actions`, `data-list-meta`, `data-sub-tabs`, `data-list-toolbar` are on the v2 markup already). Exact replacements, each occurring once in its file:

   `App/tests/test_host_list_page_layout_browser.py`:
   - `FILLED = ".btn.primary, .btn.accent, .btn.send-all"` -> `FILLED = ".btn.primary, .btn.accent, .btn.send-all, .ui-btn-primary"`
   - `const panel = one('.stays-view, .panel.list-cards');` -> `const panel = one('.stays-view, .list-cards, .ui-body-list');`
   - `const buttons = actions ? [...actions.querySelectorAll('.btn')].filter(visible) : [];` -> `const buttons = actions ? [...actions.querySelectorAll('.btn, .ui-btn')].filter(visible) : [];`
   - `r'<nav class="sub-tabs host-local-nav"[^>]*data-sub-tabs>(.*?)</nav>'` -> `r'<nav class="(?:sub-tabs host-local-nav|ui-tabs)"[^>]*data-sub-tabs[^>]*>(.*?)</nav>'`
   - `r'<a class="sub-tab" href="[^"]+" aria-current="page">([^<]+)</a>'` -> `r'<a class="(?:sub-tab|ui-tab)" href="[^"]+" aria-current="page">([^<]+)</a>'`
   - `assert '<a class="sub-tab" href="/entities">' in client.get("/apartments").text` -> `assert re.search(r'<a class="(?:sub-tab|ui-tab)" href="/entities"', client.get("/apartments").text)`
   - `assert '<a class="sub-tab" href="/entities">' in invoices and "/invoices/settings" not in invoices` -> `assert re.search(r'<a class="(?:sub-tab|ui-tab)" href="/entities"', invoices) and "/invoices/settings" not in invoices`
   - `assert len(re.findall(r'<a class="btn[^"]*"', block)) == 1, (path, block)` -> `assert len(re.findall(r'<a class="(?:btn|ui-btn)[^"]*"', block)) == 1, (path, block)`

   `App/tests/test_host_wide_geometry_browser.py`:
   - `'.page-actions .btn', '.dashboard-actions .btn',` -> `'.page-actions .btn', '.ui-ph-acts .ui-btn', '.dashboard-actions .btn',`
   - `title: box('.page-header-main h1, .host-today-head h1'),` -> `title: box('.page-header-main h1, .ui-ph-main h1, .host-today-head h1'),`
   - `pageHeader: box('.page-header, .host-today-head'),` -> `pageHeader: box('.page-header, .ui-ph, .host-today-head'),`
   - `headerMain: box('.page-header-main, .host-today-head'),` -> `headerMain: box('.page-header-main, .ui-ph-main, .host-today-head'),`
   - `headerActions: box('.page-actions, .dashboard-actions'),` -> `headerActions: box('.page-actions, .ui-ph-acts, .dashboard-actions'),`

   `App/tests/test_host_geometry.py`: `title: edges('.page-header, h1'),` -> `title: edges('.page-header, .ui-ph, h1'),`

   `App/tests/test_host_list_cards_browser.py`: `document.querySelector('.panel.list-cards')` -> `document.querySelector('.list-cards')`

   `App/tests/test_reporting_help_0097.py`: `r('.panel.list-cards')` -> `r('.list-cards')`

   Command: `cd App && .venv/bin/python -m pytest tests/test_host_list_page_layout_browser.py tests/test_host_list_cards_browser.py tests/test_reporting_help_0097.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed (no page is migrated yet, so the v1 branch of every selector is the one exercised).

9. Commit: `git add App/app/templates/host_page.html App/app/templates/_ui_layout.html App/app/static/host2.css App/app/templates/base.html App/app/static/skeleton.js docs/design/catalog.json App/tests && git commit -m "0129 step 9: host_page layout, body kinds and per-kind skeletons"`.

## 5. Do not touch

Page templates; `_components.html`; old stylesheets; `app.js`, `host.js`; the `DOWNLOAD_RE` line in `skeleton.js`; hard rules 2, 3, 6, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- `cd App && .venv/bin/python -m pytest tests/test_design_page_template.py tests/test_skeleton_loaders.py tests/test_design_ui_macros.py -q --tb=short -x 2>&1 | tail -30` expected: all passed.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_download_skeleton_browser.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` expected: all passed, 0 skipped.

## 7. Acceptance

- [ ] The four kinds render their own skeleton; old pages keep the old one.
- [ ] `test_download_skeleton_browser.py` passes (the minimum-visible change does not keep a skeleton up after a download).
- [ ] `git diff df8b842 --stat` lists only section 3 files.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0129-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/host_page.html` (self.block() slot pattern), `App/app/static/skeleton.js` (hide timing).

## Owner steps

None.
