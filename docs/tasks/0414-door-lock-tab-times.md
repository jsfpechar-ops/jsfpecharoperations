# 0414: Check-in/out times on the property's Door lock tab

Status: todo
Branch: claude/project-thread-qi1fv7 (already checked out from main; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-26): a host sets up TTLock for a second property on the Door lock tab (Settings, not the wizard). The property has no check-in/out times. The tab only shows "Check-in time — · Check-out time —" and a link to another tab, so the host gets stuck. The wizard's lock step already has the two time pickers; the Door lock tab must have them too, and they are required whenever automatic door codes are on.

After this brief:
1. The Door lock tab shows "Check-in time" and "Check-out time" selects inside `#door-code`, above the switch. They show the saved times.
2. They are `required` while the "Automatic door codes" switch is on (server-rendered, and toggled live by JS when the switch changes). The red `*` comes from existing CSS.
3. Saving from the Door lock tab stores the times picked there. With times picked and the switch on, codes turn on in one save.
4. The text line "Check-in time — · Check-out time —. Edit in Properties" and the amber "times missing" warning go away (the pickers show it). The red alert on a refused save (0397) stays.
5. The Property tab's own time selects keep working. The two pairs stay in sync with JS; without JS, the server takes the Door lock tab's value when it differs from the saved one.

No new string. One JS change, so `host.js?v=` is bumped.

## 2. Context

- The property editor is ONE form; every tab is posted. The Property tab already posts `checkin_hour` / `checkout_hour`. The new selects therefore use the names `lock_checkin_hour` / `lock_checkout_hour` (ids the same) so nothing is posted twice.
- `_save_apartment_form(apartment_id, request, form)` in `App/app/routes/admin.py` reads the hours through `_property_hour_changes(form, ...)` and `name in form`. Step 1 folds the lock-tab values into `checkin_hour` / `checkout_hour` once at the top, so the rest of the function is unchanged.
- `starlette.datastructures.FormData` accepts a list of `(key, value)` tuples; `form.multi_items()` lists the posted pairs.

## 3. Files

| Path | Action |
|---|---|
| App/app/routes/admin.py | `_with_lock_tab_hours` helper, called at the top of `_save_apartment_form` |
| App/app/templates/_property_editor.html | the two selects; drop the text line and the amber warning |
| App/app/static/host.js | sync pairs, `required` follows the switch, window preview listens to both |
| App/app/templates/base.html | bump `host.js?v=` |
| App/tests/test_door_lock_tab_times_0414.py | new tests |
| App/tests/test_door_code_missing_times_0397.py | adjust only if an assertion depended on the removed lines |

## 4. Steps

### Step 1: the server folds the Door lock tab's times in

In `App/app/routes/admin.py`, change the import line `from starlette.datastructures import UploadFile` to `from starlette.datastructures import FormData, UploadFile`.

Directly ABOVE `def _save_apartment_form(` insert:

```python
def _with_lock_tab_hours(form, apartment) -> Any:
    """0414: the Door lock tab posts its own time pickers (lock_checkin_hour,
    lock_checkout_hour) in the same form as the Property tab's. A value the
    host changed there wins; otherwise the Property tab's value stands."""
    overrides: Dict[str, str] = {}
    for name in ("checkin_hour", "checkout_hour"):
        lock_name = f"lock_{name}"
        if lock_name not in form:
            continue
        lock_value = _form_str(form, lock_name)
        saved = "" if apartment[name] is None else str(apartment[name])
        if name not in form or lock_value != saved:
            overrides[name] = lock_value
    if not overrides:
        return form
    items = [(key, value) for key, value in form.multi_items() if key not in overrides]
    items.extend(overrides.items())
    return FormData(items)


```

In `_save_apartment_form`, directly AFTER these two lines:

```python
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment")), False
```

(the first occurrence inside `_save_apartment_form`) insert:

```python
    form = _with_lock_tab_hours(form, apartment)
```

Commit `0414 step 1`.

### Step 2: the template

In `App/app/templates/_property_editor.html`, inside `<section class="panel property-section ui-section" id="door-code">`:

a. Replace these lines exactly (from `<p class="ui-sub">{{ t('why.times') }}` through the `{% elif ... warn-text ... %}` line):

```jinja
      <p class="ui-sub">{{ t('why.times') }}
          {{ t('apartment.form.door_code.checkin') }} {{ '%02d:00' | format(apartment.checkin_hour) if apartment.checkin_hour is not none else '—' }} ·
          {{ t('apartment.form.door_code.checkout') }} {{ '%02d:00' | format(apartment.checkout_hour) if apartment.checkout_hour is not none else '—' }}.
          <a href="/apartments/{{ apartment.id }}?view=settings&amp;section=property#arrival-departure">{{ t('host.property_times_edit') }}</a>
        </p>
      {% if lock_times_error %}<p class="err-text" id="door-code-times-error" role="alert">{{ t('why.times_missing') }}</p>
      {% elif apartment.checkin_hour is none or apartment.checkout_hour is none %}<p class="small warn-text">{{ t('why.times_missing') }}</p>{% endif %}
```

with:

```jinja
      <p class="ui-sub">{{ t('why.times') }}</p>
      {% if lock_times_error %}<p class="err-text" id="door-code-times-error" role="alert">{{ t('why.times_missing') }}</p>{% endif %}
      {% set switch_on = door_switch_posted if door_switch_posted is defined else door_code.enabled %}
      {#- 0414: the times live here too, so a host turning on door codes never leaves the tab. -#}
      <div class="grid two" data-lock-times>
        {% for name, label in [('checkin_hour', 'apartment.form.door_code.checkin'), ('checkout_hour', 'apartment.form.door_code.checkout')] %}
        <div class="field"><label for="lock_{{ name }}">{{ t(label) }}</label>
          <select id="lock_{{ name }}" name="lock_{{ name }}" data-hour-twin="{{ name }}"{% if switch_on %} required{% endif %}{% if lock_times_error %} aria-invalid="true" aria-describedby="door-code-times-error"{% endif %}><option value="">{{ t('apartment.form.door_code.choose') }}</option>
            {% for h in range(24) %}<option value="{{ h }}" {% if apartment[name]|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
          </select></div>
        {% endfor %}
      </div>
```

b. Delete the now-duplicate line further down (it is the one directly above `<div class="feature-switch-row">`):

```jinja
        {% set switch_on = door_switch_posted if door_switch_posted is defined else door_code.enabled %}
```

c. In the Property tab's `#arrival-departure` select line, add a twin marker. Replace exactly:

```jinja
          <select id="{{ name }}" name="{{ name }}"><option value="">{{ t('apartment.form.door_code.choose') }}</option>
```

with:

```jinja
          <select id="{{ name }}" name="{{ name }}" data-hour-twin="{{ name }}"><option value="">{{ t('apartment.form.door_code.choose') }}</option>
```

(Check with `grep -nF` that this exact line occurs once in `_property_editor.html`; if not, STOP.)

Commit `0414 step 2`.

### Step 3: JS

In `App/app/static/host.js`, replace exactly:

```js
  document.addEventListener('change', function (event) {
    if (event.target.matches('select[name="checkin_hour"], select[name="checkout_hour"]')) updateDoorCodeWindows();
  });
  updateDoorCodeWindows();
```

with:

```js
  document.addEventListener('change', function (event) {
    // 0414: the Property tab and the Door lock tab each show the two times; keep them equal.
    var twin = event.target.getAttribute && event.target.getAttribute('data-hour-twin');
    if (twin) {
      document.querySelectorAll('select[data-hour-twin="' + twin + '"]').forEach(function (other) {
        if (other !== event.target) other.value = event.target.value;
      });
    }
    if (twin || event.target.matches('select[name="checkin_hour"], select[name="checkout_hour"]')) updateDoorCodeWindows();
    // 0414: door codes need both times, so the Door lock tab's pickers are required while the switch is on.
    if (event.target.id === 'door_codes') {
      document.querySelectorAll('[data-lock-times] select').forEach(function (select) {
        select.required = event.target.checked;
      });
    }
  });
  updateDoorCodeWindows();
```

In `App/app/templates/base.html` replace `host.js?v=20261023-door-code-window` with `host.js?v=20261026-door-lock-times`.

Commit `0414 step 3`.

### Step 4: tests

Create `App/tests/test_door_lock_tab_times_0414.py`:

```python
"""0414: the Door lock tab has its own check-in/out pickers."""
from __future__ import annotations

import re

from app import db
from tests.test_door_code_one_lock_one_property import (  # noqa: F401  (fixture)
    LOCK,
    _apartment,
    _client,
    two_properties,
)


def _base(apartment_id, entity):
    return {
        "internal_name": _apartment(apartment_id)["internal_name"],
        "legal_entity_id": str(entity),
        "return_to": f"/apartments/{apartment_id}?view=settings&section=lock",
        "door_code_section": "1",
        "door_codes_fields": "1",
        "lock_id": LOCK["lock_id"],
        "checkin_hour": "",
        "checkout_hour": "",
    }


def test_lock_tab_shows_the_time_pickers(two_properties):
    _, _, (a, _) = two_properties
    page = _client().get(f"/apartments/{a}?view=settings&section=lock").text
    for name in ("lock_checkin_hour", "lock_checkout_hour"):
        assert re.search(rf'<select id="{name}" name="{name}"', page)
    assert "Edit in Properties" not in page


def test_times_picked_on_the_lock_tab_turn_codes_on_in_one_save(two_properties):
    _, entity, (a, _) = two_properties
    data = _base(a, entity)
    data.update({"door_codes": "1", "lock_checkin_hour": "15", "lock_checkout_hour": "10"})
    response = _client().post(f"/apartments/{a}", data=data, follow_redirects=False)
    assert response.status_code == 303
    row = _apartment(a)
    assert (row["checkin_hour"], row["checkout_hour"], row["lock_provider"]) == (15, 10, "ttlock")


def test_pickers_are_required_while_codes_are_on(two_properties):
    _, entity, (a, _) = two_properties
    db.update("apartment", a, {"checkin_hour": 15, "checkout_hour": 10, "lock_provider": "ttlock", "lock_id": LOCK["lock_id"]})
    page = _client().get(f"/apartments/{a}?view=settings&section=lock").text
    select = re.search(r'<select id="lock_checkin_hour"[^>]*>', page).group(0)
    assert "required" in select
    assert re.search(r'<select id="lock_checkin_hour".*?<option value="15" selected', page, re.S)


def test_missing_times_on_the_lock_tab_are_refused_inline(two_properties):
    _, entity, (a, _) = two_properties
    data = _base(a, entity)
    data.update({"door_codes": "1", "lock_checkin_hour": "", "lock_checkout_hour": ""})
    response = _client().post(
        f"/apartments/{a}", data=data, follow_redirects=False, headers={"accept": "text/html"}
    )
    assert response.status_code == 400
    assert 'id="door-code-times-error" role="alert"' in response.text
    assert _apartment(a)["lock_provider"] is None


def test_property_tab_change_still_wins_when_lock_tab_is_untouched(two_properties):
    _, entity, (a, _) = two_properties
    db.update("apartment", a, {"checkin_hour": 14, "checkout_hour": 10})
    data = _base(a, entity)
    data.update({"checkin_hour": "16", "checkout_hour": "10", "lock_checkin_hour": "14", "lock_checkout_hour": "10"})
    data["return_to"] = f"/apartments/{a}?view=settings&section=property"
    assert _client().post(f"/apartments/{a}", data=data, follow_redirects=False).status_code == 303
    assert _apartment(a)["checkin_hour"] == 16
```

Run §6 command 1. If a test in `test_door_code_missing_times_0397.py` fails ONLY because it looked for the removed "Edit in Properties" line or the amber warning, update that single assertion and note it under Deviations. Any other failure: fix once, rerun, else STOP.

Commit `0414 step 4`.

## 5. Do not touch

The wizard (`setup_wizard/door_lock.html`), `_lock_section_refusal`, i18n files, CSS.

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_door_lock_tab_times_0414.py tests/test_door_code_missing_times_0397.py tests/test_door_code_one_lock_one_property.py tests/test_wizard_second_lock_0400.py tests/test_ttlock.py tests/test_property_form_save.py tests/test_property_form_nav.py tests/test_door_code_window.py -q --tb=short 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -5
```

Browser tests run in CI (Playwright is not installed in this container); do not install it.

## 7. Acceptance

- [ ] §6 command 1 passes; lint OK.
- [ ] One commit per step.

## 8. Stop and ask

An anchor is not found, or a test fails twice: stop, write the report with `Status: blocked`. Screenshots are taken by the reviewer. Do not push.

## 9. Report

`docs/tasks/0414-report.md`.
