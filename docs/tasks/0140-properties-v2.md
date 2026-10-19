# 0140: Properties list, property page, add property and businesses on the v2 template

Status: todo
Depends on: 0139 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0140 step k`. Never push, never open a PR. Page file: `docs/design/pages/properties.md`.

## 1. Objective

Move `apartments.html` (list), `apartment_form.html` (property page: overview, bookings, settings views; and the add-property page) and `entities.html` (businesses) onto `host_page.html`; swap the hand-drawn `nav_icon` SVGs for the Lucide macro; convert buttons, badges and tables in the three property partials (`_property_overview.html`, `_property_calendars.html`, `_property_editor.html`, `_property_create.html`) without touching their structure, ids or `data-*` hooks (the property views, unsaved-changes guard and settings groups are driven by them). The partials are not enforced by the lint yet; the three pages are.

## 2. Context

Rules: MASTER 5, 5.2 (tabs), 7.4, 7.5, 4, `docs/design/pages/properties.md`. The property page keeps its own local tabs (`.property-tabs a[data-property-tab]`, read by five browser tests) and must not carry `data-sub-tabs` (`test_host_list_page_layout_browser.py` line 190). Icon names available in `_icons.html` (0127): `house`, `calendar-days`, `receipt`, `key-round`, `external-link`, `coins`, `send`.

Anchor A, `App/app/templates/apartments.html` lines 1 to 15 after 0137 (the sync button is gone), from `{% extends "base.html" %}` to the `) }}` closing `list_page_header(`; line 6 to 8 read:

```
{% set header_actions %}
  {% if rows %}<a class="btn primary sync-btn" href="/apartments/new"><span class="sync-btn-icon" aria-hidden="true">{{ nav_icon('property') }}</span><span>{{ t('apartments.add') }}</span></a>{% endif %}
{% endset %}
```

Anchor B, same file: `{{ list_toolbar(tp('properties.list.count', rows | length)) }}`.

Anchor C, `App/app/templates/apartment_form.html`: line 1 `{% extends "base.html" %}`; lines 7 to 8 `{% block content %}` and the `{% from "_components.html" import page_header, breadcrumb, copy_button, copy_inline, nav_icon, source_badge, field_label, help_tip, sync_calendars_button with context %}`; lines 13 to 14 (`{{ breadcrumb([...]) }}` and `{{ page_header(t('property_create.title'), t('property_create.lede')) }}`); lines 17 to 22 (`{{ page_header(` ... `) }}` with `apartment.internal_name`); line 31 `<nav class="property-tabs" aria-label="{{ t('property_nav.tabs_aria') }}">`; line 33 `  <a href="{{ base_url }}?view={{ key }}" data-property-tab="{{ key }}"{% if key == property_view %} aria-current="page"{% endif %}>{{ label }}</a>`.

Anchor D, `App/app/templates/entities.html` lines 1 to 18: extends, nav, title, blank, `{% block content %}`, three imports, the `<style>` block (lines 9 to 13), the breadcrumb (14 to 17) and `{{ page_header(t('entities.title'), t('entities.lede'), next_path or '/apartments', t('common.back') if next_path else t('entities.back')) }}` (18).

Test anchors: `App/tests/test_properties_table_chips.py` lines 156, 171 to 173, 181 to 182, 185 (`_nav_icon_svg`), 207, 214; `App/tests/test_host_properties_navigation.py` lines 112, 123, 128, 261; `App/tests/test_host_property_controls_browser.py` line 222; `App/tests/test_properties_inline_controls_browser.py` line 210; `App/tests/test_calendar_sync_ui.py` line 114; `App/tests/test_property_navigation_browser.py` line 281; `App/tests/test_wp28_ui_sweep.py` line 120; `App/tests/test_property_readiness.py` line 168; `App/tests/test_property_create_browser.py` line 97.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartments.html` | edit | head, toolbar, classes |
| `App/app/templates/apartment_form.html` | edit | head, blocks, local tabs classes |
| `App/app/templates/entities.html` | edit | head, style block out, classes |
| `App/app/templates/_property_overview.html` | edit | icons, buttons, badge |
| `App/app/templates/_property_calendars.html` | edit | buttons, badges, table, one style |
| `App/app/templates/_property_editor.html` | edit | buttons, two margin styles |
| `App/app/templates/_property_create.html` | edit | icons, buttons |
| `App/app/static/host2.css` | edit | append the three entities rules |
| `docs/design/catalog.json` | edit | enforce the three pages; legacy lists |
| the nine test files above | edit | exact diffs in step 5 |
| `App/tests/test_design_properties.py` | create | slots, tabs, icon |

No other file may change.

## 4. Steps

1. `apartments.html`: replace Anchor A with

```
{% extends "host_page.html" %}
{% set nav = 'apartments' %}
{% set body_kind = 'list' %}
{% from "_components.html" import list_section_heading, empty_state, row_menu_begin, row_menu_end, property_identity, help_tip, copy_icon with context %}
{% from "_ui.html" import ui_button with context %}
{% from "_ui_layout.html" import ui_toolbar, ui_section_tabs with context %}
{% block title %}{{ t('apartments.title') }}{% endblock %}
{% block meta %}{% if last_sync %}{{ t('dashboard.last_synced', when=last_sync | datetime_local) }}{% endif %}{% endblock %}
{% block primary_action %}{% if rows %}{{ ui_button(t('apartments.add'), 'primary', href='/apartments/new', icon_name='house') }}{% endif %}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
```

   and Anchor B with `{{ ui_toolbar(actions='<span class="ui-sub">' ~ tp('properties.list.count', rows | length) ~ '</span>') }}`.

   `apartment_form.html`: line 1 -> `{% extends "host_page.html" %}`; after line 3 (`{% set editing = apartment is not none %}`) insert `{% set body_kind = 'detail' if editing else 'form' %}`; replace the `{% block content %}` line and the import line with

```
{% block page_title %}{{ apartment.internal_name if editing else t('property_create.title') }}{% endblock %}
{% block meta %}{{ (apartment.city_en or apartment.addr_obec or '') if editing else t('property_create.lede') }}{% endblock %}
{% block back_url %}/apartments{% endblock %}
{% block back_label %}{{ t('apartment.form.back') if editing else t('nav.properties') }}{% endblock %}
{% block body %}
{% from "_components.html" import copy_button, copy_inline, source_badge, field_label, help_tip, sync_calendars_button with context %}
{% from "_icons.html" import icon with context %}
```

   delete lines 13 to 14 (breadcrumb and page_header of the create branch) and lines 17 to 22 (the editing `page_header(` call); replace line 31 with `<nav class="ui-tabs property-tabs" aria-label="{{ t('property_nav.tabs_aria') }}">` and line 33 with `  <a class="ui-tab" href="{{ base_url }}?view={{ key }}" data-property-tab="{{ key }}"{% if key == property_view %} aria-current="page"{% endif %}>{{ label }}</a>`.

   `entities.html`: replace Anchor D (lines 1 to 18) with

```
{% extends "host_page.html" %}
{% set nav = 'entities' %}
{% set body_kind = 'settings' %}
{% from "_components.html" import onboarding_banner, row_menu_begin, row_menu_end, help_tip with context %}
{% from "_entity_business_fields.html" import business_form_body, ico_field, register_messages, register_lookup_saved with context %}
{% from "_entity_invoice_fields.html" import invoice_fields with context %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('entities.title') }}{% endblock %}
{% block meta %}{{ t('entities.lede') }}{% endblock %}
{% block back_url %}{{ next_path or '/apartments' }}{% endblock %}
{% block back_label %}{{ t('common.back') if next_path else t('entities.back') }}{% endblock %}
{% block body %}
```

   Append to `App/app/static/host2.css` (the three rules from the deleted style block, in tokens):

```
/* 0140: businesses page, moved out of entities.html */
.host-workspace .entities-page tbody tr .row-actions > * { opacity: 1; }
.host-workspace .entities-page .row-menu-item[aria-disabled="true"] { color: var(--ink-3); cursor: not-allowed; }
.host-workspace .entities-page .row-menu-explanation { max-width: 240px; margin: 0 var(--space-2) var(--space-2); color: var(--ink-3); font-size: var(--size-12); line-height: 1.45; }
```

   Command: `cd App && .venv/bin/python -c "
from app.templating import templates
for n in ('apartments.html','apartment_form.html','entities.html'): templates.env.get_template(n)
print('compiled')"`. Expected: `compiled`.

2. Mechanical replacements, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
def patch(name, pairs, forbid=()):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:60], s.count(old)); s = s.replace(old, new)
    for f in forbid: assert f not in s, (name, f)
    p.write_text(s, encoding="utf-8")
B = {"grey": ("neutral", "grey"), "green": ("done", "green"), "teal": ("neutral", "teal"), "amber": ("action", "amber"), "red": ("action", "red"), "blue": ("action", "blue")}
def pill(t): return f'class="ui-badge ui-badge-{B[t][0]}" data-tone="{B[t][1]}"'
ICON = {"property": "house", "calendar": "calendar-days", "report": "send", "entity": "receipt", "link": "external-link", "lock": "key-round", "coins": "coins"}
def icons(s, n):
    found = re.findall(r"nav_icon\('([a-z]+)'\)", s); assert len(found) == n, (n, found)
    return re.sub(r"nav_icon\('([a-z]+)'\)", lambda m: "icon('%s', 20)" % ICON[m.group(1)], s)
patch("apartments.html", [
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1), ('class="pill amber"', pill("amber"), 2),
 ('class="panel tight scroll-x list-cards lc-properties property-summary-panel"', 'class="list-cards lc-properties property-summary-panel"', 1),
 ('class="panel tight scroll-x list-cards lc-properties"', 'class="list-cards lc-properties"', 1),
 ('class="table-cards properties-table"', 'class="ui-table ui-table-stack properties-table"', 1),
 ('class="table-cards property-summary-table"', 'class="ui-table ui-table-stack property-summary-table"', 1),
 ('class="num"', 'class="ui-num"', 2),
], forbid=('style="', 'class="btn', 'class="pill', 'nav_icon'))
patch("entities.html", [
 ('<div class="section-heading" style="margin-top:0">', '<div class="ui-section-h">', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('class="btn primary"', 'class="{{ cta }}"', 3),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="pill amber"', pill("amber"), 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 2),
 ('class="section-heading"', 'class="ui-section-h"', 1),
 ('class="small muted"', 'class="ui-sub"', 2),
 ('class="actions"', 'class="ui-form-actions"', 3),
 ('class="muted"', 'class="ui-sub"', 1), ('class="small"', 'class="ui-sub"', 1),
 ('class="num"', 'class="ui-num"', 1), ('class="mono"', 'class="ui-mono"', 2),
 ('class="panel entity-form"', 'class="ui-section entity-form"', 1),
], forbid=('style="', 'class="btn', 'class="pill', '<style'))
# partials: controls only; structure, ids and panels stay
p = pathlib.Path("app/templates/_property_overview.html"); s = p.read_text(encoding="utf-8"); s = icons(s, 8)
for old, new, n in [('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="pill amber"', pill("amber"), 1), ('class="actions"', 'class="ui-form-actions"', 1)]:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
if 'import icon' not in s: s = '{% from "_icons.html" import icon with context %}\n' + s
p.write_text(s, encoding="utf-8")
p = pathlib.Path("app/templates/_property_create.html"); s = p.read_text(encoding="utf-8"); s = icons(s, 7)
for old, new, n in [('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1), ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1), ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1), ('class="small muted"', 'class="ui-sub"', 1), (' style="max-width:420px"', '', 1)]:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
s = s.replace('{%- from "_components.html" import nav_icon, help_tip with context -%}', '{%- from "_components.html" import help_tip with context -%}\n{%- from "_icons.html" import icon with context -%}')
assert "nav_icon" not in s; p.write_text(s, encoding="utf-8")
patch("_property_calendars.html", [
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1), ('class="pill amber"', pill("amber"), 1), ('class="pill red"', pill("red"), 1),
 ('class="table-cards feed-table"', 'class="ui-table ui-table-stack feed-table"', 1),
 ('class="small muted"', 'class="ui-sub"', 1), ('class="actions"', 'class="ui-form-actions"', 2), ('class="field"', 'class="ui-field"', 3),
], forbid=('style="', 'class="btn', 'class="pill'))
patch("_property_editor.html", [
 ('<p class="small" style="margin:10px 0 0" role="status">', '<p class="ui-sub" role="status">', 1),
 ('<p class="small muted" style="margin:4px 0 0">', '<p class="ui-sub">', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 5),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 6),
 ('class="small muted"', 'class="ui-sub"', 7), ('class="actions"', 'class="ui-form-actions"', 1),
 ('class="field"', 'class="ui-field"', 14), ('class="small"', 'class="ui-sub"', 5),
], forbid=('class="btn', 'class="pill'))
print("ok")
EOF
```

   Expected: `ok`. (`_property_editor.html` keeps its three `max-width` styles until the cleanup brief; 0137 already removed one `class="btn"` there, hence 6.) Command: `cd App && .venv/bin/python -c "
from app.templating import templates
for n in ('apartments.html','apartment_form.html','entities.html'): templates.env.get_template(n)
print('compiled')"`. Expected: `compiled`.

3. Catalog: add the three pages to `enforced_templates`; run the lint, collect each page's T3 tokens as in earlier briefs and put them in `legacy` (apartments: `list-cards lc-properties property-summaries property-summaries-title property-summaries-head property-summary-panel property-summary-table properties-table list-section-heading heading-with-tip property-inline-* property-timing-* sync-btn sync-btn-icon btn-icon nowrap row-actions row-menu-form row-primary-link`; apartment_form: `property-tabs property-views property-view`; entities: `entities-page entity-* row-menu-explanation row-selected list-cards lc-entities col-name danger nowrap row-actions row-menu-form empty`). Command: `python3 scripts/design_lint.py`. Expected: OK.

4. Append the per-property icon hooks to `hooks` in the catalog if the lint names them: `property-create`, `property-create-*`. Command: `python3 scripts/design_lint.py`. Expected: OK.

5. Tests, exact edits:
   - `test_properties_table_chips.py`: 156 `r'<span class="pill (amber|green|red)">'` -> `r'<span class="ui-badge ui-badge-(?:action|done)" data-tone="(amber|green|red)">'`; 171 `assert 'class="btn primary sync-btn"' in cta` -> `assert 'class="ui-btn ui-btn-primary"' in cta`; 172 `assert 'class="sync-btn-icon" aria-hidden="true"' in cta` -> `assert 'data-icon="house"' in cta`; 173 `assert 'class="nav-icon"' in cta` -> `assert 'class="ui-icon"' in cta`; 181 `assert _nav_icon_svg("property") in cta` -> `assert 'data-icon="house"' in cta`; 182 `assert _nav_icon_svg("calendar") not in cta` -> `assert 'data-icon="calendar-days"' not in cta`; delete the `_nav_icon_svg` helper (lines 185 to its end, the function that renders `nav_icon` through the components template); 207 `panel.group(1).count('class="btn primary')` -> `panel.group(1).count('class="ui-btn ui-btn-primary')` (if 0132 already did this, keep it); 214 `assert 'class="btn primary sync-btn" href="/apartments/new"' not in empty_host.get("/apartments?lang=en").text` -> `assert 'data-icon="house"' not in empty_host.get("/apartments?lang=en").text`.
   - `test_host_properties_navigation.py`: 112 `'class="table-cards properties-table"'` -> `'class="ui-table ui-table-stack properties-table"'`; 123 `r'<span class="pill (amber|green)">'` -> `r'<span class="ui-badge ui-badge-(?:action|done)" data-tone="(amber|green)">'`; 128 `'<a class="sub-tab" href="/entities">Business &amp; legal details</a>'` -> `'<a class="ui-tab" href="/entities">Business &amp; legal details</a>'`; 261 `'.sub-tabs a, ` -> `'.ui-tabs a, `.
   - `test_host_property_controls_browser.py` 222: `.sub-tabs a[aria-current="page"]` -> `.ui-tabs a[aria-current="page"]`.
   - `test_properties_inline_controls_browser.py` 210: `'class="panel tight scroll-x list-cards lc-properties property-summary-panel"'` -> `'class="list-cards lc-properties property-summary-panel"'`.
   - `test_calendar_sync_ui.py` 114 and `test_property_navigation_browser.py` 281: `'class="pill red"'` -> `'data-tone="red"'`.
   - `test_wp28_ui_sweep.py` 120: `'class="table-cards feed-table"'` -> `'class="ui-table ui-table-stack feed-table"'`.
   - `test_property_readiness.py` 168: `'<div class="banner warning">'` -> `'<div class="ui-banner ui-banner-attention">'`.
   - `test_property_create_browser.py` 97: `'<header class="page-header"'` -> `'<header class="ui-ph"'`.

   Create `App/tests/test_design_properties.py`:

```python
"""0140: properties pages render on host_page; the property page keeps its local tabs."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import host_with_property, empty_host  # noqa: F401


def test_properties_list_header_tabs_and_icon(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-tabs" data-sub-tabs' in page and 'data-icon="house"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1


def test_property_page_keeps_local_tabs_without_section_tabs(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    match = re.search(r'data-href="(/apartments/\d+)"', page)
    assert match
    detail = host_with_property.get(match.group(1) + "?lang=en").text
    assert '<nav class="ui-tabs property-tabs"' in detail and "data-sub-tabs" not in detail
    assert detail.count('data-property-tab="') == 3 and 'class="ui-ph-back"' in detail


def test_add_property_and_businesses_are_v2_pages(empty_host):
    assert 'data-body-kind="form"' in empty_host.get("/apartments/new?lang=en").text
    assert 'data-body-kind="settings"' in empty_host.get("/entities?lang=en").text
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_properties.py tests/test_properties_table_chips.py tests/test_host_properties_navigation.py tests/test_property_*.py tests/test_calendar_sync_ui.py tests/test_wp28_ui_sweep.py tests/test_entit*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

6. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_host_unsaved_changes_browser.py tests/test_host_property_controls_browser.py tests/test_properties_inline_controls_browser.py tests/test_property_create_browser.py tests/test_host_list_page_layout_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped (the five 360 px failures in `test_host_property_controls_browser.py` are pre-existing; report them if they persist, fix only if the layout work removed the cause). Attach `/apartments`, one property page and `/entities` at 390 and 1280.

7. Commit: `git add App/app/templates App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0140 step 7: properties, property page and businesses on host_page"`.

## 5. Do not touch

`app.js` (`initPropertyViews`), routes, `_entity_*_fields.html`, settings-group ids and `data-settings-group`, the onboarding checklist partials; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 5 and step 6 commands, 0 skipped except the pre-existing five.

## 7. Acceptance

- [ ] Properties list with tabs and one primary (Lucide house icon); property page with back link and ink-underline local tabs; add property as a form page; businesses as a settings page.
- [ ] Screenshots attached.
- [ ] Lint passes with the three pages enforced; no `nav_icon` call left outside `_components.html` and `base.html`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count in step 2 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0140-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/apartment_form.html` (view switching), `App/app/templates/_property_editor.html` (settings forms).

## Owner steps

None.
