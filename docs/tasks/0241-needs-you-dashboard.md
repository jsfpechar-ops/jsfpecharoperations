# 0241: "What needs you" on the dashboard (idea N)

Status: todo
Depends on: 0240 | Base commit: after 0240 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The dashboard opens with one bordered card, "What needs you": every alert, every stay that needs the host, unfinished police setup and the paste reminder, each as one line with one button, or "Nothing needs you today. 3 stays are on track." It replaces four blocks that said the same things in different places: the alert stack (on the dashboard only), the three count tiles, the setup banner, the paste card and the "Needs action now" table.

## 2. Context

- 0240 added `needs_you.build(rows, queue, cards, missing_rows, link_unused, lang, today)` as the template global `needs_you_build`, the copy and the CSS classes `needs-you*`.
- Law (alerts.py docstring): a refused record must be shown on every screen. On the dashboard the card shows the same alerts at the top, so the separate stack is hidden there only (`hide_alert_stack`). Every other page keeps the stack.
- The dashboard's live refresh (`dashboard-calendar.js`) swaps the regions `[data-dashboard-refresh="stats"]` and `[data-dashboard-refresh="work"]` after a stay is added from the calendar. The card sits in the "stats" region, so no JS change is needed.
- The `dashboard_rows` macro stays, because the `<noscript>` "Current stays" list still uses it.
- Owner rules: no description walls outside the wizard, visible borders, WCAG 2.2 AA, one primary button per page header (the card uses secondary buttons).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | two context keys (step 1) |
| `App/app/templates/base.html` | edit | stack can be hidden (step 2) |
| `App/app/templates/dashboard.html` | replace | whole file (step 3) |
| `App/app/needs_you.py` | edit | no-form wording (step 4) |
| `App/tests/test_alert_stack.py` | edit | read the stack on the stays page (step 5) |
| `App/tests/test_dashboard_queue_copy.py` | edit | two tests (step 6) |
| `App/tests/test_host_language.py` | edit | two tests (step 7) |
| `App/tests/test_dashboard_missing_banner.py` | replace | whole file (step 8) |
| `App/tests/test_design_dashboard.py` | edit | one line (step 9) |
| `App/tests/test_deadline_after_reporting.py` | edit | two lines (step 9) |
| `App/tests/test_signed_in_chrome.py` | edit | two tests (step 10) |
| `App/tests/test_needs_you_dashboard_0241.py` | create | tests (step 11) |
| `docs/tasks/0241-report.md` | create | report |

No other file may change. Browser tests are brief 0242; do not run or edit them here.

## 4. Steps

### Step 1. `routes/admin.py`: two context keys

Anchor (exact line, in `def dashboard`): `            "missing_report_more": missing_report_more,`

Replace with:

```python
            "missing_report_more": missing_report_more,
            # 0241: "What needs you" reads every property and every bucket.
            "missing_report_rows": missing_report_rows,
            "needs_you_queue": queue,
```

Command: `cd App && .venv/bin/python -c "import app.routes.admin" 2>&1 | tail -3` → no output. Commit `0241 step 1`.

### Step 2. `base.html`: the stack can be hidden

Anchor (exact line): `    {% include "_host_alerts.html" %}`

Replace with: `    {% if not hide_alert_stack | default(false) %}{% include "_host_alerts.html" %}{% endif %}`

Commit `0241 step 2`.

### Step 3. Replace `App/app/templates/dashboard.html` with exactly this content

```jinja
{% extends "host_page.html" %}
{% set nav = 'dashboard' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import progress_pill, copy_inline, row_menu_begin, row_menu_end, onboarding_banner, onboarding_finish, onboarding_finish_strip, onboarding_welcome, next_action, deadline_badge, property_identity, guest_count with context %}
{% from "_icons.html" import icon with context %}
{% set show_welcome = not apartments and not onboarding.dismissed %}
{# 0241: the "What needs you" card carries the alerts here, so the stack is not shown twice. #}
{% set hide_alert_stack = (apartments or []) | length > 0 %}
{% block title %}{{ t('dashboard.title') }}{% endblock %}
{% block page_title %}{% if not show_welcome %}{{ t('dashboard.title') }}{% endif %}{% endblock %}
{% block meta %}{{ today.isoformat() | date_cz }}{% if last_sync %} · {{ t('dashboard.last_synced', when=last_sync | datetime_local) }}{% endif %}{% endblock %}
{% block primary_action %}{% if not show_welcome %}{{ ui_button('+ ' ~ t('stays.add_stay'), 'primary', href='/reservations?new=1', attrs='data-calendar-add data-cal-create-type="stay"') }}{% endif %}{% endblock %}
{% block secondary_actions %}{% if not show_welcome %}
  {{ ui_button('+ ' ~ t('calendar.add_cleaning'), 'secondary', href='/cleaning/new', attrs='data-calendar-add data-cal-create-type="cleaning"') }}
  
  {% if demo_loaded %}<form method="post" action="/demo/reset" class="inline" data-confirm data-confirm-message="{{ t('confirm.clear_demo') }}">{{ ui_button(t('demo.clear'), 'quiet', type='submit') }}</form>{% endif %}
  {{ ui_icon_button(t('common.more_actions'), 'ellipsis-vertical', attrs='data-toggle-panel="dashboard-more"', extra_class='ui-ph-menu') }}
{% endif %}{% endblock %}

{% macro dashboard_rows(items, empty_key) %}
{% if items %}
<div class="ui-table-wrap">
{{ ui_table_begin([(t('host.stay_dates'), ''), (t('stays.table.apartment'), ''), (t('stays.table.guests'), 'r'), (t('dashboard.stat.action'), ''), ('', '')], t('dashboard.section.needs_action', count=items | length)) }}
{% for row in items %}
  {% set reservation = row.reservation %}{% set progress = row.progress %}{% set cell = row.deadline_cell %}
  {% set stay_label = reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else reservation.internal_name %}
  <tr class="ui-row dashboard-row clickable-row{{ ' is-overdue' if cell.level == 'overdue' }}" data-stay-id="{{ reservation.id }}" data-href="/reservations/{{ reservation.id }}?return_to=/" tabindex="0" role="link"
      aria-label="{{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }} · {{ reservation.internal_name }}">
    <td class="ui-cell-first dashboard-row-copy" data-card="primary"><a class="dashboard-row-property" href="/reservations/{{ reservation.id }}?return_to=/">{{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }}</a>
      <span class="ui-sub dashboard-row-dates">{% if row.deadline and cell.state == 'countdown' and cell.level != 'future' %}{{ t('dashboard.table.deadline_by', when=row.deadline.strftime('%d.%m. %H:%M')) }}{% endif %}</span></td>
    <td data-card="secondary">{{ property_identity(reservation.apartment_id, stay_label, true) }}</td>
    <td class="ui-cell-r ui-num" data-card="meta">{{ guest_count(progress) }}</td>
    <td class="dashboard-row-task" data-card="badge">
      {% if cell.level == 'overdue' %}{{ deadline_badge(cell) }}
      {% elif progress.status == 'failed' %}{{ progress_pill(progress.status, reservation.automation_mode) }}
      {% elif progress.not_registered %}<span class="ui-badge ui-badge-action" data-tone="amber">{{ tp('host.missing', progress.not_registered) }}</span>
      {% elif cell.state in ('filed_on_time', 'filed_late') %}{{ deadline_badge(cell) }}
      {% elif progress.status in ('reported', 'not_required') %}{{ next_action(progress, reservation) }}
      {% elif progress.status == 'awaiting_guest' %}{# Routine waiting is shown as occupancy, not a task. #}
      {% else %}{{ progress_pill(progress.status, reservation.automation_mode, is_demo=('(demo)' in reservation.internal_name or reservation.source == 'demo')) }}{% endif %}
    </td>
    <td class="ui-cell-acts dashboard-row-actions" data-card="actions">
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
{% else %}{{ ui_empty(t(empty_key)) }}{% endif %}
{% endmacro %}

{#- 0241 (idea N): one line of "What needs you": subject, one sentence, one button. -#}
{% macro needs_you_line(line) %}
<li class="needs-you-item" data-tone="{{ line.tone }}" data-needs-you="{{ line.kind }}"{% if line.stay_id %} data-needs-you-stay="{{ line.stay_id }}"{% endif %}{% if line.dismiss_id %} data-notification{% endif %}>
  <div class="needs-you-copy"><strong>{{ line.subject }}</strong>{% if line.text %}<span>{{ line.text }}</span>{% endif %}</div>
  {% if line.href or line.dismiss_id %}
  <div class="needs-you-actions">
    {% if line.href %}{{ ui_button(line.action, 'secondary', href=line.href) }}{% endif %}
    {% if line.dismiss_id %}<form method="post" action="/alerts/{{ line.dismiss_id }}/dismiss" class="needs-you-dismiss" data-notification-dismiss>{{ ui_icon_button(t('a11y.dismiss_notification'), 'x', type='submit') }}</form>{% endif %}
  </div>
  {% endif %}
</li>
{% endmacro %}

{% block body %}
{% if not apartments %}
  {% if not onboarding.dismissed %}{{ onboarding_welcome(onboarding, compact=True) }}
  {% else %}{% call ui_empty(t('onboarding.skipped_title'), t('onboarding.skipped_body'), t('apartments.add'), '/apartments/new') %}{{ ui_button(t('onboarding.open_checklist'), 'secondary', href='/onboarding') }}{% endcall %}{% endif %}
{% else %}
  <div id="dashboard-more" class="ui-btn-group hidden" data-panel>{{ ui_button('+ ' ~ t('calendar.add_cleaning'), 'secondary', href='/cleaning/new') }}</div>
  {% set banner_showing = onboarding and onboarding.current and not onboarding.finished and not onboarding.dismissed %}
  {% set needs_you = needs_you_build(rows, needs_you_queue, open_alerts, missing_report_rows, link_unused, lang, today) %}
  {% set ny_lines = (needs_you.lines | rejectattr('kind', 'equalto', 'setup') | list) if banner_showing else needs_you.lines %}
  <div data-dashboard-refresh="stats">
  <section class="needs-you" id="needs-action" data-needs-you-card aria-labelledby="needs-you-title">
    <h2 id="needs-you-title">{{ t('needs_you.title') }}{% if ny_lines %} <span class="ui-badge ui-badge-action" data-tone="{{ 'red' if ny_lines[0].tone == 'red' else 'amber' }}">{{ ny_lines | length }}</span>{% endif %}</h2>
    {% if ny_lines %}
    <ul class="needs-you-list">{% for line in ny_lines[:5] %}{{ needs_you_line(line) }}{% endfor %}</ul>
    {% if ny_lines | length > 5 %}
    <details class="needs-you-more"><summary>{{ tp('needs_you.more', ny_lines | length - 5) }}</summary>
      <ul class="needs-you-list">{% for line in ny_lines[5:] %}{{ needs_you_line(line) }}{% endfor %}</ul>
    </details>
    {% endif %}
    {% if ny_lines | selectattr('kind', 'equalto', 'paste') | list %}
    <details class="needs-you-more" data-paste-check><summary>{{ t('workflow.paste.how') }}</summary>
      <ul class="needs-you-how">
        <li>{{ t('workflow.paste.airbnb') }}</li>
        <li>{{ t('workflow.paste.booking') }}</li>
        <li>{{ t('workflow.paste.direct') }}</li>
      </ul>
    </details>
    {% endif %}
    {% else %}
    <p class="needs-you-calm">{{ icon('check', 20) }}<strong>{{ t('needs_you.calm') }}</strong>{% if needs_you.on_track %}<span>{{ tp('needs_you.on_track', needs_you.on_track) }}</span>{% endif %}</p>
    {% endif %}
  </section>
  </div>
  {% include "_dashboard_calendar.html" %}
  <div data-dashboard-refresh="work">
  {% set focus_is_urgent = focus and focus.urgency in ('overdue', 'urgent') %}
  {% set finish_card_showing = onboarding and onboarding.finished and onboarding.finish and not onboarding.dismissed %}
  {% if finish_card_showing and focus_is_urgent %}{{ onboarding_finish_strip(onboarding) }}{% endif %}
  {{ onboarding_banner(onboarding) }}
  {% if not rows %}{% from "_workflow.html" import workflow_strip with context %}{{ workflow_strip(apartments[0] if apartments | length == 1 else none) }}{% endif %}
  {% if not rows and feed_count %}{{ ui_empty(t('dashboard.empty.no_stays')) }}
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

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_design_lint.py tests/test_paste_check_0233.py tests/test_dashboard_order.py -q --tb=short 2>&1 | tail -15`. `test_alert_stack.py` may fail here; step 5 fixes it. Any other failure: STOP. Commit `0241 step 3`.

### Step 4. `needs_you.py`: "has not filled in" when no guest has started

A stay with a guest count but no guest yet has status `incomplete`; it should still read "has not filled in the guest form". Anchor (exact line):

```python
        key = "needs_you.stay.no_form" if status == "awaiting_guest" else "needs_you.stay.forms_missing"
```

Replace with:

```python
        started = bool(row["progress"].get("guests"))
        key = "needs_you.stay.forms_missing" if started else "needs_you.stay.no_form"
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_0240.py -q --tb=short 2>&1 | tail -5` (the 0240 tests must still pass). Commit `0241 step 4`.

### Step 5. `test_alert_stack.py`: read the stack on the stays page

The stack is still on every page except the dashboard. Run from `App/`:

```bash
sed -i "s#host.get(\"/?lang=#host.get(\"/reservations?lang=#g; s#host.get('/?lang=#host.get('/reservations?lang=#g" tests/test_alert_stack.py && grep -c 'get(./reservations?lang=' tests/test_alert_stack.py
```

Expected: `7`. Commit `0241 step 5`.

### Step 6. `test_dashboard_queue_copy.py`: two tests

Replace the whole function `test_the_action_heading_counts_the_rows_beneath_it` (from its `def` line to the line before the next `def`) with:

```python
def test_the_card_gives_each_stay_that_needs_the_host_one_line(seeded):
    page = _page("en")
    card = _needs_action_section(page)
    assert host_i18n.translate("en", "needs_you.title") in card
    lines = re.findall(r'<li class="needs-you-item"[^>]*>(.*?)</li>', card, re.S)
    assert lines, "the seeded ready stay should need the host"
    for line in lines:
        assert line.count('class="ui-btn') == 1, line
```

Replace the whole function `test_the_action_heading_never_leaks_its_placeholder` with:

```python
def test_the_card_never_leaks_a_placeholder(seeded):
    for lang in ("en", "cs"):
        card = _needs_action_section(_page(lang))
        assert "%(" not in card
        assert host_i18n.translate(lang, "needs_you.title") in card
```

Commit `0241 step 6`.

### Step 7. `test_host_language.py`: two tests

Replace the whole function `test_the_next_action_on_a_czech_queue_row_is_czech` with:

```python
def test_the_next_action_on_a_czech_queue_row_is_czech():
    page = _host_with_a_stay_needing_action().get("/")
    assert page.status_code == 200
    card = re.search(r'<section[^>]*id="needs-action"[^>]*>(.*?)</section>', page.text, re.S)
    assert card, "no What needs you card on the dashboard"
    english = host_i18n.translate("en", "needs_you.stay.ready")
    czech = host_i18n.translate("cs", "needs_you.stay.ready")
    assert czech != english, "fixture is pointless if the two languages match"
    assert english not in card.group(1), "the line on the dashboard is in English for a Czech host"
    assert czech in card.group(1)
```

In the function `test_the_status_pill_on_a_czech_queue_row_is_czech`, replace its first line `    page = _host_with_a_stay_needing_action().get("/")` with `    page = _host_with_a_stay_needing_action().get("/reservations")` (the status pill now lives on the stays list). Change nothing else.

Commit `0241 step 7`.

### Step 8. Replace `App/tests/test_dashboard_missing_banner.py` with exactly this content

```python
"""The dashboard names a property whose police setup is unfinished, in one line (0241).

It used to list every missing field in a banner; the owner asked for one short
line and one button that opens the first missing field.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "dashboard-missing-banner-host"

COMPLETE_VALUES = {
    "uby_idub": "123456789012",
    "uby_mark": "AAKLI",
    "uby_name": "Banner Flat",
    "uby_ws_user": "uby-ws1a2b3c",
    "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
    "addr_obec": "Praha",
    "addr_house_no": "12",
    "addr_zip": "12000",
}


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        apartment_ids = [
            row["id"]
            for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,))
        ]
        for apartment_id in apartment_ids:
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _insert_apartment(internal_name: str, **overrides) -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": f"{internal_name} s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@banner.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    payload = {
        "legal_entity_id": entity_id,
        "owner_user_id": _owner_id(),
        "internal_name": internal_name,
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "12000",
        "permalink_token": f"banner{internal_name.lower().replace(' ', '')}",
        "permalink_pin": "123456",
        "automation_mode": "manual",
        "submit_after_hours": 24,
        "active": 1,
        "created_at": db.utcnow(),
    }
    payload.update(overrides)
    return db.insert("apartment", payload)


def _setup_lines(text: str) -> list[str]:
    return re.findall(r'<li class="needs-you-item"[^>]*data-needs-you="setup"[^>]*>(.*?)</li>', text, re.S)


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Banner Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    client.post("/onboarding/dismiss", data={"return_to": "/"}, follow_redirects=False)
    try:
        yield client
    finally:
        _cleanup()


def test_one_short_line_opens_the_first_missing_police_field(host):
    apartment_id = _insert_apartment("Order Flat")

    page = host.get("/?lang=en")

    lines = _setup_lines(page.text)
    assert len(lines) == 1
    line = lines[0]
    assert "Order Flat" in line
    assert host_i18n.STRINGS["en"]["needs_you.setup"] in line
    assert f'href="/apartments/{apartment_id}?view=settings&amp;section=reporting#ubyport"' in line
    # The owner asked for no field-by-field list on the dashboard.
    assert "IDUB" not in line and "Password" not in line
    assert line.count('class="ui-btn') == 1


def test_no_line_when_reporting_is_ready(host):
    apartment_id = _insert_apartment("Ready Flat", **COMPLETE_VALUES)
    db.update("apartment", apartment_id, COMPLETE_VALUES)

    page = host.get("/?lang=en")

    assert _setup_lines(page.text) == []


def test_lines_past_the_fifth_wait_behind_show_more(host):
    for index in range(1, 7):
        _insert_apartment(f"Banner Flat {index}")

    page = host.get("/?lang=en")

    assert len(_setup_lines(page.text)) == 6
    assert "Show 1 more" in page.text
    before_more = page.text.split('class="needs-you-more"', 1)[0]
    assert len(_setup_lines(before_more)) == 5


def test_inactive_properties_are_omitted(host):
    _insert_apartment("Inactive Flat", active=0)

    page = host.get("/?lang=en")

    assert _setup_lines(page.text) == []


def test_the_setup_line_is_in_czech(host):
    _insert_apartment("Czech Flat")

    page = host.get("/?lang=cs")

    line = _setup_lines(page.text)[0]
    assert host_i18n.STRINGS["cs"]["needs_you.setup"] in line
    assert host_i18n.STRINGS["cs"]["needs_you.action.setup"] in line
```

Commit `0241 step 8`.

### Step 9. Two small test edits

In `App/tests/test_design_dashboard.py`, replace the line

```python
    assert 'class="ui-stats' in page and len(re.findall(r'class="[^"]*\bui-stat\b[^"]*"', page)) == 3
```

with

```python
    # 0241: the count tiles gave way to the "What needs you" card.
    assert 'class="needs-you"' in page and 'class="ui-stats' not in page
```

In `App/tests/test_deadline_after_reporting.py`, the line `            assert task and host_i18n.STRINGS["en"]["action.reported"] not in task.group(1)` appears twice. Replace both with `            assert not task or host_i18n.STRINGS["en"]["action.reported"] not in task.group(1)` (the dashboard no longer has a task column for stays that need nothing).

Commit `0241 step 9`.

### Step 10. `test_signed_in_chrome.py`: two tests

Replace the whole function `test_dashboard_status_counts_use_distinct_colours` with:

```python
def test_dashboard_opens_with_the_what_needs_you_card(host_with_property):
    page = host_with_property.get("/?lang=en").text

    assert 'id="needs-action"' in page
    assert host_i18n.STRINGS["en"]["needs_you.title"] in page
    assert 'class="dashboard-stat' not in page
    assert page.index('id="needs-action"') < page.index("data-calendar")
```

Replace the whole function `test_positive_action_count_uses_semantic_color_and_zeros_stay_neutral` with:

```python
def test_a_stay_that_needs_the_host_gets_one_line_with_one_button(host_with_property):
    owner_id = _owner_id()
    apartment = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ?", (owner_id,))
    today = claim.prague_today()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment["id"], "source": "manual", "uid": "chrome-action-stay",
        "date_from": (today + timedelta(days=1)).isoformat(),
        "date_to": (today + timedelta(days=3)).isoformat(), "status": "active",
        "expected_guests_override": 1, "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    try:
        page = host_with_property.get("/?lang=en").text
        line = re.search(
            rf'<li class="needs-you-item"[^>]*data-needs-you-stay="{reservation_id}"[^>]*>(.*?)</li>', page, re.S
        )
        assert line, "the stay arriving tomorrow has no line"
        assert "The guest arrives tomorrow and has not filled in the guest form." in line.group(1)
        assert line.group(1).count('class="ui-btn') == 1
        assert f'href="/reservations/{reservation_id}?return_to=/#stay-link"' in line.group(1)
    finally:
        db.execute("DELETE FROM reservation WHERE id = ?", (reservation_id,))
```

Leave `test_stat_tiles_use_the_status_tokens` as it is (it reads a stylesheet). Commit `0241 step 10`.

### Step 11. Create `App/tests/test_needs_you_dashboard_0241.py` with exactly this content

```python
"""0241 (idea N): the dashboard card carries the alerts; other pages keep the stack."""

from __future__ import annotations

from app import db
from tests.test_alert_stack import _alert, host  # noqa: F401
from tests.test_signed_in_chrome import host_with_property  # noqa: F401


def test_alerts_show_once_on_the_dashboard_and_still_on_other_pages(host_with_property):  # noqa: F811
    owner = db.query_one("SELECT owner_user_id FROM apartment ORDER BY id DESC LIMIT 1")
    db.insert("alert", {
        "level": "warning", "kind": "feed_error", "apartment_id": None,
        "owner_user_id": owner["owner_user_id"], "dedupe_key": "wf0241-feed",
        "message": "Calendar 'Test' could not be synchronised.", "detail": "boom",
        "params": '{"feed": "Test", "error": "boom"}', "created_at": db.utcnow(),
    })
    try:
        dashboard = host_with_property.get("/?lang=en").text
        assert "data-host-alerts" not in dashboard, "the stack repeats the card on the dashboard"
        assert "Calendar &#39;Test&#39; could not be read." in dashboard or "Calendar 'Test' could not be read." in dashboard
        stays = host_with_property.get("/reservations?lang=en").text
        assert "data-host-alerts" in stays
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", ("wf0241-feed",))


def test_the_calm_line_when_nothing_needs_the_host(host_with_property):  # noqa: F811
    page = host_with_property.get("/?lang=en").text
    card = page.split('id="needs-action"', 1)[1].split("</section>", 1)[0]
    if 'class="needs-you-item"' not in card:
        assert "Nothing needs you today." in card
```

If `_alert` or `host` cannot be imported from `tests.test_alert_stack` (ImportError), remove that import line only; the tests do not use them. If the `alert` table has no `params` column (an error says so), remove the `"params"` entry only. Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_dashboard_0241.py -q --tb=short 2>&1 | tail -15` → pass. Commit `0241 step 11`.

## 5. Do not touch

Everything outside §3, in particular `reporting.py`, `alerts.py`, `dashboard-calendar.js`, every `*_browser.py` test (brief 0242), and the setup wizard and stay fee files (another thread is changing them).

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_dashboard_0241.py tests/test_needs_you_0240.py tests/test_dashboard_queue_copy.py tests/test_host_language.py tests/test_dashboard_missing_banner.py tests/test_design_dashboard.py tests/test_deadline_after_reporting.py tests/test_signed_in_chrome.py tests/test_paste_check_0233.py tests/test_dashboard_order.py tests/test_design_lint.py tests/test_plain_fixes_0239.py tests/test_notification_copy.py -q --tb=short 2>&1 | tail -20`
2. `cd App && grep -ln 'get("/?lang\|get("/")\|goto(f"{base}/?lang' tests/test_*.py | grep -v _browser | head -40` and then run those files together (with `tests/test_alert_stack.py` first): `.venv/bin/python -m pytest tests/test_alert_stack.py <the files> -q --tb=line 2>&1 | tail -25`. Any failure here that is about the removed tiles, banner, table or stack on "/": list it in the report with the file and line, and do not fix it. Failures with "no such table": list them too.
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] §6 command 1 passes.
- [ ] §6 command 2 failures (if any) are listed in the report.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0241-report.md` (600 tokens at most) and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/templates/dashboard.html` (whole page), `App/app/templates/base.html` (stack condition), the test rewrites in steps 5 to 10.

## Owner steps

None.
