# 0133: Dashboard on the v2 template (detail kind)

Status: todo
Depends on: 0132 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0133 step k`. Never push, never open a PR. Page file: `docs/design/pages/dashboard.md`.

## 1. Objective

Move `dashboard.html` onto `host_page.html` as a detail page: v2 header (title, date meta, one primary Add stay), stat row, attention banner, the existing calendar, and the Needs-you list as a table on desktop and cards on phone. Behaviour, routes, the five-row cap, the 30-day window and the calendar refresh stay exactly as they are.

## 2. Context

Rules: MASTER 5 (detail kind), 7.3, 7.14, 4 (one primary), `docs/design/pages/dashboard.md`. The dashboard refresh in `dashboard-calendar.js` swaps `[data-dashboard-refresh="stats"]` and `[data-dashboard-refresh="work"]` by attribute, so the new markup keeps both attributes and the `dashboard-row`, `dashboard-row-copy`, `dashboard-row-task`, `data-stay-id` hooks that `test_dashboard_calendar_browser.py` and `test_host_quiet_dashboard_browser.py` read.

Anchor A, `App/app/templates/dashboard.html`, lines 1 to 6:

```
{% extends "base.html" %}
{% set nav = 'dashboard' %}
{% block title %}{{ t('dashboard.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import progress_pill, copy_inline, row_menu_begin, row_menu_end, onboarding_banner, onboarding_finish, onboarding_finish_strip, onboarding_welcome, next_action, deadline_badge, property_identity, sync_calendars_button, guest_count with context %}
```

Anchor B, `App/tests/test_host_geometry.py`:

```
        page.wait_for_selector(".dashboard-actions .action-group", timeout=30000)
```

Anchor C, `docs/design/catalog.json`:

```
  "enforced_templates": ["App/app/templates/dev_ui.html"],
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/dashboard.html` | rewrite | the whole file (step 1) |
| `docs/design/catalog.json` | edit | enforce the template; dashboard hooks |
| `App/tests/test_host_geometry.py` | edit | header selector (Anchor B and the measurements that follow it) |
| `App/tests/test_design_dashboard.py` | create | slots and hooks |

No other file may change.

## 4. Steps

1. Replace the whole content of `App/app/templates/dashboard.html` (verify Anchor A is its first six lines first) with:

```
{% extends "host_page.html" %}
{% set nav = 'dashboard' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import progress_pill, copy_inline, row_menu_begin, row_menu_end, onboarding_banner, onboarding_finish, onboarding_finish_strip, onboarding_welcome, next_action, deadline_badge, property_identity, sync_calendars_button, guest_count with context %}
{% set show_welcome = not apartments and not onboarding.dismissed %}
{% block title %}{{ t('dashboard.title') }}{% endblock %}
{% block page_title %}{% if not show_welcome %}{{ t('dashboard.title') }}{% endif %}{% endblock %}
{% block meta %}{{ today.isoformat() | date_cz }}{% if last_sync %} · {{ t('dashboard.last_synced', when=last_sync | datetime_local) }}{% endif %}{% endblock %}
{% block primary_action %}{% if not show_welcome %}{{ ui_button('+ ' ~ t('stays.add_stay'), 'primary', href='/reservations?new=1', attrs='data-calendar-add data-cal-create-type="stay"') }}{% endif %}{% endblock %}
{% block secondary_actions %}{% if not show_welcome %}
  {{ ui_button('+ ' ~ t('calendar.add_cleaning'), 'secondary', href='/cleaning/new', attrs='data-calendar-add data-cal-create-type="cleaning"') }}
  {% if feed_count %}{{ sync_calendars_button(return_to='/', last_sync=none) }}{% endif %}
  {% if demo_loaded %}<form method="post" action="/demo/reset" class="inline" data-confirm data-confirm-message="{{ t('confirm.clear_demo') }}">{{ ui_button(t('demo.clear'), 'quiet', type='submit') }}</form>{% endif %}
  {{ ui_icon_button(t('common.more_actions'), 'ellipsis-vertical', attrs='class="ui-btn ui-btn-quiet ui-btn-icon ui-ph-menu" data-toggle-panel="dashboard-more"') }}
{% endif %}{% endblock %}

{% macro dashboard_rows(items, empty_key) %}
{% if items %}
<div class="ui-table-wrap">
{{ ui_table_begin([(t('host.stay_dates'), ''), (t('stays.table.apartment'), ''), (t('stays.table.guests'), 'r'), (t('dashboard.table.task'), ''), ('', '')], t('dashboard.section.needs_action', count=items | length)) }}
{% for row in items %}
  {% set reservation = row.reservation %}{% set progress = row.progress %}{% set cell = row.deadline_cell %}
  {% set stay_label = reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else reservation.internal_name %}
  <tr class="ui-row dashboard-row clickable-row" data-stay-id="{{ reservation.id }}" data-href="/reservations/{{ reservation.id }}?return_to=/" tabindex="0" role="link"
      aria-label="{{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }} · {{ reservation.internal_name }}">
    <td class="ui-cell-first dashboard-row-copy"><a class="dashboard-row-property" href="/reservations/{{ reservation.id }}?return_to=/">{{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }}</a>
      <span class="ui-sub dashboard-row-dates">{% if row.deadline and cell.state == 'countdown' and cell.level != 'future' %}{{ t('dashboard.table.deadline_by', when=row.deadline.strftime('%d.%m. %H:%M')) }}{% endif %}</span></td>
    <td>{{ property_identity(reservation.apartment_id, stay_label, true) }}</td>
    <td class="ui-cell-r ui-num">{{ guest_count(progress) }}</td>
    <td class="dashboard-row-task">
      {% if cell.level == 'overdue' %}{{ deadline_badge(cell) }}
      {% elif progress.status == 'failed' %}{{ progress_pill(progress.status, reservation.automation_mode) }}
      {% elif progress.not_registered %}<span class="ui-badge ui-badge-action" data-tone="amber">{{ tp('host.missing', progress.not_registered) }}</span>
      {% elif cell.state in ('filed_on_time', 'filed_late') %}{{ deadline_badge(cell) }}
      {% elif progress.status in ('reported', 'not_required') %}{{ next_action(progress, reservation) }}
      {% elif progress.status == 'awaiting_guest' %}{# Routine waiting is shown as occupancy, not a task. #}
      {% else %}{{ progress_pill(progress.status, reservation.automation_mode, is_demo=('(demo)' in reservation.internal_name or reservation.source == 'demo')) }}{% endif %}
    </td>
    <td class="ui-cell-acts dashboard-row-actions">
      {{ row_menu_begin() }}
        <a class="row-menu-item" href="/reservations/{{ reservation.id }}?return_to=/" role="menuitem">{{ t('common.open') }}</a>
        <a class="row-menu-item" href="/reservations/{{ reservation.id }}/guests/new" role="menuitem">{{ t('dashboard.row.add_guest') }}</a>
        {% if reservation.permalink_token %}
        <a class="row-menu-item" href="/l/{{ reservation.permalink_slug or reservation.permalink_token }}/{{ reservation.id }}" target="_blank" rel="noopener" role="menuitem">{{ t('dashboard.row.open_guest_form') }}</a>
        {{ copy_inline('dashboard-stay-link-' ~ reservation.id, public_base_url ~ '/l/' ~ (reservation.permalink_slug or reservation.permalink_token) ~ '/' ~ reservation.id, t('host.copy_guest_form_link'), 'menuitem') }}
        {% endif %}
        <form method="post" action="/reservations/{{ reservation.id }}/archive" class="row-menu-form" data-confirm data-confirm-message="{{ t('host.delete_to_archived.confirm') }}">
          <input type="hidden" name="return_to" value="/"><button class="row-menu-item" type="submit" role="menuitem">{{ t('host.delete') }}</button>
        </form>
      {{ row_menu_end() }}
    </td>
  </tr>
{% endfor %}
{{ ui_table_end() }}
</div>
<div class="ui-cards">
{% for row in items %}
  {% set reservation = row.reservation %}{% set progress = row.progress %}{% set cell = row.deadline_cell %}
  {% set stay_label = reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else reservation.internal_name %}
  {% set badge %}{% if cell.level == 'overdue' %}{{ deadline_badge(cell) }}{% elif progress.status == 'failed' %}{{ progress_pill(progress.status, reservation.automation_mode) }}{% elif progress.not_registered %}<span class="ui-badge ui-badge-action" data-tone="amber">{{ tp('host.missing', progress.not_registered) }}</span>{% elif cell.state in ('filed_on_time', 'filed_late') %}{{ deadline_badge(cell) }}{% elif progress.status not in ('awaiting_guest', 'reported', 'not_required') %}{{ progress_pill(progress.status, reservation.automation_mode) }}{% endif %}{% endset %}
  {{ ui_card('/reservations/' ~ reservation.id ~ '?return_to=/', (reservation.date_from | date_cz) ~ ' – ' ~ (reservation.date_to | date_cz), stay_label, guest_count(progress), badge) }}
{% endfor %}
</div>
{% else %}{{ ui_empty(t(empty_key)) }}{% endif %}
{% endmacro %}

{% block body %}
{% if not apartments %}
  {% if not onboarding.dismissed %}{{ onboarding_welcome(onboarding, compact=True) }}
  {% else %}{% call ui_empty(t('onboarding.skipped_title'), t('onboarding.skipped_body'), t('apartments.add'), '/apartments/new') %}{{ ui_button(t('onboarding.open_checklist'), 'secondary', href='/onboarding') }}{% endcall %}{% endif %}
{% else %}
  <div id="dashboard-more" class="ui-btn-group hidden" data-panel>{{ ui_button('+ ' ~ t('calendar.add_cleaning'), 'secondary', href='/cleaning/new') }}{% if feed_count %}{{ sync_calendars_button(return_to='/', last_sync=none) }}{% endif %}</div>
  <nav class="ui-stats" aria-label="{{ t('nav.overview') }}" data-dashboard-refresh="stats">
    <a class="ui-stat" href="#needs-action"><strong class="ui-num">{{ counts.attention }}</strong><span>{{ t('dashboard.stat.action') }}</span></a>
    <a class="ui-stat" href="/reservations"><strong class="ui-num">{{ counts.ready }}</strong><span>{{ t('dashboard.stat.ready') }}</span></a>
    <a class="ui-stat" href="#needs-action"><strong class="ui-num">{{ counts.overdue }}</strong><span>{{ t('dashboard.stat.overdue') }}</span></a>
  </nav>
  {% call ui_section('') %}{% include "_dashboard_calendar.html" %}{% endcall %}
  <div data-dashboard-refresh="work">
  {% set focus_is_urgent = focus and focus.urgency in ('overdue', 'urgent') %}
  {% set finish_card_showing = onboarding and onboarding.finished and onboarding.finish and not onboarding.dismissed %}
  {% set banner_showing = onboarding and onboarding.current and not onboarding.finished and not onboarding.dismissed %}
  {% if missing_report_display and not banner_showing %}
  {% set anchor_query = {'basics': 'view=settings&section=property', 'address': 'view=settings&section=property', 'ubyport': 'view=settings&section=reporting', 'calendars': 'view=bookings'} %}
  {% set missing_text %}
    {% for row in missing_report_display %}
    <span class="dashboard-missing-line"><strong>{{ property_identity(row.apartment.id, row.apartment.internal_name, true) }}</strong>: {{ t('dashboard.missing_banner.missing') }}
      {% for item in row.missing %}<a href="/apartments/{{ row.apartment.id }}?{{ anchor_query.get(item.anchor, 'view=settings') }}#{{ item.anchor }}">{{ t('apartment.form.readiness.item.' ~ item.key) }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</span>
    {% endfor %}
    {% if missing_report_more %}<a href="/apartments">{{ t('dashboard.missing_banner.and_more', count=missing_report_more) }}</a>{% endif %}
  {% endset %}
  {{ ui_banner('attention', missing_text) }}
  {% endif %}
  {% call ui_section(t('dashboard.section.needs_action', count=counts.attention), actions='<a href="/reservations">' ~ t('dashboard.section.view_stays') ~ '</a>', id='needs-action') %}
    {{ dashboard_rows(queue_groups.needs_action, 'dashboard.queue.empty.action') }}
    {% if additional_action_count %}<p class="ui-sub"><a href="/reservations">{{ t('dashboard.more_action', count=additional_action_count) }}</a></p>{% endif %}
  {% endcall %}
  {% if finish_card_showing and focus_is_urgent %}{{ onboarding_finish_strip(onboarding) }}{% endif %}
  {{ onboarding_banner(onboarding) }}
  {% if not rows and feed_count %}{% call ui_empty(t('dashboard.empty.no_stays')) %}{{ sync_calendars_button(return_to='/', label_key='dashboard.empty.sync_now') }}{% endcall %}
  {% elif not rows %}{{ ui_empty(t('dashboard.empty.no_feed'), '', t('dashboard.empty.connect_calendar'), '/apartments/' ~ apartments[0].id ~ '?view=bookings#calendars', primary=false) }}
  {% endif %}
  <noscript>
    {% if queue_groups.current %}{% call ui_section(t('dashboard.section.current'), actions='<a href="/reservations">' ~ t('dashboard.section.view_stays') ~ '</a>', id='current') %}{{ dashboard_rows(queue_groups.current, 'dashboard.queue.empty.waiting') }}{% endcall %}{% endif %}
  </noscript>
  {% if finish_card_showing and not focus_is_urgent %}{{ onboarding_finish(onboarding) }}{% endif %}
  </div>
{% endif %}
{% endblock %}
```

   Notes: the empty-state buttons use `primary=false` because the header already holds the one primary. `t('dashboard.table.task')` may not exist: run `grep -n '"dashboard.table.task"' App/app/host_i18n.py`; if absent, use `t('dashboard.stat.action')` for that column label instead and say so in the report. Command: `cd App && .venv/bin/python -c "from app.templating import templates; templates.get_template('dashboard.html'); print('compiles')"`. Expected: `compiles`.

2. In `docs/design/catalog.json`: replace Anchor C with `  "enforced_templates": ["App/app/templates/dev_ui.html", "App/app/templates/dashboard.html"],` and add to `hooks`: `"dashboard-row", "dashboard-row-copy", "dashboard-row-task", "dashboard-row-actions", "dashboard-row-property", "dashboard-row-dates", "dashboard-missing-line", "ui-table-wrap"` (and `"ui-table-wrap"` also to `classes`). Command: `python3 scripts/design_lint.py`. Expected: OK; if it names a class in `dashboard.html` that is not listed, it is either a typo in the template (fix the template) or a missing hook from this list (add it, report it).

3. In `App/tests/test_host_geometry.py`, replace Anchor B with `        page.wait_for_selector(".ui-ph-acts", timeout=30000)` and, in the lines that follow it (read 63 to 134 first), change every `.dashboard-actions .action-group` to `.ui-ph-acts` and every `.action-group > *` or `.action-group .btn` to `.ui-ph-acts .ui-btn`; keep the assertions (equal heights, equal gaps, shared right edge). Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed, 0 skipped.

4. Create `App/tests/test_design_dashboard.py`:

```python
"""Dashboard on host_page.html (docs/design/pages/dashboard.md)."""
import re

from tests.test_signed_in_chrome import empty_host, host_with_property  # noqa: F401


def test_dashboard_with_a_property_has_the_v2_header_one_primary_and_refresh_hooks(host_with_property):
    page = host_with_property.get("/?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="detail"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert 'data-dashboard-refresh="stats"' in page and 'data-dashboard-refresh="work"' in page
    assert 'class="ui-stats"' in page and page.count('class="ui-stat"') == 3
    assert "dashboard-stats" not in page and "page-toolbar" not in page
    assert 'data-skeleton-kind="detail"' in page


def test_the_zero_state_keeps_the_welcome_card_and_one_h1(empty_host):
    page = empty_host.get("/?lang=en").text
    assert page.count("<h1") == 1
    assert 'class="onboarding-welcome"' in page
    assert 'class="ui-ph"' not in page


def test_no_raw_style_or_pill_in_the_dashboard_template():
    text = open("app/templates/dashboard.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="pill' not in text and "<svg" not in text
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_dashboard.py tests/test_signed_in_chrome.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_quiet_dashboard_browser.py tests/test_dashboard_calendar_browser.py tests/test_onboarding_followup_browser.py tests/test_host_list_layouts_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Where a test reads `.dashboard-row-dates` text or `.dashboard-row-copy` text, the hooks are kept; where one reads `.dashboard-stat.is-positive` or `.dashboard-actions`, update that selector to `.ui-stat` or `.ui-ph-acts` and list the file in the report.

6. Commit: `git add App/app/templates/dashboard.html docs/design/catalog.json App/tests && git commit -m "0133 step 6: dashboard on host_page (detail kind)"`.

## 5. Do not touch

`_dashboard_calendar.html`, `dashboard-calendar.js`, `dashboard-calendar.css`, `app/reporting.py`, routes; onboarding macros; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- `cd App && .venv/bin/python -m pytest tests/test_design_dashboard.py tests/test_signed_in_chrome.py tests/test_archive_stays_on_page.py tests/test_query_budget.py -q --tb=short 2>&1 | tail -30` expected: passed.
- Browser row from step 5, plus `tests/test_host_geometry.py`, 0 skipped.

## 7. Acceptance

- [ ] One h1, one primary, stats, banner, calendar, Needs-you table (1280) and cards (390).
- [ ] 390 px and 1280 px screenshots attached; dashboard skeleton is the detail skeleton (`/?__skeleton` is not needed: show it by throttling or attach the catalog shot).
- [ ] Lint passes with `dashboard.html` enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change (test selector updates named in step 5 excepted); section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0133-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/dashboard.html` (row grammar, refresh hooks).

## Owner steps

None.
