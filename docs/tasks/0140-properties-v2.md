# 0140: Properties list, property page, add property and businesses on the v2 template

Status: todo
Depends on: 0139 | Base commit: 79252fd (refreshed 2026-10-19 against 0130-0137 and 0147-0152; every anchor count below was asserted on a scratch copy of this head and the result compiled and tested) | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0140 step k`. Never push, never open a PR. Page file: `docs/design/pages/properties.md`.

**How to run this brief.** Every step is one command, run from `App/` (`cd App` first; the scripts use paths relative to `App/`). Each script asserts the count of every anchor before it writes anything and prints `ok` at the end; if it prints an `AssertionError` tuple instead (the anchor text and the count it found), nothing was written: stop and put the tuple in the report. Do not retype the scripts and do not edit the files by hand. Known-failing tests are named per step; a failure not named there is yours to report, not to fix by weakening the test.

## 1. Objective

Move `apartments.html` (list), `apartment_form.html` (property page: overview, bookings, settings views; and the add-property page) and `entities.html` (businesses) onto `host_page.html`; swap the hand-drawn `nav_icon` SVGs for the Lucide `icon()` macro; convert buttons, badges, fields and tables in the four property partials (`_property_overview.html`, `_property_calendars.html`, `_property_editor.html`, `_property_create.html`) without touching their structure, ids or `data-*` hooks. The partials are not enforced by the lint; the three pages are.

## 2. Context

Rules: MASTER 4, 5, 5.2 (tabs), 7.3, 7.4, 7.5, `docs/design/pages/properties.md`. The property page keeps its own local tabs (`.property-tabs a[data-property-tab]`, read by five browser tests) and must not carry `data-sub-tabs` (`test_host_list_page_layout_browser.py`). Settled since the first version:

- The properties count is the header meta (with "last synced" after a dot); the toolbar slot renders an empty `ui_toolbar()` so the list layout test finds `[data-list-toolbar]` (the property search lands with its route).
- `entities.html` is `body_kind = 'list'`, not `settings`: the 720 px settings lane made the inline business editor overflow at 1280 (scroll width 1392).
- One DOM per list with roles: property/name `primary`, entity/seat `secondary`, counts `meta` right-aligned, setup state `badge`, the actions cell `actions`; icon-only cells `hide`. Row links that sit in an actions cell are wrapped in `row-action-form` so the phone card lays them out like the stays list.
- Action rows are `ui-btn-group` (never `ui-form-actions`, hidden below 1024). `.panel` boxes that keep a frame (entity editor, add form, empty state) are `ui-section ui-card`.
- The two inline SVGs in `apartments.html` become `icon('external-link', 16)` and `icon('refresh-cw', 16)`; the overview's `nav_icon` map becomes Lucide names.
- Seven browser tests clicked `.btn.primary` selectors on these pages; they move to `.ui-btn-primary` (same assertion). The wide-lane capture reads the v2 wrappers (`.lc-properties`, `.ui-empty`, `.ui-toolbar`).
- Known failures before this brief, not yours: `test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages`, `test_property_navigation_browser.py`, `test_host_property_controls_browser.py` (360 px), `test_property_create_browser.py::test_create_page_fits_...` (`:437 assert 0 == 1`), `test_host_copy_corrections.py::test_copy_correction_pages_browser_evidence` (`wait_for_function` timeout). `test_host_list_page_layout_browser.py` fails on tab/toolbar rhythm until the four lists are v2 (fees come with 0142); its properties `[40, 42]` height check passes after this brief.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartments.html` | edit | head, meta, toolbar slot (script 1); icons, roles, badges (script 2) |
| `App/app/templates/apartment_form.html` | edit | head, blocks, local tabs classes |
| `App/app/templates/entities.html` | edit | head (`list` kind), style block out, roles, action rows |
| `App/app/templates/_property_overview.html` | edit | Lucide icons, badges, action row |
| `App/app/templates/_property_calendars.html` | edit | buttons, badges, feed table roles, fields |
| `App/app/templates/_property_editor.html` | edit | buttons, fields, pairs |
| `App/app/templates/_property_create.html` | edit | icons, buttons, one style |
| `App/app/static/host2.css` | edit | the three entities rules (script 1) |
| `docs/design/catalog.json` | edit | enforce the three pages; legacy lists (script 3) |
| `App/tests/test_properties_table_chips.py` | edit | v2 badge, icon, primary strings; `_nav_icon_svg` helper removed |
| `App/tests/test_host_properties_navigation.py` | edit | v2 table, badge, tab strings |
| `App/tests/test_host_property_controls_browser.py`, `App/tests/test_properties_inline_controls_browser.py`, `App/tests/test_calendar_sync_ui.py`, `App/tests/test_property_navigation_browser.py`, `App/tests/test_wp28_ui_sweep.py`, `App/tests/test_property_readiness.py`, `App/tests/test_property_create_browser.py` | edit | one or more strings or selectors each (script 4) |
| `App/tests/test_fee_setup_compatibility.py`, `App/tests/test_host_copy_corrections.py`, `App/tests/test_host_unsaved_changes_browser.py`, `App/tests/test_lock_navigation_browser.py`, `App/tests/test_host_wide_geometry_browser.py` | edit | `.btn.primary`/`a.btn` selectors to `.ui-btn-primary`/`a.ui-btn`; wide-lane selectors |
| `App/tests/test_design_properties.py` | create | header, tabs, icon, roles, kinds, no `nav_icon` |

No other file may change.

## 4. Steps

1. Heads and the entities CSS:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("app/templates/apartments.html", [("""{% extends "base.html" %}
{% set nav = 'apartments' %}
{% block title %}{{ t('apartments.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import list_page_header, list_toolbar, list_section_heading, empty_state, row_menu_begin, row_menu_end, property_identity, nav_icon, help_tip, copy_icon with context %}
{% set header_actions %}
  {% if rows %}<a class="btn primary sync-btn" href="/apartments/new"><span class="sync-btn-icon" aria-hidden="true">{{ nav_icon('property') }}</span><span>{{ t('apartments.add') }}</span></a>{% endif %}
{% endset %}
{#- 0099: the shared records (Business & legal details, Door lock account)
    are this section's sub-page tabs under the title (0078 shared scope). -#}
{{ list_page_header(
  t('apartments.title'),
  actions=header_actions,
  meta=(t('dashboard.last_synced', when=last_sync | datetime_local) if last_sync else '')
) }}

{% if rows %}
{{ list_toolbar(tp('properties.list.count', rows | length)) }}
""", """{% extends "host_page.html" %}
{% set nav = 'apartments' %}
{% set body_kind = 'list' %}
{% from "_components.html" import list_section_heading, empty_state, row_menu_begin, row_menu_end, property_identity, help_tip, copy_icon with context %}
{% from "_ui_layout.html" import ui_toolbar, ui_section_tabs with context %}
{% block title %}{{ t('apartments.title') }}{% endblock %}
{#- properties.md: the count line is the meta (the toolbar's right side is hidden below 1024 px). -#}
{% block meta %}{% if rows %}{{ tp('properties.list.count', rows | length) }}{% if last_sync %} · {% endif %}{% endif %}{% if last_sync %}{{ t('dashboard.last_synced', when=last_sync | datetime_local) }}{% endif %}{% endblock %}
{% block primary_action %}{% if rows %}{{ ui_button(t('apartments.add'), 'primary', href='/apartments/new', icon_name='house') }}{% endif %}{% endblock %}
{#- 0099: the shared records (Business & legal details, Door lock account) are this section's tabs. -#}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{#- The toolbar is the list layout's slot (0099 layout test); the property search lands with its route. -#}
{% block toolbar %}{% if rows %}{{ ui_toolbar() }}{% endif %}{% endblock %}
{% block body %}
{% if rows %}
""")])
patch("app/templates/apartment_form.html", [
 ("""{% extends "base.html" %}
{% set nav = 'apartments' %}
{% set editing = apartment is not none %}
""", """{% extends "host_page.html" %}
{% set nav = 'apartments' %}
{% set editing = apartment is not none %}
{% set body_kind = 'detail' if editing else 'form' %}
"""),
 ("""{% block content %}
{% from "_components.html" import page_header, breadcrumb, copy_button, copy_inline, nav_icon, source_badge, field_label, help_tip, sync_calendars_button with context %}
""", """{% block page_title %}{{ apartment.internal_name if editing else t('property_create.title') }}{% endblock %}
{% block meta %}{{ (apartment.city_en or apartment.addr_obec or '') if editing else t('property_create.lede') }}{% endblock %}
{% block back_url %}/apartments{% endblock %}
{% block back_label %}{{ t('apartment.form.back') if editing else t('nav.properties') }}{% endblock %}
{% block body %}
{% from "_components.html" import copy_button, copy_inline, source_badge, field_label, help_tip, sync_calendars_button with context %}
"""),
 ("""{% if not editing %}
{{ breadcrumb([{'url': '/apartments', 'label': t('nav.properties')}, {'label': t('property_create.title')}]) }}
{{ page_header(t('property_create.title'), t('property_create.lede')) }}
{% include "_property_create.html" %}
{% else %}
{{ page_header(
  apartment.internal_name,
  apartment.city_en or apartment.addr_obec or '',
  '/apartments',
  t('apartment.form.back')
) }}
""", """{% if not editing %}
{% include "_property_create.html" %}
{% else %}
"""),
 ("""<nav class="property-tabs" aria-label="{{ t('property_nav.tabs_aria') }}">""", """<nav class="ui-tabs property-tabs" aria-label="{{ t('property_nav.tabs_aria') }}">"""),
 ("""  <a href="{{ base_url }}?view={{ key }}" data-property-tab="{{ key }}"{% if key == property_view %} aria-current="page"{% endif %}>{{ label }}</a>""",
  """  <a class="ui-tab" href="{{ base_url }}?view={{ key }}" data-property-tab="{{ key }}"{% if key == property_view %} aria-current="page"{% endif %}>{{ label }}</a>"""),
])
patch("app/templates/entities.html", [("""{% extends "base.html" %}
{% set nav = 'entities' %}
{% block title %}{{ t('entities.title') }}{% endblock %}

{% block content %}
{% from "_components.html" import page_header, breadcrumb, onboarding_banner, row_menu_begin, row_menu_end, help_tip with context %}
{% from "_entity_business_fields.html" import business_form_body, ico_field, register_messages, register_lookup_saved with context %}
{% from "_entity_invoice_fields.html" import invoice_fields with context %}
<style>
  .entities-page tbody tr .row-actions > * { opacity: 1; }
  .entities-page .row-menu-item[aria-disabled="true"] { color: var(--muted); cursor: not-allowed; }
  .entities-page .row-menu-explanation { max-width: 240px; margin: 0 8px 6px; color: var(--muted); font-size: 12px; line-height: 1.45; }
</style>
{{ breadcrumb([
  {'label': t('nav.properties'), 'url': '/apartments'},
  {'label': t('entities.title'), 'url': ''}
]) }}
{{ page_header(t('entities.title'), t('entities.lede'), next_path or '/apartments', t('common.back') if next_path else t('entities.back')) }}
""", """{% extends "host_page.html" %}
{% set nav = 'entities' %}
{#- list kind: the businesses table plus the inline editor; the settings lane (720 px) makes the editor grid overflow at 1280. -#}
{% set body_kind = 'list' %}
{% from "_components.html" import onboarding_banner, row_menu_begin, row_menu_end, help_tip with context %}
{% from "_entity_business_fields.html" import business_form_body, ico_field, register_messages, register_lookup_saved with context %}
{% from "_entity_invoice_fields.html" import invoice_fields with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{# The three Save buttons sit in exclusive branches (editor, add form): one class variable, one coral at a time. #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('entities.title') }}{% endblock %}
{% block meta %}{{ t('entities.lede') }}{% endblock %}
{% block back_url %}{{ next_path or '/apartments' }}{% endblock %}
{% block back_label %}{{ t('common.back') if next_path else t('entities.back') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
""")])
p = pathlib.Path("app/static/host2.css"); s = p.read_text(encoding="utf-8")
assert "0140: businesses page" not in s
s = s.rstrip("\n") + """

/* 0140: businesses page, moved out of entities.html */
.host-workspace .entities-page tbody tr .row-actions > * { opacity: 1; }
.host-workspace .entities-page .row-menu-item[aria-disabled="true"] { color: var(--ink-3); cursor: not-allowed; }
.host-workspace .entities-page .row-menu-explanation { max-width: 15rem; margin: 0 var(--space-2) var(--space-2); color: var(--ink-3); font-size: var(--size-12); line-height: 1.45; }
"""
p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('apartments.html'); templates.env.get_template('apartment_form.html'); templates.env.get_template('entities.html'); print('compiled')"`. Expected: `compiled`. Commit `0140 step 1`.

2. Icons, roles, badges, controls, fields (pages and partials):

```
.venv/bin/python - <<'EOF'
import pathlib, re
def patch(name, pairs, forbid=()):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:70], s.count(old)); s = s.replace(old, new)
    for f in forbid:
        assert f not in s, (name, f)
    p.write_text(s, encoding="utf-8")
B = {"grey": ("neutral", "grey"), "green": ("done", "green"), "amber": ("action", "amber"), "red": ("action", "red")}
def pill(t): return f'class="ui-badge ui-badge-{B[t][0]}" data-tone="{B[t][1]}"'
CPT = 'class="ui-btn ui-btn-secondary ui-btn-compact"'
SEC = 'class="ui-btn ui-btn-secondary"'
ACTS = '<td class="ui-cell-acts row-actions" data-card="actions" data-label="">'
ICON = {"property": "house", "calendar": "calendar-days", "report": "send", "entity": "receipt", "link": "external-link", "lock": "key-round", "coins": "coins", "users": "users", "automation": "settings"}
def icons(s, n):
    found = re.findall(r"nav_icon\('([a-z]+)'\)", s); assert len(found) == n, (n, found)
    return re.sub(r"nav_icon\('([a-z]+)'\)", lambda m: "icon('%s', 20)" % ICON[m.group(1)], s)

# properties list: one DOM, MASTER 7.3 roles; the two hand-drawn SVGs become Lucide icons (lint T5)
p = pathlib.Path("app/templates/apartments.html"); s = p.read_text(encoding="utf-8")
svgs = re.findall(r'<svg width="16"[^>]*>.*?</svg>', s, re.S); assert len(svgs) == 2, len(svgs)
s = s.replace(svgs[0], "{{ icon('external-link', 16) }}", 1).replace(svgs[1], "{{ icon('refresh-cw', 16) }}", 1)
p.write_text(s, encoding="utf-8")
patch("apartments.html", [
 ('<div class="panel tight scroll-x list-cards lc-properties">', '<div class="list-cards lc-properties">', 1),
 ('<table class="table-cards properties-table">', '<table class="ui-table ui-table-stack properties-table">', 1),
 ("<th>{{ t('apartments.table.calendars') }}</th>", "<th class=\"ui-cell-r\">{{ t('apartments.table.calendars') }}</th>", 1),
 ("<th>{{ t('apartments.table.stays') }}</th>", "<th class=\"ui-cell-r\">{{ t('apartments.table.stays') }}</th>", 1),
 ("<td data-label=\"{{ t('apartments.table.property') }}\">\n          <a class=\"row-primary-link\"", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('apartments.table.property') }}\">\n          <a class=\"row-primary-link\"", 1),
 ("<td data-label=\"{{ t('apartments.table.entity') }}\">", "<td data-card=\"secondary\" data-label=\"{{ t('apartments.table.entity') }}\">", 1),
 ("<td class=\"num\" data-label=\"{{ t('apartments.table.calendars') }}\">", "<td class=\"ui-num ui-cell-r\" data-card=\"meta\" data-label=\"{{ t('apartments.table.calendars') }}\">", 1),
 ("<td class=\"num\" data-label=\"{{ t('apartments.table.stays') }}\">", "<td class=\"ui-num ui-cell-r\" data-card=\"meta\" data-label=\"{{ t('apartments.table.stays') }}\">", 1),
 ("<td data-label=\"{{ t('apartments.table.setup') }}\">", "<td data-card=\"badge\" data-label=\"{{ t('apartments.table.setup') }}\">", 1),
 ('<td class="nowrap row-actions" data-label="">', ACTS, 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1), ('class="pill amber"', pill("amber"), 2),
 # property summaries: the property cell leads the phone card; the control cells stack under it
 ('<div class="panel tight scroll-x list-cards lc-properties property-summary-panel">', '<div class="list-cards lc-properties property-summary-panel">', 1),
 ('<table class="table-cards property-summary-table">', '<table class="ui-table ui-table-stack property-summary-table">', 1),
 ("<td data-label=\"{{ t('apartments.table.property') }}\">\n            <a class=\"row-primary-link\"", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('apartments.table.property') }}\">\n            <a class=\"row-primary-link\"", 1),
 ('<button class="btn small" type="submit" data-timing-save>', '<button ' + CPT + ' type="submit" data-timing-save>', 1),
 ('<span class="small property-timing-status"', '<span class="ui-sub property-timing-status"', 1),
 ('<code class="mono property-inline-url"', '<code class="ui-mono property-inline-url"', 1),
 ('<code class="mono property-inline-pin-value"', '<code class="ui-mono property-inline-pin-value"', 1),
], forbid=('style="', 'class="btn ', 'class="btn"', 'class="pill', 'nav_icon', '<svg', 'class="small', 'class="num"', 'class="mono'))

patch("entities.html", [
 ('<div class="panel entity-form" id="entity-edit">', '<div class="ui-section ui-card entity-form" id="entity-edit">', 1),
 ('<div class="section-heading" style="margin-top:0">', '<div class="ui-section-h">', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('<div class="actions"><button class="btn primary" type="submit">', '<div class="ui-btn-group"><button class="{{ cta }}" type="submit">', 3),
 ('<div class="panel tight scroll-x entities-page list-cards lc-entities">', '<div class="list-cards lc-entities entities-page">', 1),
 ('<table class="table-cards">', '<table class="ui-table ui-table-stack">', 2),
 ("<th>{{ t('entities.properties') }}</th>", "<th class=\"ui-cell-r\">{{ t('entities.properties') }}</th>", 1),
 ("        <td class=\"col-name\" data-label=\"{{ t('entities.name') }}\">", "        <td class=\"ui-cell-first col-name\" data-card=\"primary\" data-label=\"{{ t('entities.name') }}\">", 2),
 ("<td data-label=\"{{ t('entities.seat') }}\">", "<td data-card=\"secondary\" data-label=\"{{ t('entities.seat') }}\">", 1),
 ("<td class=\"mono\" data-label=\"{{ t('entities.ico') }}\">", "<td class=\"ui-mono\" data-card=\"hide\" data-label=\"{{ t('entities.ico') }}\">", 2),
 ("<td class=\"small\" data-label=\"{{ t('entities.contact') }}\">", "<td data-card=\"meta\" data-label=\"{{ t('entities.contact') }}\">", 1),
 ("<td class=\"num\" data-label=\"{{ t('entities.properties') }}\">", "<td class=\"ui-num ui-cell-r\" data-card=\"meta\" data-label=\"{{ t('entities.properties') }}\">", 1),
 ("<td class=\"small muted\" data-label=\"{{ t('entities.archived') }}\">", "<td data-card=\"secondary\" data-label=\"{{ t('entities.archived') }}\">", 1),
 ('<td class="nowrap row-actions" data-label="">', ACTS, 2),
 ('          <a class="btn small" href="/entities?edit={{ entity.id }}">{{ t(\'common.edit\') }}</a>\n          <a class="btn small" href="/entities?edit={{ entity.id }}#entity-invoice">{{ t(\'host.invoice_settings\') }}</a>',
  '          <span class="row-action-form"><a ' + CPT + ' href="/entities?edit={{ entity.id }}">{{ t(\'common.edit\') }}</a>\n          <a ' + CPT + ' href="/entities?edit={{ entity.id }}#entity-invoice">{{ t(\'host.invoice_settings\') }}</a></span>', 1),
 ('class="pill amber"', pill("amber"), 1),
 ('<div class="panel empty">', '<div class="ui-section ui-card empty">', 1),
 ('<p class="small muted">', '<p class="ui-sub">', 1),
 ('<div class="panel tight scroll-x">', '<div class="ui-section scroll-x">', 1),
 ('<div class="panel entity-add" id="entity-add">', '<div class="ui-section ui-card entity-add" id="entity-add">', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
], forbid=('style="', 'class="btn', 'class="pill', '<style', 'class="small', 'class="num"', 'class="mono"', 'class="actions"', 'class="panel'))

# partials: controls, badges and icons only; structure, ids and panels stay
p = pathlib.Path("app/templates/_property_overview.html"); s = p.read_text(encoding="utf-8"); s = icons(s, 7)
for old, new, n in [
 ('{%- from "_components.html" import nav_icon, copy_button,', '{%- from "_icons.html" import icon with context -%}\n{%- from "_components.html" import copy_button,', 1),
 ('<a class="btn primary" href="{{ setup_progress.continue_url }}">', '<a class="ui-btn ui-btn-primary" href="{{ setup_progress.continue_url }}">', 1),
 ('class="pill amber"', pill("amber"), 1),
 ('<div class="actions">', '<div class="ui-btn-group">', 1),
 ('<div class="actions host-property-card-actions">', '<div class="ui-btn-group host-property-card-actions">', 1),
 ("{% set icons = {'property': 'property', 'calendar': 'calendar', 'guest_link': 'link', 'try_it': 'users', 'police': 'report', 'stay_fee': 'coins', 'door_lock': 'lock', 'automation': 'automation'} %}",
  "{% set icons = {'property': 'house', 'calendar': 'calendar-days', 'guest_link': 'external-link', 'try_it': 'users', 'police': 'send', 'stay_fee': 'coins', 'door_lock': 'key-round', 'automation': 'settings'} %}", 1),
 ("{{ nav_icon(icons[row.key]) }}", "{{ icon(icons[row.key], 20) }}", 1),
 ("""<span class="pill {{ 'green' if readiness.invite_ready else 'grey' }}">""", """<span class="ui-badge ui-badge-{{ 'done' if readiness.invite_ready else 'neutral' }}" data-tone="{{ 'green' if readiness.invite_ready else 'grey' }}">""", 1),
 ("""<span class="pill {{ 'green' if status == 'done' else 'amber' if status == 'waiting' else 'grey' }}">""", """<span class="ui-badge ui-badge-{{ 'done' if status == 'done' else 'action' if status == 'waiting' else 'neutral' }}" data-tone="{{ 'green' if status == 'done' else 'amber' if status == 'waiting' else 'grey' }}">""", 1),
]:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert "nav_icon" not in s and 'class="btn' not in s and 'class="pill' not in s
p.write_text(s, encoding="utf-8")

p = pathlib.Path("app/templates/_property_create.html"); s = p.read_text(encoding="utf-8"); s = icons(s, 7)
for old, new, n in [
 ('{%- from "_components.html" import nav_icon, help_tip with context -%}', '{%- from "_components.html" import help_tip with context -%}\n{%- from "_icons.html" import icon with context -%}', 1),
 ('<div class="actions property-create-actions">', '<div class="ui-btn-group property-create-actions">', 1),
 ('<a class="btn" href="/apartments">', '<a ' + SEC + ' href="/apartments">', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small"', CPT, 1),
 ('<span class="small muted">', '<span class="ui-sub">', 1),
 (' style="max-width:420px"', '', 1),
]:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
assert "nav_icon" not in s and 'class="btn' not in s and 'style="' not in s
p.write_text(s, encoding="utf-8")

patch("_property_calendars.html", [
 ('{%- from "_components.html" import nav_icon, copy_button,', '{%- from "_components.html" import copy_button,', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('<div class="actions">', '<div class="ui-btn-group">', 2),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small danger"', 'class="ui-btn ui-btn-danger ui-btn-compact"', 1),
 ('class="btn small"', CPT, 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1), ('class="pill amber"', pill("amber"), 1), ('class="pill red"', pill("red"), 1),
 ('<table class="table-cards feed-table">', '<table class="ui-table ui-table-stack feed-table">', 1),
 ("<td data-label=\"{{ t('apartment.form.feed.name') }}\">", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('apartment.form.feed.name') }}\">", 1),
 ("<td data-label=\"{{ t('apartment.form.feed.portal') }}\">", "<td data-card=\"meta\" data-label=\"{{ t('apartment.form.feed.portal') }}\">", 1),
 ("<td class=\"nowrap\" data-label=\"{{ t('apartment.form.feed.last_sync') }}\">", "<td class=\"nowrap\" data-card=\"badge\" data-label=\"{{ t('apartment.form.feed.last_sync') }}\">", 1),
 ("<td class=\"small mono truncate\" data-label=\"{{ t('apartment.form.feed.url') }}\">", "<td class=\"ui-mono truncate\" data-card=\"secondary\" data-label=\"{{ t('apartment.form.feed.url') }}\">", 1),
 ('<td class="row-actions" data-label="">\n              <form method="post" action="/feeds/{{ feed.id }}/delete" class="inline"', '<td class="ui-cell-acts row-actions" data-card="actions" data-label="">\n              <form method="post" action="/feeds/{{ feed.id }}/delete" class="inline row-action-form"', 1),
 ('<div class="small muted">', '<div class="ui-sub">', 1),
 ('<div class="small err-text">', '<div class="ui-sub err-text">', 1),
 ('<div class="field">', '<div class="ui-field">', 3),
 ('<div class="field calendar-other-platform">', '<div class="ui-field calendar-other-platform">', 1),
], forbid=('style="', 'class="btn', 'class="pill', 'class="small', 'class="actions"', 'nav_icon'))

patch("_property_editor.html", [
 ('{%- from "_components.html" import nav_icon, copy_button,', '{%- from "_components.html" import copy_button,', 1),
 ('<p class="small" style="margin:10px 0 0" role="status">', '<p class="ui-sub" role="status">', 1),
 ('<p class="small muted" style="margin:4px 0 0">', '<p class="ui-sub">', 1),
 ('<div class="actions host-property-save">', '<div class="ui-btn-group host-property-save">', 1),
 ('<div class="actions">', '<div class="ui-btn-group">', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small police-sample-link"', 'class="ui-btn ui-btn-secondary ui-btn-compact police-sample-link"', 1),
 ('class="btn small"', CPT, 5),
 ('class="btn"', SEC, 6),
 ('<p class="small muted police-no-credentials">', '<p class="ui-sub police-no-credentials">', 1),
 ('class="small muted"', 'class="ui-sub"', 6),
 ('<p class="small fee-return-note">', '<p class="ui-sub fee-return-note">', 1),
 ('<p class="small warn-text">', '<p class="ui-sub warn-text">', 1),
 ('class="small"', 'class="ui-sub"', 5),
 ('<input type="text" id="permalink_pin" name="permalink_pin" value="{{ pin }}" class="mono"', '<input type="text" id="permalink_pin" name="permalink_pin" value="{{ pin }}" class="ui-mono"', 1),
 ('<div class="field grow">', '<div class="ui-field grow">', 1),
 ('<div class="field guest-link-url">', '<div class="ui-field guest-link-url">', 1),
 ('<div class="field guest-link-pin">', '<div class="ui-field guest-link-pin">', 1),
 ('class="field"', 'class="ui-field"', 14),
 ('<div class="grid two">', '<div class="ui-pair">', 4),
], forbid=('class="btn', 'class="pill', 'class="small', 'class="actions', 'class="field"', 'class="field ', 'nav_icon'))
print("ok")
EOF
```

   Expected: `ok`. Then the compile command of step 1 again. Expected: `compiled`. Commit `0140 step 2`.

3. Catalog:

```
.venv/bin/python - <<'EOF'
import json, pathlib
p = pathlib.Path("../docs/design/catalog.json"); s = p.read_text(encoding="utf-8")
LEGACY = {
 "apartments.html": ["btn-icon", "heading-with-tip", "lc-properties", "list-cards", "list-section-heading", "properties-table", "property-inline-form", "property-inline-icons", "property-inline-link", "property-inline-pin", "property-inline-pin-value", "property-inline-timing", "property-inline-url", "property-inline-value", "property-summaries", "property-summaries-head", "property-summaries-title", "property-summary-panel", "property-summary-table", "property-timing-form", "property-timing-hours", "property-timing-status", "row-actions", "row-primary-link"],
 "apartment_form.html": ["property-tabs", "property-view", "property-views"],
 "entities.html": ["col-name", "danger", "empty", "entities-page", "entity-add", "entity-form", "entity-linked", "entity-linked-label", "entity-linked-list", "entity-section", "entity-section-head", "entity-section-title", "invoice-settings-form", "lc-entities", "list-cards", "muted", "row-actions", "row-menu-explanation", "row-primary-link", "row-selected", "scroll-x"],
}
old = '"App/app/templates/guest_form_admin.html"],\n  "legacy": {\n'
assert s.count(old) == 1, s.count(old)
new = ('"App/app/templates/guest_form_admin.html", ' + ", ".join(f'"App/app/templates/{n}"' for n in LEGACY) + '],\n  "legacy": {\n'
       + "".join(f'    "App/app/templates/{n}": {json.dumps(t)},\n' for n, t in LEGACY.items()))
s = s.replace(old, new); json.loads(s); p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then `cd .. && python3 scripts/design_lint.py && cd App`. Expected: `design lint: OK`. Commit `0140 step 3`.

4. Tests:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("tests/test_properties_table_chips.py", [
 ("""    assert re.search(r'<span class="pill (amber|green|red)">', page)""", """    assert re.search(r'<span class="ui-badge ui-badge-(?:action|done)" data-tone="(amber|green|red)">', page)"""),
 ("""    assert 'class="btn primary sync-btn"' in cta
    assert 'class="sync-btn-icon" aria-hidden="true"' in cta
    assert 'class="nav-icon"' in cta
""", """    assert 'class="ui-btn ui-btn-primary"' in cta
    assert 'class="ui-icon"' in cta
"""),
 ("""    assert _nav_icon_svg("property") in cta
    assert _nav_icon_svg("calendar") not in cta


def _nav_icon_svg(name: str) -> str:
    lines = _COMPONENTS.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if f"{{% elif name == '{name}' %}}" in line:
            return lines[index + 1].strip()
    raise AssertionError(f"no icon named {name}")
""", """    assert 'data-icon="house"' in cta
    assert 'data-icon="calendar-days"' not in cta
"""),
 ("""    assert 'class="btn primary sync-btn" href="/apartments/new"' not in empty_host.get("/apartments?lang=en").text""",
  """    assert 'class="ui-ph-acts"' not in empty_host.get("/apartments?lang=en").text"""),
])
patch("tests/test_host_properties_navigation.py", [
 ("""    table = page[page.index('class="table-cards properties-table"'):page.index("</table>")]""", """    table = page[page.index('class="ui-table ui-table-stack properties-table"'):page.index("</table>")]"""),
 ("""    assert re.search(r'<span class="pill (amber|green)">', table)""", """    assert re.search(r'<span class="ui-badge ui-badge-(?:action|done)" data-tone="(amber|green)">', table)"""),
 ("""    assert '<a class="sub-tab" href="/entities">Business &amp; legal details</a>' in host.get("/apartments").text""", """    assert '<a class="ui-tab" href="/entities">Business &amp; legal details</a>' in host.get("/apartments").text"""),
 ("""  const sel = '.sub-tabs a, .properties-table a, .properties-table button, '""", """  const sel = '.ui-tabs a, .properties-table a, .properties-table button, '"""),
])
patch("tests/test_host_property_controls_browser.py", [
 ("""        assert page.locator('.sub-tabs a[aria-current="page"]').inner_text() == "Properties\"""", """        assert page.locator('.ui-tabs a[aria-current="page"]').inner_text() == "Properties\""""),
])
patch("tests/test_properties_inline_controls_browser.py", [
 ("""    assert 'class="panel tight scroll-x list-cards lc-properties property-summary-panel"' in summary""", """    assert 'class="list-cards lc-properties property-summary-panel"' in summary"""),
])
patch("tests/test_calendar_sync_ui.py", [("""    assert 'class="pill red"' in table""", """    assert 'data-tone="red"' in table""")])
patch("tests/test_property_navigation_browser.py", [("""    assert 'class="pill red"' in one""", """    assert 'data-tone="red"' in one""")])
patch("tests/test_wp28_ui_sweep.py", [("""    assert 'class="table-cards feed-table"' in page""", """    assert 'class="ui-table ui-table-stack feed-table"' in page""")])
patch("tests/test_property_readiness.py", [("""    assert '<div class="banner warning">' not in page.text""", """    assert '<div class="ui-banner ui-banner-attention">' not in page.text""")])
patch("tests/test_property_create_browser.py", [("""    content = page[page.index('<header class="page-header"'):]""", """    content = page[page.index('<header class="ui-ph"'):]""")])

# browser tests that click the property pages' Save/Continue buttons by their legacy class
def patchn(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patchn("tests/test_fee_setup_compatibility.py", [("""'#property-settings-form button.btn.primary[type="submit"]'""", """'#property-settings-form button.ui-btn-primary[type="submit"]'""", 1)])
patchn("tests/test_host_copy_corrections.py", [('".property-create-actions .btn.primary"', '".property-create-actions .ui-btn-primary"', 1)])
patchn("tests/test_property_create_browser.py", [('".property-create-actions .btn.primary"', '".property-create-actions .ui-btn-primary"', 5)])
patchn("tests/test_property_navigation_browser.py", [('".property-create-actions .btn.primary"', '".property-create-actions .ui-btn-primary"', 1), ('".host-property-save .btn.primary"', '".host-property-save .ui-btn-primary"', 3)])
patchn("tests/test_host_unsaved_changes_browser.py", [('".host-property-save .btn.primary"', '".host-property-save .ui-btn-primary"', 1), ('"#entity-edit .section-heading a.btn"', '"#entity-edit .ui-section-h a.ui-btn"', 1)])
patchn("tests/test_lock_navigation_browser.py", [('"#door-code a.btn"', '"#door-code a.ui-btn"', 1)])
pathlib.Path("tests/test_design_properties.py").write_text('''"""0140: properties pages render on host_page; the property page keeps its local tabs."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import host_with_property, empty_host  # noqa: F401


def test_properties_list_header_tabs_and_icon(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-tabs" data-sub-tabs' in page and 'data-icon="house"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert 'class="ui-table ui-table-stack properties-table"' in page and 'data-card="primary"' in page


def test_property_page_keeps_local_tabs_without_section_tabs(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    match = re.search(r'data-href="(/apartments/\\d+)"', page)
    assert match
    detail = host_with_property.get(match.group(1) + "?lang=en").text
    assert '<nav class="ui-tabs property-tabs"' in detail and "data-sub-tabs" not in detail
    assert detail.count('data-property-tab="') == 3 and 'class="ui-ph-back"' in detail


def test_add_property_and_businesses_are_v2_pages(empty_host):
    assert 'data-body-kind="form"' in empty_host.get("/apartments/new?lang=en").text
    assert 'data-body-kind="list"' in empty_host.get("/entities?lang=en").text


def test_no_nav_icon_or_raw_style_in_the_property_templates():
    for name in ("apartments.html", "apartment_form.html", "entities.html", "_property_overview.html",
                 "_property_create.html", "_property_calendars.html"):
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert "nav_icon" not in text and 'style="' not in text, name
        assert 'class="btn"' not in text and 'class="btn ' not in text, name
''', encoding="utf-8")
patchn("tests/test_host_wide_geometry_browser.py", [
 ('    "properties": ("/apartments", ".panel.tight.scroll-x, .panel.empty"),', '    "properties": ("/apartments", ".lc-properties, .ui-empty"),', 1),
 ('    "operators": ("/entities", ".entities-page, .panel.empty"),', '    "operators": ("/entities", ".entities-page, .ui-empty"),', 1),
 ("filterToolbar: box('.filter-toolbar'),", "filterToolbar: box('.filter-toolbar, .ui-toolbar'),", 1),
])
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -m pytest tests/test_design_properties.py tests/test_properties_table_chips.py tests/test_host_properties_navigation.py tests/test_calendar_sync_ui.py tests/test_wp28_ui_sweep.py tests/test_property_readiness.py tests/test_fee_setup_compatibility.py tests/test_entit*.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -30`. Expected: all passed except the known `test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages`. Commit `0140 step 4`.

5. Browser: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_unsaved_changes_browser.py tests/test_properties_inline_controls_browser.py tests/test_lock_navigation_browser.py tests/test_property_create_browser.py tests/test_property_navigation_browser.py tests/test_host_property_controls_browser.py tests/test_host_list_cards_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_wide_geometry_browser.py -q --tb=line 2>&1 | tail -30`. Expected: `test_host_unsaved_changes_browser`, `test_properties_inline_controls_browser`, `test_lock_navigation_browser`, `test_host_list_cards_browser` and `test_host_wide_geometry_browser` pass with 0 skipped; the known failures from section 2 may remain (quote each message in the report; the `properties` `[40, 42]` assertion of the list layout test must not be among them).

6. Screenshots: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers SHOT_TASK=0140 SHOT_PAGES="properties property add-property entities" .venv/bin/python -m pytest -p tests.conftest /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shoot_pages.py -q -s 2>&1 | tail -8`. Eight files under `.../scratchpad/shots/0140/`. Then `git status --short | head -20`: the only changes must be the files in section 3. If a tracked evidence folder changed (for example `docs/tasks/0087-evidence/`), `git checkout -- <that folder>` before committing.

7. Commit: `git add App/app/templates App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0140 step 7: properties, property page and businesses on host_page"`.

## 5. Do not touch

`app.js` (`initPropertyViews`), routes, `_entity_*_fields.html`, settings-group ids and `data-settings-group`, the onboarding checklist partials; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands; only the known failures named in section 2.

## 7. Acceptance

- [ ] Properties list with tabs, count meta and one primary (Lucide house icon); property page with back link and ink-underline local tabs; add property as a form page; businesses as a list page with the inline editor.
- [ ] Screenshots attached (390 and 1280, four pages).
- [ ] Lint passes with the three pages enforced; no `nav_icon` call left in the six templates.

## 8. Stop and ask

Stop, and write the report, if: a script prints an `AssertionError` instead of `ok`; a test not named as known-failing fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0140-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, the known failures seen (one line each, with the message), deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/apartment_form.html` (view switching), `App/app/templates/_property_editor.html` (settings forms), `App/app/templates/entities.html` (kind change).

## Owner steps

None.
