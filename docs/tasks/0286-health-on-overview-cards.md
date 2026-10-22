# 0286: Property health check on the Overview cards (one place, not two)

Status: todo
Depends on: 0285 | Base commit: the 0285 commits | Branch: claude/project-thread-futwgu (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The property Overview shows its status twice: the shortcut cards and, below them, a separate "Health check" box. The owner wants one place: each checked card gets a status dot before its title (green fine, amber to do, red broken, grey off), a card with a problem names the problem and opens its fix, and the separate box goes. The "Checklist details" disclosure stays, as a plain collapsed line under the cards.

## 2. Context

- Health rows come from `App/app/property_health.py` (`checks()`): keys `calendar`, `guest_link`, `police`, `business`, `door`; `state` is ok | warn | bad | off; `href` and `action_key` only on warn/bad. Unchanged.
- The new `_property_overview.html` keeps every card, link and the readiness list; it only adds `data-health-check` / `data-state` on the checked cards, a dot, the problem sentence, and moves `data-setup-status` onto the "Checklist details" `<details>`.
- Tests that pinned the old box (`.host-checklist`, `.health-row`, the "Health check" title) are updated by the script in step 3.
- Lint on host2.css: no raw colours, no bare px except 0 and 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_property_overview.html | replace whole file | step 1 |
| App/app/static/host2.css | append | dot and problem styles |
| App/app/templates/base.html | edit | host2.css key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_property_health_0244.py, test_onboarding_followup_browser.py, test_design_guardrails_browser.py, test_onboarding_wizard_browser.py, test_property_form_nav.py | edit | step 3 script only |
| App/tests/test_0286_health_cards.py | new | step 4 |

No other file may change.

## 4. Steps

1. Replace the whole content of `App/app/templates/_property_overview.html` with exactly (the file starts with `{#- 0094/0102` and ends with `{% endif %}` and a newline):

```jinja
{#- 0094/0102: Overview tab — shortcut cards and setup progress. -#}
{%- from "_icons.html" import icon with context -%}
{%- from "_components.html" import copy_button, copy_inline, field_label, help_tip, source_badge, sync_calendars_button with context -%}
{%- set base_url = '/apartments/' ~ apartment.id -%}
{%- set operator = (entities | selectattr('id', 'equalto', apartment.legal_entity_id) | list | first) -%}
{%- set feed_errors_count = feeds | selectattr('last_status', 'equalto', 'error') | list | length -%}
{%- set report_missing = (readiness.report | rejectattr('done') | list | length) if readiness else 0 -%}
{%- set address_text = [((apartment.addr_street or '') ~ ' ' ~ (apartment.addr_house_no or '')) | trim, apartment.addr_obec or ''] | select | join(', ') -%}
{% if setup_progress and not setup_progress.hidden %}
<section class="panel setup-continue-card" aria-label="{{ t('wizard.continue_card_aria') }}">
  <p>{{ t('wizard.continue_card', done=setup_progress.done, total=setup_progress.total) }}
    {% if setup_progress.reporting_waiting %}<span class="ui-badge ui-badge-action" data-tone="amber">{{ t('setup_guide.reporting.waiting_item') }}</span>{% endif %}
  </p>
  <div class="actions">
    <a class="ui-btn ui-btn-primary" href="{{ setup_progress.continue_url }}">{{ t('wizard.continue') }}</a>
    <form method="post" action="/apartments/{{ apartment.id }}/setup" class="inline">
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <button class="ui-btn ui-btn-quiet" type="submit" name="action" value="hide" formnovalidate>{{ t('setup_guide.hide') }}</button>
    </form>
  </div>
</section>
{% elif setup_hidden %}
<form method="post" action="/apartments/{{ apartment.id }}/setup" class="property-setup-show">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <button class="link-button" type="submit" name="action" value="show">{{ t('setup_guide.show') }}</button>
</form>
{% endif %}
{#- 0286: the health check lives on these cards (owner 2026-10-22: one place,
    not a second box). A dot before the title says how each one is; a card
    with a problem names it and opens its fix. -#}
{%- set hc = {} -%}
{%- for row in health or [] %}{% set _ = hc.update({row.key: row}) %}{% endfor -%}
{%- macro hc_attrs(row) -%}{% if row %} data-health-check="{{ row.key }}" data-state="{{ row.state }}"{% endif %}{%- endmacro -%}
{%- macro hc_dot(row) -%}{% if row %}<span class="host-property-card-dot" data-state="{{ row.state }}">{% if row.state not in ('bad', 'warn') %}<span class="sr-only">{{ t(row.text_key) }}</span>{% endif %}</span>{% endif %}{%- endmacro -%}
{%- macro hc_href(row, href) -%}{{ row.href if row and row.state in ('bad', 'warn') and row.href else href }}{%- endmacro -%}
{%- macro hc_small(row, text) -%}{% if row and row.state in ('bad', 'warn') %}<small class="host-property-card-problem">{{ t(row.text_key) }}</small>{% elif text %}<small>{{ text }}</small>{% endif %}{%- endmacro -%}
{%- set h_cal, h_link, h_police, h_business, h_door = hc.get('calendar'), hc.get('guest_link'), hc.get('police'), hc.get('business'), hc.get('door') -%}
{%- set open_pill -%}<span class="host-property-card-open" aria-hidden="true"><span class="host-property-card-open-text">{{ t('common.open') }}</span>{{ icon('chevron-right', 16) }}</span>{%- endset -%}
<div class="host-property-grid">
  <a class="host-property-card" href="{{ hc_href(h_cal, base_url ~ '?view=bookings#calendars') }}"{{ hc_attrs(h_cal) }}>{{ icon('calendar-days', 20) }}<div><strong>{{ hc_dot(h_cal) }}{{ t('wizard.overview.calendars') }}</strong>
    {{ hc_small(h_cal, tp('apartment.form.calendars_count', feeds | length) ~ ((' · ' ~ t('apartment.form.feed.status.error')) if feed_errors_count else '')) }}</div>{{ open_pill }}</a>
  <div class="host-property-card host-property-card-static"{{ hc_attrs(h_link) }}>{{ icon('external-link', 20) }}<div><strong>{{ hc_dot(h_link) }}<a class="host-property-card-link" href="{{ base_url }}?view=settings&amp;section=guests#communication">{{ t('nav.guest_links') }}</a></strong>
    {{ hc_small(h_link, t('wizard.guest_link.ready')) }}</div>
    <div class="actions host-property-card-actions">{{ copy_inline('overview-guest-url', permalink, t('wizard.guest_link.copy_link')) }}</div>
    {{ open_pill }}</div>
  <a class="host-property-card" href="{{ hc_href(h_police, base_url ~ '?view=settings&section=reporting#ubyport') }}"{{ hc_attrs(h_police) }}>{{ icon('send', 20) }}<div><strong>{{ hc_dot(h_police) }}{{ t('host.reporting') }}</strong>
    {{ hc_small(h_police, t('property_nav.report_ready') if not report_missing else tp('property_nav.report_missing', report_missing)) }}</div>{{ open_pill }}</a>
  <a class="host-property-card" href="{{ hc_href(h_business, ('/entities?edit=' ~ apartment.legal_entity_id ~ '&next=' ~ (base_url | urlencode)) if operator else (base_url ~ '?view=settings&section=property#operator-picker')) }}"{{ hc_attrs(h_business) }}>{{ icon('receipt', 20) }}<div><strong>{{ hc_dot(h_business) }}{{ t('host.business') }}</strong>
    {{ hc_small(h_business, operator.name if operator else '') }}</div>{{ open_pill }}</a>
  <a class="host-property-card" href="{{ base_url }}?view=settings&amp;section=reporting#stay-fee-settings">{{ icon('coins', 20) }}<div><strong>{{ t('host.fee') }}</strong>
    <small>{{ apartment.stay_fee_rate_czk or 0 }} Kč / {{ t('stay_fees.nights.one', count=1) }}</small></div>{{ open_pill }}</a>
  <a class="host-property-card" href="{{ base_url }}?view=settings&amp;section=property#address">{{ icon('house', 20) }}<div><strong>{{ t('host.property_details') }}</strong>
    <small>{{ address_text or t('property_nav.address_missing') }}</small></div>{{ open_pill }}</a>
  {% if door_code %}
  <a class="host-property-card" href="{{ base_url }}?view=settings&amp;section=lock#door-code"{{ hc_attrs(h_door) }}>{{ icon('key-round', 20) }}<div><strong>{{ hc_dot(h_door) }}{{ t('host.door_code') }}</strong>
    <small>{{ t('property_nav.switch_enabled') if door_code.enabled else t('property_nav.switch_off') }}</small></div>{{ open_pill }}</a>
  {% endif %}
</div>

{%- set wizard_active = setup_progress and not setup_progress.hidden -%}
{% if readiness and not wizard_active %}
<details class="setup-readiness-help" data-setup-status>
    <summary><span aria-hidden="true">?</span> {{ t('wizard.overview.details') }}</summary>
    <section class="readiness">
  <div class="readiness-group">
    <h3 class="readiness-title">{{ t('apartment.form.readiness.invite_title') }}</h3>
    <ul class="readiness-list">
      {% for item in readiness.invite %}
      <li class="readiness-item{% if item.done %} is-done{% endif %}">
        <span class="readiness-mark" aria-hidden="true">{{ '✓' if item.done else '✗' }}</span>
        {% if item.done %}{{ t('apartment.form.readiness.item.' ~ item.key) }}
        {% else %}<a href="#{{ item.anchor }}">{{ t('apartment.form.readiness.missing') }} {{ t('apartment.form.readiness.item.' ~ item.key) }}</a>{% endif %}
      </li>
      {% endfor %}
    </ul>
    {% if readiness.invite_ready %}
    <p class="readiness-ready">{{ t('apartment.form.readiness.invite_ready') }}</p>
    {% if not setup_finished %}{{ copy_inline('readiness-permalink', permalink, t('apartment.form.readiness.copy_link')) }}{% endif %}
    {% endif %}
  </div>
  <div class="readiness-group">
    <h3 class="readiness-title">{{ t('apartment.form.readiness.report_title') }}</h3>
    <ul class="readiness-list">
      {% for item in readiness.report %}
      <li class="readiness-item{% if item.done %} is-done{% endif %}">
        <span class="readiness-mark" aria-hidden="true">{{ '✓' if item.done else '✗' }}</span>
        {% if item.done %}{{ t('apartment.form.readiness.item.' ~ item.key) }}
        {% else %}<a href="#{{ item.anchor }}">{{ t('apartment.form.readiness.missing') }} {{ t('apartment.form.readiness.item.' ~ item.key) }}</a>
          {% if item.message %}<span class="readiness-why">{{ validation_message(item.message) }}</span>{% endif %}
        {% endif %}
      </li>
      {% endfor %}
    </ul>
  </div>
</section>
</details>
{% endif %}
```

2. host2.css: append at the very end:

```css

/* 0286: the property health check lives on the Overview cards: a dot before the
   title says how each one is (green fine, amber to do, red broken, grey off);
   a card with a problem names it, opens its fix and carries a coloured edge. */
.host-workspace .host-property-card-dot { display: inline-block; width: var(--space-2); height: var(--space-2); margin-right: var(--space-2); border-radius: var(--radius-pill); background: var(--green-700); vertical-align: middle; }
.host-workspace .host-property-card-dot[data-state="warn"] { background: var(--amber); }
.host-workspace .host-property-card-dot[data-state="bad"] { background: var(--red); }
.host-workspace .host-property-card-dot[data-state="off"] { background: var(--ink-3); }
.host-workspace .host-property-card small.host-property-card-problem { color: var(--ink); }
.host-workspace .host-property-card[data-state="warn"] { border-left: var(--space-1) solid var(--amber); }
.host-workspace .host-property-card[data-state="bad"] { border-left: var(--space-1) solid var(--red); }
.host-workspace .host-property-grid + details.setup-readiness-help { margin-top: var(--space-3); }
```

3. Update the tests. Save this as `/tmp/claude-0/s/fix0286.py` and run it from `App/` with `.venv/bin/python /tmp/claude-0/s/fix0286.py 2>&1 | tail -5` (it stops on the first anchor it cannot find exactly once):

```python
from pathlib import Path

def swap(path, old, new, count=1):
    p = Path(path); text = p.read_text(encoding="utf-8")
    assert text.count(old) == count, (path, old[:60], text.count(old))
    p.write_text(text.replace(old, new), encoding="utf-8")

swap("tests/test_property_health_0244.py", "        assert title in page, lang\n",
     "        assert \"host-property-card-dot\" in page and title not in page, lang\n")

p = Path("tests/test_onboarding_followup_browser.py"); text = p.read_text(encoding="utf-8")
start = text.index('        status = page.locator("[data-setup-status]")\n')
end = text.index('        _fits(page)\n        _shot(page, f"40-overview-health')
assert text.count('        status = page.locator("[data-setup-status]")\n') == 1
p.write_text(text[:start] + """        status = page.locator("[data-setup-status]")
        assert status.is_visible()
        # 0286: the health check lives on the overview cards: a dot per checked card, no separate box.
        cards = page.locator(".host-property-grid [data-health-check]")
        assert cards.count() >= 4
        assert page.locator(".host-checklist, .health-row").count() == 0
        assert not status.evaluate("el => el.open")
        for index in range(cards.count()):
            card = cards.nth(index)
            assert card.locator(".host-property-card-dot").is_visible(), card.get_attribute("data-health-check")
            assert card.evaluate("el => getComputedStyle(el).borderTopStyle") == "solid"
            assert card.bounding_box()["height"] >= 43.5
        police = page.locator('.host-property-grid [data-health-check="police"]')
        assert police.count() == 1
        assert page.locator(".host-property-grid > a.host-property-card").count() >= 5
        status.locator("summary").click()
        assert status.locator(".readiness").is_visible()
        status.locator("summary").click()
""" + text[end:], encoding="utf-8")

p = Path("tests/test_design_guardrails_browser.py"); text = p.read_text(encoding="utf-8")
swap("tests/test_design_guardrails_browser.py",
     '    """0178: the setup checklist is a normal card (no tint, solid border, heading inside the padding)."""',
     '    """0286: the health check lives on the overview cards; no separate checklist box, details stay."""')
text = p.read_text(encoding="utf-8")
start = text.index("        facts = page.evaluate(\n            \"\"\"() => {\n                const box = document.querySelector('.host-workspace .host-checklist[data-setup-status]');")
end_anchor = '        assert facts["headGap"] is not None and facts["headGap"] >= 12, f"heading starts {facts[\'headGap\']}px from the left edge"\n'
end = text.index(end_anchor) + len(end_anchor)
p.write_text(text[:start] + """        facts = page.evaluate(
            \"\"\"() => ({
                box: !!document.querySelector('.host-checklist'),
                dots: document.querySelectorAll('.host-property-grid [data-health-check] .host-property-card-dot').length,
                details: !!document.querySelector('.host-workspace details.setup-readiness-help[data-setup-status]'),
            })\"\"\"
        )
        print(f"setup health measured: {facts}")
        assert not facts["box"], "the separate health check box is back"
        assert facts["dots"] >= 4, f"only {facts['dots']} cards carry a health dot"
        assert facts["details"], "the checklist details are missing"
""" + text[end:], encoding="utf-8")

swap("tests/test_onboarding_wizard_browser.py", "'class=\"panel host-checklist\"'", "'data-setup-status'", count=4)
swap("tests/test_onboarding_wizard_browser.py", 'page.locator(".host-checklist")', 'page.locator("[data-setup-status]")')
swap("tests/test_property_form_nav.py", "'<section class=\"panel host-checklist\"'", "'<details class=\"setup-readiness-help\"'")
print("ok")
```

4. Create `App/tests/test_0286_health_cards.py` with exactly:

```python
"""0286: the property health check lives on the Overview cards."""
from __future__ import annotations

import re
import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as


def _client():
    db.init_db()
    user = f"hc-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Health Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flat = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))["id"]
    return client, flat


def _card(page, key):
    match = re.search(r'<(?:a|div) class="host-property-card[^"]*"[^>]*data-health-check="' + key + r'"[^>]*>.*?</(?:a|div)>', page, re.S)
    assert match, key
    return match.group(0)


def test_cards_carry_the_health_and_the_box_is_gone():
    client, flat = _client()
    for lang in ("en", "cs", "vi"):
        page = client.get(f"/apartments/{flat}?view=overview&lang={lang}").text
        assert 'class="panel host-checklist"' not in page and 'class="health-row"' not in page, lang
        for key in ("calendar", "guest_link", "police", "business"):
            assert "host-property-card-dot" in _card(page, key), (lang, key)


def test_a_problem_card_names_the_problem_and_opens_the_fix():
    client, flat = _client()
    db.execute("UPDATE ical_feed SET active = 0 WHERE apartment_id = ?", (flat,))
    page = client.get(f"/apartments/{flat}?view=overview&lang=en").text
    card = _card(page, "calendar")
    assert 'data-state="warn"' in card
    assert "host-property-card-problem" in card and "No calendar connected" in card
    assert f'href="/apartments/{flat}?view=bookings#calendars"' in card
```

5. Cache key, from the repo root:

```
sed -i 's/host2.css?v=20261022-0285"/host2.css?v=20261022-0286"/' App/app/templates/base.html
grep -c 'host2.css?v=20261022-0286"' App/app/templates/base.html
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5
```

Commit after each step: `0286 step k`.

## 5. Do not touch

Everything not in section 3; `property_health.py` and the i18n files stay as they are. AGENTS.md hard rules 6 and 7.

## 6. Commands (from `App/`, with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`)

```
.venv/bin/python -m pytest tests/test_0286_health_cards.py tests/test_property_health_0244.py tests/test_property_form_nav.py tests/test_static_versions.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k setup_checklist tests/test_onboarding_followup_browser.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5
```

Expected: all pass, 0 skipped; lint clean. If `db.execute` does not exist in `app/db.py`, use the helper that file offers for an UPDATE (grep `^def ` in it) and note it under Deviations.

## 7. Acceptance

- [ ] test_0286 passes in EN/CS/VI; the updated tests pass, 0 skipped.
- [ ] No "Health check" box on the Overview; dots on the checked cards; "Checklist details" still opens.
- [ ] host2.css key `20261022-0286`; static_versions.json regenerated; design lint clean.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8.

## 9. Report

`docs/tasks/0286-report.md` (600 tokens at most), set `Status: review`. Do not push.
