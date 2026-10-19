# 0140: Properties list, property page, add property and businesses on the v2 template

Status: done
Depends on: 0139 | Base commit: 075294b | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: about 14 tool calls, 30 tool calls at most, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit once at the end (step 8). Never push, never open a PR. Page file: `docs/design/pages/properties.md`.

## 1. Objective

Move `apartments.html` (list), `apartment_form.html` (property page with its overview, bookings and settings views, and the add-property page) and `entities.html` (businesses) onto `host_page.html`, the way `reservations.html` and `reservation_detail.html` already are. Swap the hand-drawn `nav_icon` SVGs for the Lucide `icon` macro, and convert buttons and badges in the four property partials (`_property_overview.html`, `_property_calendars.html`, `_property_editor.html`, `_property_create.html`). Structure, ids, `data-*` hooks, tables and their wrappers do not change.

Kept on purpose (the reconcile found that changing them breaks things):
- tables stay `table-cards` inside `panel tight scroll-x list-cards ...`: `test_host_list_cards_browser.py` and the wide-geometry lane tests read the card switch and `.panel.tight.scroll-x`;
- `.field`, `.actions`, `.num`, `.mono` and `.panel` stay: `app.js` reads `.field` (`syncAutomationHours`) and `.actions [type=submit]`; these tokens go in the catalog's `legacy` lists;
- businesses is a `list` page (same lane and tabs as the other Properties tabs), not `settings`: a 720 px settings lane turns its table into cards at 1280.

## 2. Context

Rules: MASTER 5, 5.2 (tabs), 7.1, 7.4, 7.5, and the page file. Every script below was dry-run against commit 075294b (after 0141) and passes. The property page keeps its own local tabs (`.property-tabs a[data-property-tab]`, read by app.js `initPropertyViews` and by the browser tests) and must not get `data-sub-tabs`. A new host2.css block restyles those tabs from the old host.css pills to the ink underline, and lets the businesses forms fill the page lane (app.css capped them at 700 px, which put them off the header's right edge in the wide-geometry test).

Run every script from `App/` with `.venv/bin/python - <<'EOF' ... EOF` (step 3 runs from the repo root). Each script asserts its own anchors and counts. If one stops with an AssertionError, stop and report (section 8). Do not fix it by hand.

Browser tests need `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`. Without it, Playwright looks for a headless-shell build that is not installed.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartments.html` | edit | host_page head, Lucide icons, badges (step 1, 2) |
| `App/app/templates/apartment_form.html` | edit | host_page head, local tabs classes (step 1) |
| `App/app/templates/entities.html` | edit | host_page head, tabs, style block out, buttons (step 1, 2) |
| `App/app/templates/_property_overview.html` | edit | icons, buttons, badges (step 2) |
| `App/app/templates/_property_calendars.html` | edit | buttons, badges (step 2) |
| `App/app/templates/_property_editor.html` | edit | buttons, two margin styles (step 2) |
| `App/app/templates/_property_create.html` | edit | icons, buttons, one style (step 2) |
| `App/app/static/host2.css` | edit | append the 0140 block (step 1) |
| `docs/design/catalog.json` | edit | enforce the three pages; legacy lists (step 3) |
| `App/app/templates/base.html` | edit | host2.css `?v=` key (step 7) |
| `App/tests/static_versions.json` | edit | regenerated (step 7) |
| `App/tests/test_properties_table_chips.py`, `test_host_properties_navigation.py`, `test_host_property_controls_browser.py`, `test_calendar_sync_ui.py`, `test_property_navigation_browser.py`, `test_property_create_browser.py`, `test_host_copy_corrections.py`, `test_fee_setup_compatibility.py`, `test_host_unsaved_changes_browser.py`, `test_lock_navigation_browser.py`, `test_onboarding_followup_browser.py`, `test_host_list_cards_browser.py`, `test_host_list_page_layout_browser.py`, `test_wp28_geometry.py`, `test_host_wide_geometry_browser.py` | edit | old-markup selectors (step 4) |
| `App/tests/test_design_properties.py` | create | slots, tabs, icon (step 4) |

No other file may change.

## 4. Steps

1. Page heads and the host2.css block. From `App/`, run:

```
.venv/bin/python - <<'EOF'
import pathlib
def edit(name, pairs):
    p = pathlib.Path(name); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
T = "app/templates/"
edit(T + "apartments.html", [
("""{% extends "base.html" %}
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
""", """{% extends "host_page.html" %}
{% set nav = 'apartments' %}
{% set body_kind = 'list' %}
{% from "_components.html" import list_section_heading, empty_state, row_menu_begin, row_menu_end, property_identity, help_tip, copy_icon with context %}
{% from "_ui.html" import ui_button with context %}
{% from "_ui_layout.html" import ui_toolbar, ui_section_tabs with context %}
{% from "_icons.html" import icon with context %}
{% block title %}{{ t('apartments.title') }}{% endblock %}
{% block meta %}{% if last_sync %}{{ t('dashboard.last_synced', when=last_sync | datetime_local) }}{% endif %}{% endblock %}
{% block primary_action %}{% if rows %}{{ ui_button(t('apartments.add'), 'primary', href='/apartments/new', icon_name='house') }}{% endif %}{% endblock %}
{#- 0099: the shared records (Business & legal details, Door lock account)
    are this section's sub-page tabs under the title (0078 shared scope). -#}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block toolbar %}{% if rows %}{{ ui_toolbar(actions='<span class="ui-sub">' ~ tp('properties.list.count', rows | length) ~ '</span>') }}{% endif %}{% endblock %}
{% block body %}
"""),
("{{ list_toolbar(tp('properties.list.count', rows | length)) }}\n", ""),
("""<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><circle cx="8" cy="8" r="2" stroke="currentColor" stroke-width="1.4"/></svg>""", "{{ icon('external-link', 16) }}"),
("""<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><path d="M12.5 1.5v3h-3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>""", "{{ icon('refresh-cw', 16) }}"),
])
edit(T + "apartment_form.html", [
('{% extends "base.html" %}\n', '{% extends "host_page.html" %}\n'),
("{% set editing = apartment is not none %}\n", "{% set editing = apartment is not none %}\n{% set body_kind = 'detail' if editing else 'form' %}\n"),
("""{% block content %}
{% from "_components.html" import page_header, breadcrumb, copy_button, copy_inline, nav_icon, source_badge, field_label, help_tip, sync_calendars_button with context %}
""", """{% block meta %}{{ (apartment.city_en or apartment.addr_obec or '') if editing else t('property_create.lede') }}{% endblock %}
{% block back_url %}/apartments{% endblock %}
{% block back_label %}{{ t('apartment.form.back') if editing else t('nav.properties') }}{% endblock %}
{% block body %}
{% from "_components.html" import copy_button, copy_inline, source_badge, field_label, help_tip, sync_calendars_button with context %}
{% from "_icons.html" import icon with context %}
"""),
("""{{ breadcrumb([{'url': '/apartments', 'label': t('nav.properties')}, {'label': t('property_create.title')}]) }}
{{ page_header(t('property_create.title'), t('property_create.lede')) }}
""", ""),
("""{{ page_header(
  apartment.internal_name,
  apartment.city_en or apartment.addr_obec or '',
  '/apartments',
  t('apartment.form.back')
) }}
""", ""),
('<nav class="property-tabs" aria-label=', '<nav class="ui-tabs property-tabs" aria-label='),
('  <a href="{{ base_url }}?view={{ key }}" data-property-tab=', '  <a class="ui-tab" href="{{ base_url }}?view={{ key }}" data-property-tab='),
])
edit(T + "entities.html", [
("""{% extends "base.html" %}
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
{% set body_kind = 'list' %}
{% from "_components.html" import onboarding_banner, row_menu_begin, row_menu_end, help_tip with context %}
{% from "_entity_business_fields.html" import business_form_body, ico_field, register_messages, register_lookup_saved with context %}
{% from "_entity_invoice_fields.html" import invoice_fields with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('entities.title') }}{% endblock %}
{% block meta %}{{ t('entities.lede') }}{% endblock %}
{% block back_url %}{{ next_path or '/apartments' }}{% endblock %}
{% block back_label %}{{ t('common.back') if next_path else t('entities.back') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
"""),
])
css = pathlib.Path("app/static/host2.css"); s = css.read_text(encoding="utf-8")
assert "0140:" not in s
s = s.rstrip("\n") + """

/* 0140: businesses page, moved out of entities.html */
.host-workspace .entities-page tbody tr .row-actions > * { opacity: 1; }
.host-workspace .entities-page .row-menu-item[aria-disabled="true"] { color: var(--ink-3); cursor: not-allowed; }
.host-workspace .entities-page .row-menu-explanation { max-width: 240px; margin: 0 var(--space-2) var(--space-2); color: var(--ink-3); font-size: var(--size-12); line-height: 1.45; }
.host-workspace .ui-body .entity-form, .host-workspace .ui-body .entity-add { max-width: none; } /* the forms share the page lane with the header (app.css capped them at 700px) */
/* 0140: property page local tabs take the ui-tabs look over the host.css .property-tabs pills */
.host-workspace .ui-tabs.property-tabs { flex-wrap: wrap; padding: 0; }
.host-workspace .ui-tabs.property-tabs .ui-tab { min-height: 0; border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: none; }
.host-workspace .ui-tabs.property-tabs .ui-tab[aria-current] { background: none; border-color: var(--ink); color: var(--ink); }
/* 0140: the overview setup tiles' badge keeps the spacing the old .pill had (host.css) */
.host-workspace .setup-status-copy > .ui-badge { margin-top: var(--space-2); white-space: normal; }
"""
css.write_text(s, encoding="utf-8")
print("step1 ok")
EOF
```

   Expected: `step1 ok`. Then, from `App/`: `.venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('apartments.html','apartment_form.html','entities.html','_property_overview.html','_property_create.html','_property_calendars.html','_property_editor.html')]; print('compiled')"`. Expected: `compiled`.

2. Buttons, badges and icons in the three pages and the four partials. From `App/`, run:

```
.venv/bin/python - <<'EOF'
import pathlib, re
def patch(name, pairs, forbid=()):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:60], s.count(old)); s = s.replace(old, new)
    for f in forbid: assert f not in s, (name, f)
    p.write_text(s, encoding="utf-8")
B = {"grey": ("neutral", "grey"), "green": ("done", "green"), "amber": ("action", "amber"), "red": ("action", "red")}
def pill(t): return f'class="ui-badge ui-badge-{B[t][0]}" data-tone="{B[t][1]}"'
ICON = {"property": "house", "calendar": "calendar-days", "report": "send", "entity": "receipt", "link": "external-link", "lock": "key-round", "coins": "coins"}
STATIC = re.compile(r"nav_icon\('([a-z]+)'\)")
def icons(s, n):
    found = STATIC.findall(s); assert len(found) == n, (n, found)
    return STATIC.sub(lambda m: "icon('%s', 20)" % ICON[m.group(1)], s)
NO_BTN = ('class="btn ', 'class="btn"', 'class="pill')
# Tables, table wrappers (.panel, .list-cards, .table-cards), .num, .mono, .field and .actions stay:
# the card switch, the lane geometry tests and app.js (.field, .actions) still read them.
patch("apartments.html", [
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1), ('class="pill amber"', pill("amber"), 2),
], forbid=NO_BTN + ('style="', 'nav_icon', '<path'))
patch("entities.html", [
 ('<div class="section-heading" style="margin-top:0">', '<div class="ui-section-h">', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('class="btn primary"', 'class="{{ cta }}"', 3),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="pill amber"', pill("amber"), 1),
 ('class="small muted"', 'class="ui-sub"', 2),
 ('class="muted"', 'class="ui-sub"', 1), ('class="small"', 'class="ui-sub"', 1),
], forbid=NO_BTN + ('style="', '<style', 'nav_icon'))
p = pathlib.Path("app/templates/_property_overview.html"); s = p.read_text(encoding="utf-8"); s = icons(s, 7)
for old, new, n in [
 ("{% set icons = {'property': 'property', 'calendar': 'calendar', 'guest_link': 'link', 'try_it': 'users', 'police': 'report', 'stay_fee': 'coins', 'door_lock': 'lock', 'automation': 'automation'} %}",
  "{% set icons = {'property': 'house', 'calendar': 'calendar-days', 'guest_link': 'external-link', 'try_it': 'users', 'police': 'send', 'stay_fee': 'coins', 'door_lock': 'key-round', 'automation': 'refresh-cw'} %}", 1),
 ("{{ nav_icon(icons[row.key]) }}", "{{ icon(icons[row.key], 20) }}", 1),
 ('{%- from "_components.html" import nav_icon, copy_button,', '{%- from "_icons.html" import icon with context -%}\n{%- from "_components.html" import copy_button,', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="pill amber"', pill("amber"), 1),
 ("""class="pill {{ 'green' if readiness.invite_ready else 'grey' }}\"""",
  """class="ui-badge ui-badge-{{ 'done' if readiness.invite_ready else 'neutral' }}" data-tone="{{ 'green' if readiness.invite_ready else 'grey' }}\"""", 1),
 ("""class="pill {{ 'green' if status == 'done' else 'amber' if status == 'waiting' else 'grey' }}\"""",
  """class="ui-badge ui-badge-{{ 'done' if status == 'done' else 'action' if status == 'waiting' else 'neutral' }}" data-tone="{{ 'green' if status == 'done' else 'amber' if status == 'waiting' else 'grey' }}\"""", 1),
]:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
for f in NO_BTN + ("nav_icon",): assert f not in s, f
p.write_text(s, encoding="utf-8")
p = pathlib.Path("app/templates/_property_create.html"); s = p.read_text(encoding="utf-8"); s = icons(s, 7)
for old, new, n in [
 ('{%- from "_components.html" import nav_icon, help_tip with context -%}', '{%- from "_components.html" import help_tip with context -%}\n{%- from "_icons.html" import icon with context -%}', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1), ('class="small muted"', 'class="ui-sub"', 1), (' style="max-width:420px"', '', 1)]:
    assert s.count(old) == n, (old[:60], s.count(old)); s = s.replace(old, new)
for f in NO_BTN + ("nav_icon", 'style="'): assert f not in s, f
p.write_text(s, encoding="utf-8")
patch("_property_calendars.html", [
 ('{%- from "_components.html" import nav_icon, copy_button,', '{%- from "_components.html" import copy_button,', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small danger"', 'class="ui-btn ui-btn-danger ui-btn-compact"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1), ('class="pill amber"', pill("amber"), 1), ('class="pill red"', pill("red"), 1),
 ('class="small muted"', 'class="ui-sub"', 1),
], forbid=NO_BTN + ('style="', 'nav_icon'))
patch("_property_editor.html", [
 ('{%- from "_components.html" import nav_icon, copy_button,', '{%- from "_components.html" import copy_button,', 1),
 ('<p class="small" style="margin:10px 0 0" role="status">', '<p class="ui-sub" role="status">', 1),
 ('<p class="small muted" style="margin:4px 0 0">', '<p class="ui-sub">', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small police-sample-link"', 'class="ui-btn ui-btn-secondary ui-btn-compact police-sample-link"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 5),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 6),
 ('class="small muted"', 'class="ui-sub"', 6), ('class="small"', 'class="ui-sub"', 5),
], forbid=NO_BTN + ('nav_icon',))
print("ok")
EOF
```

   Expected: `ok`. Then run the step 1 compile command again. Expected: `compiled`.

3. Catalog. From the repo root, run:

```
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path("docs/design/catalog.json"); c = json.loads(p.read_text(encoding="utf-8"))
LEGACY = {
 "App/app/templates/apartments.html": "btn-icon heading-with-tip lc-properties list-cards list-section-heading mono nowrap num panel properties-table property-inline-form property-inline-icons property-inline-link property-inline-pin property-inline-pin-value property-inline-timing property-inline-url property-inline-value property-summaries property-summaries-head property-summaries-title property-summary-panel property-summary-table property-timing-form property-timing-hours property-timing-status row-actions row-primary-link scroll-x small table-cards tight",
 "App/app/templates/apartment_form.html": "property-tabs property-view property-views",
 "App/app/templates/entities.html": "actions col-name danger empty entities-page entity-add entity-form entity-linked entity-linked-label entity-linked-list entity-section entity-section-head entity-section-title invoice-settings-form lc-entities list-cards mono nowrap num panel row-actions row-menu-explanation row-primary-link row-selected scroll-x table-cards tight",
}
for path, tokens in LEGACY.items():
    if path not in c["enforced_templates"]: c["enforced_templates"].append(path)
    c.setdefault("legacy", {})[path] = sorted(tokens.split())
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("catalog ok")
EOF
```

   Expected: `catalog ok`. Then `python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: `design lint: OK`.

4. Tests. From `App/`, run (it edits the old-markup selectors in fifteen test files and creates `tests/test_design_properties.py`):

```
.venv/bin/python - <<'EOF'
import pathlib
def fix(name, pairs):
    p = pathlib.Path("tests/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
SAVE = (".host-property-save .btn.primary", ".host-property-save .ui-btn-primary")
CREATE = (".property-create-actions .btn.primary", ".property-create-actions .ui-btn-primary")
fix("test_properties_table_chips.py", [
 ("""r'<span class="pill (amber|green|red)">'""", """r'<span class="ui-badge ui-badge-(?:action|done)" data-tone="(amber|green|red)">'""", 1),
 ("""    assert 'class="btn primary sync-btn"' in cta
    assert 'class="sync-btn-icon" aria-hidden="true"' in cta
    assert 'class="nav-icon"' in cta
""", """    assert 'class="ui-btn ui-btn-primary"' in cta
    assert 'class="ui-icon"' in cta
""", 1),
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
""", 1),
 ("""'class="btn primary sync-btn" href="/apartments/new"' not in""", """'class="ui-btn ui-btn-primary" href="/apartments/new"' not in""", 1),
])
fix("test_host_properties_navigation.py", [
 ("""r'<span class="pill (amber|green)">'""", """r'<span class="ui-badge ui-badge-(?:action|done)" data-tone="(amber|green)">'""", 1),
 ("""'<a class="sub-tab" href="/entities">""", """'<a class="ui-tab" href="/entities">""", 1),
 ("""const sel = '.sub-tabs a, """, """const sel = '.ui-tabs a, """, 1),
])
fix("test_host_property_controls_browser.py", [
 ("""'.sub-tabs a[aria-current="page"]'""", """'.ui-tabs a[aria-current="page"]'""", 1),
 ("#operator-picker .btn,", "#operator-picker .ui-btn,", 1),
 ('#calendar-add .btn")', '#calendar-add .ui-btn")', 1),
])
fix("test_calendar_sync_ui.py", [("""'class="pill red"'""", """'data-tone="red"'""", 1)])
fix("test_property_navigation_browser.py", [
 ("""'class="pill red"'""", """'data-tone="red"'""", 1),
 ("""html.index('<nav class="property-tabs"')""", """html.index('<nav class="ui-tabs property-tabs"')""", 1),
 (".property-view.is-active .btn,", ".property-view.is-active .ui-btn,", 1),
 (SAVE[0], SAVE[1], 3), (CREATE[0], CREATE[1], 1),
])
fix("test_property_create_browser.py", [
 ("""page.index('<header class="page-header"')""", """page.index('<header class="ui-ph"')""", 1),
 (".property-create .btn,", ".property-create .ui-btn,", 1),
 (CREATE[0], CREATE[1], 5),
])
fix("test_host_copy_corrections.py", [(CREATE[0], CREATE[1], 1)])
fix("test_fee_setup_compatibility.py", [("""'#property-settings-form button.btn.primary[type="submit"]'""", """'#property-settings-form button.ui-btn-primary[type="submit"]'""", 1)])
fix("test_host_unsaved_changes_browser.py", [
 ('"#entity-edit .section-heading a.btn"', '"#entity-edit .ui-section-h a.ui-btn"', 1),
 (SAVE[0], SAVE[1], 1),
])
fix("test_lock_navigation_browser.py", [('"#door-code a.btn"', '"#door-code a.ui-btn"', 1)])
fix("test_onboarding_followup_browser.py", [
 ('police.locator(".pill.amber")', """police.locator('[data-tone="amber"]')""", 1),
 ('police.locator(".pill.green")', """police.locator('[data-tone="green"]')""", 1),
])
fix("test_host_list_cards_browser.py", [("'tbody td.row-actions a.btn, ", "'tbody td.row-actions a.btn, tbody td.row-actions a.ui-btn, ", 1)])
# v2 header: the meta line sits under the title, beside or above the actions (host_page.html)
fix("test_host_list_page_layout_browser.py", [
 ("""if r["meta"] and r["meta"]["top"] < r["actions"]["bottom"] - 1:
                        failures.append((label, "meta not under the actions", r["meta"], r["actions"]))""",
  """if r["meta"] and r["meta"]["top"] < r["h1"]["bottom"] - 1:
                        failures.append((label, "meta not under the title", r["meta"], r["h1"]))""", 1),
])
fix("test_wp28_geometry.py", [("wrap.querySelector('.row-actions .btn')", "wrap.querySelector('.row-actions .ui-btn')", 1)])
fix("test_host_wide_geometry_browser.py", [('header = page.locator(".page-header").first.bounding_box()', 'header = page.locator(".ui-ph").first.bounding_box()', 1)])
pathlib.Path("tests/test_design_properties.py").write_text('''"""0140: properties pages render on host_page; the property page keeps its local tabs."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import empty_host, host_with_property  # noqa: F401


def test_properties_list_header_tabs_and_icon(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-tabs" data-sub-tabs' in page and 'data-icon="house"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1


def test_property_page_keeps_local_tabs_without_section_tabs(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    match = re.search(r'data-href="(/apartments/\\d+)"', page)
    assert match
    detail = host_with_property.get(match.group(1) + "?lang=en").text
    assert '<nav class="ui-tabs property-tabs"' in detail and "data-sub-tabs" not in detail
    assert detail.count('data-property-tab="') == 3 and 'class="ui-ph-back"' in detail
    assert 'data-body-kind="detail"' in detail and "nav_icon" not in detail


def test_add_property_and_businesses_are_v2_pages(empty_host):
    assert 'data-body-kind="form"' in empty_host.get("/apartments/new?lang=en").text
    businesses = empty_host.get("/entities?lang=en").text
    assert 'data-body-kind="list"' in businesses and 'class="ui-tabs" data-sub-tabs' in businesses
''', encoding="utf-8")
print("tests ok")
EOF
```

   Expected: `tests ok`.

5. Unit tests. From `App/`: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_properties.py tests/test_properties_table_chips.py tests/test_host_properties_navigation.py tests/test_property_readiness.py tests/test_property_form_nav.py tests/test_property_form_save.py tests/test_property_hub.py tests/test_property_address_required.py tests/test_property_operator_defaults.py tests/test_calendar_sync_ui.py tests/test_wp28_ui_sweep.py tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py tests/test_design_lint.py -q --tb=line 2>&1 | tail -15`. Expected: all pass except `test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages`, which already fails before this brief (see step 6).

6. Browser tests (the orchestrator takes the screenshots; attach none). From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_host_unsaved_changes_browser.py tests/test_host_property_controls_browser.py tests/test_properties_inline_controls_browser.py tests/test_property_create_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_list_cards_browser.py tests/test_host_wide_geometry_browser.py tests/test_wp28_geometry.py tests/test_onboarding_followup_browser.py tests/test_lock_navigation_browser.py tests/test_fee_setup_compatibility.py tests/test_host_copy_corrections.py tests/test_host_controls_browser.py tests/test_host_ux_acceptance.py tests/test_shell_lane_browser.py -q --tb=line 2>&1 | grep -E "FAILED|passed|failed|skipped" | tail -20`. It takes about 12 minutes; run it in the background and wait for it. Expected: 0 skipped, and no failure outside this list that already fail before this brief with the same message:
   - `test_property_navigation_browser.py::test_three_views_four_groups_one_editor_and_unique_ids` (`'<details' not in ...`, line 196)
   - `test_property_navigation_browser.py::test_create_offers_the_calendar_first_and_works_without_js` (Locator.click timeout)
   - `test_property_create_browser.py::test_create_page_fits_and_follow_ups_move_below_when_narrow` (`assert 0 == 1`, line 437)
   - `test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages` (360 px, line 320)
   - `test_host_property_controls_browser.py::test_property_and_operator_controls_render_and_work_in_browser` (line 203)
   - `test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls` (`(360, [])`, line 206)
   - `test_host_list_page_layout_browser.py::test_list_pages_share_order_edges_and_rhythm` (only the `rhythm` entries)
   - `test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back` and `::test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus` (Locator timeouts)
   - `test_host_wide_geometry_browser.py::test_host_wide_lanes_align`, only while it stops on an invoices route (`invoices/...` or `invoice-new-picker/...: selected result lane ... is missing`, left by 0141). If it names an `operator-*`, `invoice-settings`, `property-*` or `guest-links` route, that is this brief: stop and report.

   A failure outside that list, or one of these with a different message: stop and report it (section 8). Do not change a test limit.

7. Static version (last change before the commit). host2.css changed, so bump its key in every template that loads it, then rebuild the manifest. From `App/`, run:

```
.venv/bin/python - <<'EOF'
import pathlib, re
REF = re.compile(r'/static/host2\.css\?v=[^"&]+')
changed = []
for p in sorted(pathlib.Path("app/templates").rglob("*.html")):
    if "archive" in p.parts: continue
    s = p.read_text(encoding="utf-8"); n = REF.sub("/static/host2.css?v=20261019-0140", s)
    if n != s: p.write_text(n, encoding="utf-8"); changed.append(str(p))
assert changed, "no template references host2.css"
print(changed)
EOF
```

   Expected: a list holding `app/templates/base.html`. Then `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -5`. Expected: `passed`.

8. Commit, from the repo root: `git add App/app/templates App/app/static/host2.css docs/design/catalog.json App/tests && git status --short | tail -30 && git commit -m "0140: properties, property page and businesses on host_page"`. `git status` must list only the files in section 3.

## 5. Do not touch

`app.js` (`initPropertyViews`, `syncAutomationHours`), routes, `_entity_*_fields.html`, `_components.html`, settings-group ids and `data-settings-group`, the onboarding and setup-wizard templates; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: `design lint: OK`.
- `python3 scripts/context_lint.py` (repo root) expected: OK.
- The step 5, 6 and 7 commands, with the results named there.

## 7. Acceptance

- [ ] `/apartments`: v2 header with one primary "Add a property" (Lucide `house`), Properties tabs, count in the toolbar; `/apartments/new` is a `form` page; `/apartments/{id}` is a `detail` page with a back link and ink-underline local tabs, no `data-sub-tabs`; `/entities` is a `list` page with the Properties tabs.
- [ ] Lint passes with the three pages enforced; `grep -n "nav_icon" App/app/templates/apartments.html App/app/templates/apartment_form.html App/app/templates/entities.html App/app/templates/_property_*.html` prints nothing.
- [ ] Step 6: 0 skipped, no new failure. No screenshots (the orchestrator takes them).

## 8. Stop and ask

Stop and write the report if: a script stops with an AssertionError; a test fails that is not in the step 6 list; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0140-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`apartment_form.html` (view switching under host_page), `_property_editor.html` (settings forms, buttons only), host2.css `.property-tabs` override against host.css pills, `test_host_list_page_layout_browser.py` (the meta check now reads "under the title": the v2 header puts the meta under the h1, beside the actions).

## Owner steps

None.
