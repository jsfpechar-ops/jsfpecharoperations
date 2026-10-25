# 0391: The wizard's lock step can add a second lock

Status: todo
Branch: claude/project-thread-rmxe40 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): a host with one property and one TTLock lock runs the setup wizard for a second property. Their new lock is not yet shared with UbyHost in the TTLock app. The wizard's lock step (`/apartments/<id>/setup/door_lock`) shows only a dropdown holding the first property's lock, with no way to add the new one, so they get lost. Saving the taken lock is refused and the times they chose are wiped. "They should be able to do it all in there."

After this brief:
1. **No free lock** (every connected lock already serves another property): the step does not show the dropdown. It shows one sentence on why, the taken locks with "in use by <property>", and the TTLock sharing steps (UbyHost name + copy, 3 steps, **Check connection** as the primary button). "No smart lock" stays as the secondary action.
2. **A free lock exists:** the dropdown shows as now, but a lock used by another property is disabled and labelled "in use by <property>" (same as the property's Door lock tab), and an "Add another lock" fold-out with the same sharing steps sits under the form.
3. A refused lock save on this step stays on this step and keeps the times and the switch the host chose. It never jumps to step 1.
4. The sharing steps live in ONE macro used by the Door lock tab and the wizard.

## 2. Context

- `App/app/templates/_smart_locks_panel.html` defines `share_block(code_id, section)` inline. It reads `receiver` and `return_to` from `{% with %}` scope.
- `POST /smart-locks/refresh` with `return_to=/apartments/<id>/setup/door_lock` already lands back on the wizard step (`_lock_property_return`), and with `#smart-locks-share` / `#smart-locks-add-more` anchors on "none found" or errors. Do not change the route.
- The wizard context already has `lock_panel` (receiver, return_to = the wizard URL) and `door_code` (from `_door_code_context`, each lock has `used_by`, a comma-joined string of OTHER properties using it).
- Copy rule: wizard steps say why, in plain words. Every new string in en, cs and vi.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_smart_lock_share.html | new: the shared macro |
| App/app/templates/_smart_locks_panel.html | use the macro |
| App/app/templates/setup_wizard/door_lock.html | new branches, disabled options, draft values |
| App/app/routes/admin.py | `free_lock_count`; refusals stay on the lock step |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | 1 new key |
| App/tests/test_wizard_second_lock_0391.py | new tests |

## 4. Steps

### Step 1: the shared macro

Create `App/app/templates/_smart_lock_share.html` with exactly:

```jinja
{% from "_components.html" import help_tip, copy_button with context %}
{#- 0391: the TTLock sharing steps. One copy for the Door lock tab and the setup wizard. -#}
{% macro share_block(code_id, section, receiver, return_to, primary) %}
  <h2>{{ t('smart_locks.share_title') }}</h2>
  <p class="ui-sub">{{ t('smart_locks.warn_owner') }}</p>
  <p><strong>{{ t('smart_locks.name_label') }}</strong></p>
  <p><code id="{{ code_id }}">{{ receiver }}</code> {{ copy_button(code_id) }}</p>
  {# 0090: three essentials here; every TTLock tap lives in the Guide. #}
  <h3 class="smart-locks-steps-title">{{ t('smart_locks.steps_title') }}
    {{ help_tip('smart-locks-steps-help-' ~ section, t('smart_locks.steps_help'), '/guide#door-codes-share') }}</h3>
  <ol class="guide-steps">{% for n in range(1, 4) %}<li>{{ t('smart_locks.essential' ~ n) }}</li>{% endfor %}</ol>
  <p class="ui-sub"><strong>{{ t('smart_locks.warn_ekey') }}</strong></p>
  <form method="post" action="/smart-locks/refresh"><input type="hidden" name="return_to" value="{{ return_to }}">
    <input type="hidden" name="section" value="{{ section }}">
    <div class="action-group"><button class="{{ 'ui-btn ui-btn-primary' if primary else 'ui-btn ui-btn-secondary' }}" type="submit">{{ t('smart_locks.check') }}</button></div></form>
{% endmacro %}
```

Commit `0391 step 1`.

### Step 2: the panel uses the macro

In `App/app/templates/_smart_locks_panel.html`:

a. Delete the whole block from the line `{% macro share_block(code_id, section) %}` through its `{% endmacro %}` line (inclusive), and put this single line in its place:

```jinja
{% from "_smart_lock_share.html" import share_block with context %}
```

b. Replace `{{ share_block('ttlock-receiver', 'share') }}` with `{{ share_block('ttlock-receiver', 'share', receiver, return_to, true) }}`.

c. Replace `{{ share_block('ttlock-receiver-more', 'add-more') }}` with `{{ share_block('ttlock-receiver-more', 'add-more', receiver, return_to, false) }}`.

Run: `cd App && .venv/bin/python -m pytest tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30`. Commit `0391 step 2`.

### Step 3: `free_lock_count` in the lock context

In `App/app/routes/admin.py`, function `_door_code_context`, find the line
`        "default_lock_id": free_locks[0]["lock_id"] if len(free_locks) == 1 else "",`
and add directly under it:

```python
        # 0391: 0 means every connected lock serves another property.
        "free_lock_count": len(free_locks),
```

Commit `0391 step 3`.

### Step 4: refused lock saves stay on the lock step

In `App/app/routes/admin.py`:

a. In `_lock_section_refusal`, replace

```python
        return _wizard_rerender(
            request,
            apartment_id,
            "door_lock",
            notice=_flash(request, error_key),
            status_code=400,
        ), False
```

with

```python
        # 0391: keep what the host chose, so a refusal never wipes the step.
        lock_draft = {
            "checkin_hour": _form_str(form, "checkin_hour"),
            "checkout_hour": _form_str(form, "checkout_hour"),
            "enabled": _form_str(form, "door_codes") == "1",
        }
        return _wizard_rerender(
            request,
            apartment_id,
            "door_lock",
            notice=_flash(request, error_key),
            status_code=400,
            extra={"lock_draft": lock_draft},
        ), False
```

b. In `_save_apartment_form`, find

```python
    if hour_error:
        if setup_step:
```

and replace with

```python
    if hour_error:
        if setup_step == "door_lock":
            return _lock_section_refusal(request, apartment_id, form, hour_error)
        if setup_step:
```

c. In the same function, find

```python
        if not valid_pair:
            if setup_step:
```

and replace with

```python
        if not valid_pair:
            if setup_step == "door_lock":
                return _lock_section_refusal(request, apartment_id, form, "flash.error.door_code_hours")
            if setup_step:
```

Commit `0391 step 4`.

### Step 5: the new string

In `App/app/host_i18n.py`, under the line `        "wizard.door_lock.other_brands": "Other brands are not supported yet.",` add:

```python
        "wizard.door_lock.all_taken": "Your connected lock already opens another property, and one lock serves one property. First add this property's lock to UbyHost in the TTLock app:",
```

Under `        "wizard.door_lock.other_brands": "Jiné značky zatím nepodporujeme.",` add:

```python
        "wizard.door_lock.all_taken": "Váš připojený zámek už otevírá jiné ubytování a jeden zámek slouží jen jednomu ubytování. Nejdřív v aplikaci TTLock přidejte UbyHost k zámku tohoto ubytování:",
```

In `App/app/host_vi_i18n.py`, under `    "wizard.door_lock.other_brands": "Hiện chưa hỗ trợ các hãng khác.",` add:

```python
    "wizard.door_lock.all_taken": "Khóa bạn đã kết nối đang mở một chỗ ở khác, và mỗi khóa chỉ dùng cho một chỗ ở. Trước tiên, hãy thêm UbyHost vào khóa của chỗ ở này trong ứng dụng TTLock:",
```

Commit `0391 step 5`.

### Step 6: the wizard template

In `App/app/templates/setup_wizard/door_lock.html`:

a. Replace the line `{% from "_components.html" import field_label, help_tip with context %}` with:

```jinja
{% from "_components.html" import field_label, help_tip with context %}
{% from "_smart_lock_share.html" import share_block with context %}
```

b. Replace the line `{% if door_code and door_code.account and door_code.locks %}` that comes right after the `_door_code_window.html` include (the FIRST one, inside `wizard_content`) with:

```jinja
{% if door_code and door_code.account and door_code.locks and door_code.free_lock_count %}
```

c. Replace

```jinja
        {% for h in range(24) %}<option value="{{ h }}" {% if apartment[name]|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
```

with

```jinja
        {% for h in range(24) %}<option value="{{ h }}" {% if (lock_draft if lock_draft is defined else apartment)[name]|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
```

d. Replace `<input type="checkbox" role="switch" id="door_codes" name="door_codes" value="1" {% if door_code.enabled %}checked{% endif %}>` with

```jinja
<input type="checkbox" role="switch" id="door_codes" name="door_codes" value="1" {% if (lock_draft.enabled if lock_draft is defined else door_code.enabled) %}checked{% endif %}>
```

e. Replace

```jinja
      {% for lock in door_code.locks %}<option value="{{ lock.lock_id }}" {% if lock.lock_id == door_code.lock_id or (not door_code.lock_id and lock.lock_id == door_code.default_lock_id) %}selected{% endif %}>{{ lock.alias }}</option>{% endfor %}
```

with

```jinja
      {% for lock in door_code.locks %}<option value="{{ lock.lock_id }}" {% if lock.used_by and lock.lock_id != door_code.lock_id %}disabled{% endif %} {% if lock.lock_id == door_code.lock_id or (not door_code.lock_id and lock.lock_id == door_code.default_lock_id) %}selected{% endif %}>{{ lock.alias }}{% if lock.used_by %} · {{ t('apartment.form.door_code.in_use', property=lock.used_by) }}{% endif %}</option>{% endfor %}
```

f. Replace the two lines

```jinja
</form>
{% elif door_code %}
```

(the first `</form>` followed by `{% elif door_code %}`) with:

```jinja
</form>
{% if lock_panel and lock_panel.smart_locks_enabled %}
{#- 0391: a second lock is added here, without leaving the wizard. -#}
<details class="ui-section setup-wizard-lock-panel" id="smart-locks-add-more">
  <summary>{{ t('smart_locks.add_more') }}</summary>
  {{ share_block('ttlock-receiver-more', 'add-more', lock_panel.receiver, lock_panel.return_to, false) }}
</details>
{% endif %}
{% elif door_code and door_code.account and door_code.locks %}
{#- 0391: every connected lock already serves another property: add this property's lock first. -#}
<section class="ui-section setup-wizard-lock-panel" id="smart-locks-share">
  <p class="setup-wizard-instruction">{{ t('wizard.door_lock.all_taken') }}</p>
  <ul class="setup-wizard-taken-locks">{% for lock in door_code.locks %}<li>{{ lock.alias }} · {{ t('apartment.form.door_code.in_use', property=lock.used_by) }}</li>{% endfor %}</ul>
  {% if lock_panel and lock_panel.smart_locks_enabled %}
  {{ share_block('ttlock-receiver', 'share', lock_panel.receiver, lock_panel.return_to, true) }}
  {% endif %}
</section>
{% elif door_code %}
```

g. In `{% block wizard_actions %}`, replace

```jinja
{% if door_code and door_code.account and door_code.locks %}
<form method="post" action="/apartments/{{ apartment.id }}/setup" class="inline setup-wizard-skip">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="step" value="door_lock">
  <button class="ui-btn ui-btn-secondary" type="submit" name="action" value="none" formnovalidate>{{ t('wizard.door_lock.no') }}</button>
</form>
<button class="{{ cta }}" type="submit" form="door-lock-form">{{ t('wizard.save_continue') }}</button>
```

with

```jinja
{% if door_code and door_code.account and door_code.locks %}
<form method="post" action="/apartments/{{ apartment.id }}/setup" class="inline setup-wizard-skip">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="step" value="door_lock">
  <button class="ui-btn ui-btn-secondary" type="submit" name="action" value="none" formnovalidate>{{ t('wizard.door_lock.no') }}</button>
</form>
{% if door_code.free_lock_count %}<button class="{{ cta }}" type="submit" form="door-lock-form">{{ t('wizard.save_continue') }}</button>{% endif %}
```

Commit `0391 step 6`.

### Step 7: tests

Create `App/tests/test_wizard_second_lock_0391.py` with exactly:

```python
"""0391: a second property's lock is added inside the setup wizard."""
from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, property_setup
from app.main import app
from tests.conftest import login_as

USERNAME = "secondlock-host"
LOCK_A = {"lock_id": "35874326", "alias": "Vivus A2.6", "battery": 100, "tz_offset_ms": 3600000}
LOCK_B = {"lock_id": "35874327", "alias": "Garden door", "battery": 90, "tz_offset_ms": 3600000}


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    _cleanup()
    owner = auth.create_account(f"{USERNAME}@example.test", "Second Lock", username=USERNAME)
    now = db.utcnow()
    entity = db.insert(
        "legal_entity", {"name": "Second Lock", "seat": "Praha", "created_at": now, "owner_user_id": owner}
    )
    ids = []
    for n, name in enumerate(("Flat A", "Flat B")):
        ids.append(db.insert("apartment", {
            "legal_entity_id": entity, "owner_user_id": owner, "internal_name": name,
            "permalink_token": f"secondlock-tok-{n}", "permalink_pin": "123456",
            "automation_mode": "manual", "default_purpose": "10", "active": 1, "created_at": now,
            "addr_obec": "Praha", "addr_house_no": "1", "addr_zip": "11000",
            "lock_provider": "ttlock" if n == 0 else None,
            "lock_id": LOCK_A["lock_id"] if n == 0 else None,
            "checkin_hour": 15 if n == 0 else None, "checkout_hour": 10 if n == 0 else None,
        }))
    db.insert("lock_account", {
        "owner_user_id": owner, "provider": "ttlock", "username": "x_secondlock",
        "status": "ok", "locks_json": json.dumps([LOCK_A]), "created_at": now, "updated_at": now,
    })
    second = ids[1]
    property_setup.start(second)
    for step, mark in (("property", "done"), ("calendar", "skipped"), ("police", "waiting"),
                       ("automation", "done"), ("stay_fee", "skipped")):
        property_setup.mark(second, step, mark)
    yield owner, entity, ids[0], second
    _cleanup()


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        oid = row["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{apt['id']}",))
            db.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _client() -> TestClient:
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    return client


def _step(client, apartment_id):
    response = client.get(f"/apartments/{apartment_id}/setup/door_lock")
    assert response.status_code == 200
    return response.text


def _add_lock_b(owner):
    db.execute(
        "UPDATE lock_account SET locks_json = ? WHERE owner_user_id = ?",
        (json.dumps([LOCK_A, LOCK_B]), owner),
    )


def test_no_free_lock_shows_the_sharing_steps_not_a_dead_dropdown(world):
    _, _, _, second = world
    page = _step(_client(), second)
    assert 'id="door-lock-form"' not in page
    assert 'id="smart-locks-share"' in page
    assert "x_secondlock" in page  # the UbyHost name to paste in TTLock
    assert 'action="/smart-locks/refresh"' in page
    assert f'value="/apartments/{second}/setup/door_lock"' in page
    assert "one lock serves one property" in page
    assert "Vivus A2.6 · in use by Flat A" in page
    assert "No smart lock" in page


def test_a_free_lock_is_offered_and_the_taken_one_is_disabled(world):
    owner, _, _, second = world
    _add_lock_b(owner)
    page = _step(_client(), second)
    assert 'id="door-lock-form"' in page
    taken = re.search(r'<option value="35874326"[^>]*>[^<]*', page).group(0)
    assert "disabled" in taken and "in use by Flat A" in taken
    free = re.search(r'<option value="35874327"[^>]*>', page).group(0)
    assert "selected" in free and "disabled" not in free
    assert 'id="smart-locks-add-more"' in page
    assert "x_secondlock" in page


def test_the_first_property_keeps_its_own_lock_selectable(world):
    _, _, first, _ = world
    page = _client().get(f"/apartments/{first}/setup/door_lock").text
    option = re.search(r'<option value="35874326"[^>]*>', page)
    if option:  # the first property may have finished its wizard already
        assert "disabled" not in option.group(0)


def test_a_refused_lock_save_stays_on_the_step_and_keeps_the_times(world):
    owner, entity, _, second = world
    _add_lock_b(owner)
    response = _client().post(f"/apartments/{second}", data={
        "return_to": f"/apartments/{second}/setup/guest_link",
        "setup_step": "door_lock", "door_code_section": "1", "door_codes_fields": "1",
        "internal_name": "Flat B", "legal_entity_id": str(entity), "default_purpose": "10",
        "checkin_hour": "14", "checkout_hour": "11", "door_codes": "1",
        "lock_id": LOCK_A["lock_id"],
    }, follow_redirects=False)
    assert response.status_code == 400
    page = response.text
    assert "already sends codes for another property" in page
    assert 'id="door-lock-form"' in page
    assert re.search(r'<select id="checkin_hour"[\s\S]*?<option value="14" selected>', page)
    assert re.search(r'<select id="checkout_hour"[\s\S]*?<option value="11" selected>', page)
    assert re.search(r'id="door_codes"[^>]*checked', page)
    assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (second,))["lock_provider"] is None


def test_the_door_lock_tab_still_shows_its_sharing_steps(world):
    _, _, _, second = world
    page = _client().get(f"/apartments/{second}?view=settings&section=lock").text
    assert 'id="smart-locks-add-more"' in page
    assert "x_secondlock" in page
```

Run: `cd App && .venv/bin/python -m pytest tests/test_wizard_second_lock_0391.py -q --tb=short -x 2>&1 | tail -30`. Commit `0391 step 7`.

## 5. Out of scope

Do not change routes other than the three edits in step 4, CSS, the guide, or any other wizard step.

## 6. Tests

```
cd App && .venv/bin/python -m pytest tests/test_wizard_second_lock_0391.py tests/test_smart_locks_page.py tests/test_door_code_one_lock_one_property.py tests/test_lock_question_0234.py tests/test_onboarding_wizard_survival.py -q --tb=short 2>&1 | tail -30
cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome .venv/bin/python -m pytest tests/test_lock_navigation_browser.py tests/test_onboarding_wizard_browser.py tests/test_door_code_window_browser.py -q -rs --tb=short 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -30
```

## 7. Done when

- [ ] All commands in §6 pass, 0 skipped.
- [ ] One commit per step.

## 8. Stop and report

An anchor is not found, or a test fails twice: stop, write the report with `Status: blocked`. Screenshots are taken by the reviewer; do not take them. Do not push.
