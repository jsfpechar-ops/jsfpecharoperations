# 0134: Stays list on the v2 template (list kind)

Status: todo
Depends on: 0133 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0134 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md`.

## 1. Objective

Move `reservations.html` onto `host_page.html` as a list page: v2 header (title, one primary Add stay, Send-all as secondary), section tabs, v2 toolbar with chips and the Filters button, the stays table in v2 classes (stacked under 1024 px), v2 pagination and v2 form controls in the add-stay panel and the filter form. Routes, filters, saved views, CSV export, row menus and every `data-*` hook stay as they are.

## 2. Context

Rules: MASTER 5 (list kind), 5.3 (toolbar), 7.4 (table), 7.13 (pagination), 4 (one primary), `docs/design/pages/stays.md`. `app.js` keys on `[data-filter-panel]`, `[data-filter-toggle]`, `[data-filter-summary]`, `[data-filter-cancel]`, `[data-toggle-panel]`, `.action-panel`, `[data-save-view]`, `[data-saved-views]` and `.clickable-row`, never on `.btn`, `.pill`, `.chip` or `.field`, so class renames are safe. The page's one literal `ui-btn-primary` is the filter Apply; the header primary comes from the `ui_button` macro.

Anchor A, `App/app/templates/reservations.html`, lines 1 to 17 (verify with `sed -n 1,17p`):

```
{% extends "base.html" %}
{% set nav = 'reservations' %}
{% block title %}{{ t('stays.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import list_page_header, list_toolbar, empty_state, progress_pill, row_menu_begin, row_menu_end, row_reporting_actions, bulk_send_ready, csv_actions_menu, copy_inline, property_identity, guest_count, deadline_badge, source_badge with context %}
{% set csv_export_params = 'apartment=' ~ (apartment_id or '') %}
{% set view_query = 'range=' ~ date_range ~ '&status=' ~ status ~ '&apartment=' ~ (apartment_id or '') ~ '&from=' ~ (date_from or '') ~ '&to=' ~ (date_to or '') %}
{% if apartments %}
{% set header_actions %}
  {{ bulk_send_ready(ready_send_count, return_to) }}
  <button class="btn" type="button" data-toggle-panel="add-stay-panel">{{ t('stays.add_stay') }}</button>
{% endset %}
{% else %}
{# Nothing to send and nothing to add to yet, so the header stays out of the way. #}
{% set header_actions = '' %}
{% endif %}
{{ list_page_header(t('stays.title'), actions=header_actions) }}
```

Anchor B (chips, lines 74 to 79):

```
{% set stay_chips %}
    {% for value, label_key in [('upcoming', 'stays.chip.upcoming'), ('past', 'stays.chip.past'), ('all', 'stays.chip.all'), ('archive', 'stays.chip.archive')] %}
      <a class="chip {{ 'on' if date_range == value or (value == 'archive' and show_archive) }}"
         href="/reservations?range={{ value }}&status={{ status }}&apartment={{ apartment_id or '' }}">{{ t(label_key) }}</a>
    {% endfor %}
{% endset %}
```

Anchor C (toolbar call, line 93):

```
{{ list_toolbar(stay_summary, chips=stay_chips, panel_id='stays-filter-panel', actions=stay_list_actions) }}
```

Anchor D (pagination, lines 221 to 227):

```
  <nav class="pagination" aria-label="{{ t('stays.title') }}">
    {% if previous_page_url %}<a class="btn" href="{{ previous_page_url }}">{{ t('stays.pagination.prev') }}</a>
    {% else %}<span class="btn disabled" aria-disabled="true">{{ t('stays.pagination.prev') }}</span>{% endif %}
    <span class="pagination-label">{{ t('stays.pagination.label', page=page, pages=page_count) }}</span>
    {% if next_page_url %}<a class="btn" href="{{ next_page_url }}">{{ t('stays.pagination.next') }}</a>
    {% else %}<span class="btn disabled" aria-disabled="true">{{ t('stays.pagination.next') }}</span>{% endif %}
  </nav>
```

Anchor E, `App/app/templates/reservations.html` line 60:

```
      <div class="actions"><button class="btn primary" type="submit">{{ t('stays.add_panel.create') }}</button></div>
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservations.html` | edit | head, toolbar, table classes, pagination, controls |
| `App/app/static/host2.css` | edit | append: stacked table under 1024 px, legacy inputs inside `.ui-field` |
| `docs/design/catalog.json` | edit | `ui-table-stack` class; enforce the template; its legacy list |
| `App/tests/test_stays_empty_workspace.py` | edit | two Apply-button assertions |
| `App/tests/test_host_filter_panels_browser.py` | edit | selected chip selector |
| `App/tests/test_design_stays.py` | create | slots and hooks |

No other file may change.

## 4. Steps

1. Replace Anchor A (lines 1 to 17) with:

```
{% extends "host_page.html" %}
{% set nav = 'reservations' %}
{% set body_kind = 'list' %}
{% from "_components.html" import empty_state, progress_pill, row_menu_begin, row_menu_end, row_reporting_actions, bulk_send_ready, csv_actions_menu, copy_inline, property_identity, guest_count, deadline_badge, source_badge, onboarding_banner with context %}
{% from "_ui.html" import ui_button, ui_pagination with context %}
{% from "_ui_layout.html" import ui_toolbar, ui_section_tabs with context %}
{% set csv_export_params = 'apartment=' ~ (apartment_id or '') %}
{% set view_query = 'range=' ~ date_range ~ '&status=' ~ status ~ '&apartment=' ~ (apartment_id or '') ~ '&from=' ~ (date_from or '') ~ '&to=' ~ (date_to or '') %}
{% block title %}{{ t('stays.title') }}{% endblock %}
{% block primary_action %}{% if apartments %}{{ ui_button(t('stays.add_stay'), 'primary', attrs='data-toggle-panel="add-stay-panel"') }}{% endif %}{% endblock %}
{% block secondary_actions %}{% if apartments %}{{ bulk_send_ready(ready_send_count, return_to) }}{% endif %}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
{{ onboarding_banner(onboarding) }}
```

   The file's last line `{% endblock %}` now closes `body`. Command: `cd App && .venv/bin/python -m pytest tests/test_stays_empty_workspace.py -q --tb=short 2>&1 | tail -5`. Expected: the two Apply assertions fail, nothing else.

2. Replace Anchor B with:

```
{% set stay_chip_items = [] %}
{% for value, label_key in [('upcoming', 'stays.chip.upcoming'), ('past', 'stays.chip.past'), ('all', 'stays.chip.all'), ('archive', 'stays.chip.archive')] %}
  {% set _ = stay_chip_items.append(('/reservations?range=' ~ value ~ '&status=' ~ status ~ '&apartment=' ~ (apartment_id or ''), t(label_key), date_range == value or (value == 'archive' and show_archive))) %}
{% endfor %}
```

   Replace Anchor C with:

```
{{ ui_toolbar(chips=stay_chip_items, filters_id='stays-filter-panel', actions=stay_list_actions) }}
<p class="ui-sub" data-filter-summary>{{ stay_summary }}</p>
```

   Replace Anchor D with:

```
  {{ ui_pagination(page, page_count, prev_url=previous_page_url or '', next_url=next_page_url or '', label=t('stays.title'), more_label=t('stays.pagination.next'), prev_label=t('stays.pagination.prev'), next_label=t('stays.pagination.next')) }}
```

   Replace Anchor E with:

```
      <div class="ui-form-actions">{{ ui_button(t('stays.add_panel.create'), 'primary', type='submit') }}</div>
```

3. Mechanical class replacements. Run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/reservations.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('<div class="section-heading" style="margin-top:0">', '<div class="ui-section-h">', 1),
 ('class="btn small ghost"', 'class="ui-btn ui-btn-quiet ui-btn-compact"', 1),
 ('class="btn primary filter-apply"', 'class="ui-btn ui-btn-primary filter-apply"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 3),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 2),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="small muted"', 'class="ui-sub"', 5),
 ('class="field"', 'class="ui-field"', 8),
 ('class="filters panel host-filter-panel"', 'class="filters ui-section host-filter-panel"', 1),
 ('<div class="panel">', '<div class="ui-section">', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'style="' not in s and 'class="btn' not in s and 'class="pill' not in s
p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. If a count differs, stop and report the line.

4. Append to `App/app/static/host2.css`:

```
/* 0134: legacy inputs inside a v2 field, until every form uses ui_field */
.host-workspace .ui-field > input:not([type="checkbox"]):not([type="radio"]), .host-workspace .ui-field > select, .host-workspace .ui-field > textarea { width: 100%; min-height: var(--control-h); padding: 0 var(--space-3); border: 1px solid var(--line-strong); border-radius: var(--radius-2); background: var(--surface); color: var(--ink); font: inherit; font-size: var(--size-16); }
.host-workspace .ui-field > textarea { min-height: calc(var(--control-h) * 2); padding: var(--space-2) var(--space-3); }
.host-workspace .ui-field > label { display: block; margin: 0 0 var(--space-1); font-size: var(--size-14); color: var(--ink-2); }
/* 0134: stacked table under the desktop breakpoint; the header row is read by assistive tech only */
@media (max-width: 1023px) {
  .host-workspace .ui-table-stack thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  .host-workspace .ui-table-stack tr { display: block; padding: var(--row-py) 0; border-bottom: 1px solid var(--line); }
  .host-workspace .ui-table-stack td { display: flex; gap: var(--space-3); padding: var(--space-1) 0; border: 0; }
  .host-workspace .ui-table-stack td[data-label]::before { content: attr(data-label); flex: 0 0 38%; color: var(--ink-3); font-size: var(--size-14); }
  .host-workspace .ui-table-stack td[data-label=""]::before, .host-workspace .ui-table-stack td:not([data-label])::before { content: none; }
}
```

   In `docs/design/catalog.json` add `"ui-table-stack"` after `"ui-table"` in `classes`, add `"App/app/templates/reservations.html"` to `enforced_templates`, then run `python3 scripts/design_lint.py 2>&1 | grep reservations.html | sed 's/.*catalog: //' | sort -u | tr '\n' ' '`. Put every token it prints into `legacy["App/app/templates/reservations.html"]` (expected: `action-panel filters host-filter-panel filter-fields filter-panel-actions filter-apply grid two opt saved-views stays-view stay-col-dates stay-col-guests stay-col-property stay-col-reporting stay-col-source stay-col-stay stay-col-actions stay-date-link stay-identity-link stay-report-deadline row-primary-link row-actions row-action-pair row-menu-form nowrap num empty-state-extra` plus any you see). Command: `python3 scripts/design_lint.py`. Expected: OK.

5. Tests. In `App/tests/test_stays_empty_workspace.py` replace both occurrences of
   `'class="btn primary filter-apply" type="submit" name="range" value="custom"'` with
   `'class="ui-btn ui-btn-primary filter-apply" type="submit" name="range" value="custom"'`.
   In `App/tests/test_host_filter_panels_browser.py` replace `[data-list-toolbar] .chip.on` with `[data-list-toolbar] .ui-chip[aria-current="true"]`.
   Create `App/tests/test_design_stays.py`:

```python
"""0134: the stays list renders on host_page with v2 controls and its hooks."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property, empty_host  # noqa: F401


def test_stays_list_has_the_v2_header_toolbar_and_table(host_with_property):
    page = host_with_property.get("/reservations?range=all&lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-toolbar" data-filter-toolbar data-list-toolbar' in page
    assert 'data-filter-toggle aria-expanded="true" aria-controls="stays-filter-panel" hidden' in page
    assert 'class="ui-table ui-table-stack"' in page or "data-empty-state" in page
    assert 'id="add-stay-panel" class="action-panel hidden"' in page
    assert 'data-toggle-panel="add-stay-panel"' in page
    assert "list-page-header" not in page and "filter-toolbar" not in page


def test_an_empty_workspace_has_no_header_actions(empty_host):
    page = empty_host.get("/reservations?lang=en").text
    assert page.count("<h1") == 1
    assert 'class="ui-ph-acts"' not in page
    assert page.count("data-empty-state") == 1


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/reservations.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text
    assert text.count('ui-btn-primary') == 1
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_stays.py tests/test_stays_empty_workspace.py tests/test_archive_stays_on_page.py tests/test_manual_stay_uid.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

6. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_filter_panels_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_list_cards_browser.py tests/test_host_geometry.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach `/tmp/ubyhost-shots` shots of `/reservations?range=all` at 390 and 1280 (take them with a 6-line Playwright script if no test writes them; name `stays-390.png`, `stays-1280.png`).

7. Commit: `git add App/app/templates/reservations.html App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0134 step 7: stays list on host_page (list kind)"`.

## 5. Do not touch

`_components.html`, `_date_range.html`, `app.js`, `routes/reservations.py`, the filter and saved-view behaviour, the archive and demo flows; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 5 and step 6 commands, 0 skipped.

## 7. Acceptance

- [ ] One h1, Add stay the only primary, Send all ready secondary, tabs under the title, toolbar with four chips and the Filters button, the table stacked at 390 px.
- [ ] 390 px and 1280 px screenshots attached.
- [ ] Lint passes with `reservations.html` enforced; its legacy list is in the catalog.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count in step 3 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0134-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/reservations.html` (filter panel hooks, send-all button, row grammar).

## Owner steps

None.
