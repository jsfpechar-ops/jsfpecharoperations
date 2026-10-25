# 0397: Turning on door codes without check-in/out times crashes the save

Status: review
Branch: claude/project-thread-qi1fv7 (already checked out, built on PR #515; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): on a property with no check-in or check-out time, he switched on "Automatic door codes" on the Door lock tab, chose a lock and pressed Save. He landed on the generic "Something went wrong" page (500).

Root cause (reproduced): the save refuses correctly (door codes need both times) and calls `_refuse_apartment_save`, which copies the posted hours into the draft as raw text (`""`). `_door_code_context` then passes them to `_door_code_hours_overlap`, which does `"" - ""` and raises `TypeError`. Any refused property save that posts a blank hour crashes the same way.

After this brief:
1. A refused save never crashes: posted hours reach the page as an int or `None`.
2. Refused from the Door lock tab: the page stays on the Door lock tab, shows the existing "times missing" sentence as an error (`role="alert"`), the switch stays on as the host left it (status "Not saved yet"), and the chosen lock stays selected. Nothing is saved.
3. Refused from the Property tab: unchanged (Property tab, existing time error), just no crash.

No new string: the error reuses `why.times_missing` ("…Set them first."). No CSS/JS change, no `?v=` bump.

## 2. Context

- The property editor is one form; every tab's fields are posted. The hidden `return_to` holds `...?view=settings&section=<tab>` (JS updates it on tab switch; without JS each tab is a real link, so it is right too).
- `_render_apartment_detail(..., extra=...)` passes `extra` keys to the template; `settings_section` picks the visible tab.

## 3. Files

| Path | Action |
|---|---|
| App/app/routes/admin.py | helper, refusal coercion, lock-tab refusal |
| App/app/templates/_property_editor.html | error line, switch keeps posted state |
| App/tests/test_door_code_missing_times_0397.py | new tests |

## 4. Steps

### Step 1: hours become int or None in the refusal

In `App/app/routes/admin.py`, find `def _door_code_hours_overlap(` and insert directly ABOVE it:

```python
def _hour_or_none(raw: Any) -> Optional[int]:
    """0397: a posted hour as 0..23, or None when blank or not an hour."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 23 else None


```

Then in `_refuse_apartment_save`, replace exactly:

```python
    for field in ("checkin_hour", "checkout_hour"):
        if field in form:
            draft[field] = _form_str(form, field)
    copy_ctx = {
```

with:

```python
    for field in ("checkin_hour", "checkout_hour"):
        if field in form:
            # 0397: the page does arithmetic on these; text here crashed it.
            draft[field] = _hour_or_none(_form_str(form, field))
    copy_ctx = {
```

Commit `0397 step 1`.

### Step 2: a lock-tab refusal stays on the lock tab

a. In `_refuse_apartment_save`, change the signature line `    shared_time_error: Optional[str] = None,` to these two lines:

```python
    shared_time_error: Optional[str] = None,
    lock_times_error: bool = False,
```

b. In the same function, replace exactly:

```python
    return _render_apartment_detail(
        request,
        draft,
        copy_ctx,
        operator_error=operator_error,
        extra={
            "property_view": "settings",
            "settings_section": "property",
            "address_errors": address_errors or {},
            "shared_time_error": shared_time_error,
        },
        status_code=400 if (operator_error or address_errors or shared_time_error) else 200,
    )
```

with:

```python
    extra = {
        "property_view": "settings",
        "settings_section": "property",
        "address_errors": address_errors or {},
        "shared_time_error": shared_time_error,
    }
    if lock_times_error:
        # 0397: door codes need both times; stay on the Door lock tab with
        # the switch and the lock the host chose.
        draft["lock_id"] = _form_str(form, "lock_id") or draft.get("lock_id")
        extra.update(
            {
                "settings_section": "lock",
                "lock_times_error": True,
                "door_switch_posted": _form_str(form, "door_codes") == "1",
            }
        )
    return _render_apartment_detail(
        request,
        draft,
        copy_ctx,
        operator_error=operator_error,
        extra=extra,
        status_code=400
        if (operator_error or address_errors or shared_time_error or lock_times_error)
        else 200,
    )
```

c. In `_save_apartment_form`, inside `if not valid_pair:`, replace exactly:

```python
            return _refuse_apartment_save(
                request, apartment, form, None, shared_time_error="flash.error.door_code_hours"
            ), False
```

with:

```python
            from_lock_tab = "section=lock" in _form_str(form, "return_to")
            return _refuse_apartment_save(
                request,
                apartment,
                form,
                None,
                shared_time_error=None if from_lock_tab else "flash.error.door_code_hours",
                lock_times_error=from_lock_tab,
            ), False
```

Commit `0397 step 2`.

### Step 3: the template

In `App/app/templates/_property_editor.html`:

a. Replace the whole line

```jinja
      {% if apartment.checkin_hour is none or apartment.checkout_hour is none %}<p class="small warn-text">{{ t('why.times_missing') }}</p>{% endif %}
```

with:

```jinja
      {% if lock_times_error %}<p class="err-text" id="door-code-times-error" role="alert">{{ t('why.times_missing') }}</p>
      {% elif apartment.checkin_hour is none or apartment.checkout_hour is none %}<p class="small warn-text">{{ t('why.times_missing') }}</p>{% endif %}
```

b. Directly ABOVE the line `        <div class="feature-switch-row">` (the one inside `#door-code`), insert:

```jinja
        {% set switch_on = door_switch_posted if door_switch_posted is defined else door_code.enabled %}
```

c. In the `<input type="checkbox" role="switch" id="door_codes" ...>` line, replace `{% if door_code.enabled %}checked{% endif %}` with `{% if switch_on %}checked{% endif %}`. Leave `data-switch-saved` as it is.

d. Replace the `<span class="switch-status...` opening line and its text line, i.e. exactly

```jinja
          <span class="switch-status{% if door_code.enabled %} is-on{% endif %}" id="door_codes-status" aria-live="polite"
```

with

```jinja
          <span class="switch-status{% if switch_on != door_code.enabled %} is-unsaved{% elif door_code.enabled %} is-on{% endif %}" id="door_codes-status" aria-live="polite"
```

and

```jinja
                data-unsaved="{{ t('property_nav.switch_unsaved') }}">{{ t('property_nav.switch_enabled') if door_code.enabled else t('property_nav.switch_off') }}</span>
```

with

```jinja
                data-unsaved="{{ t('property_nav.switch_unsaved') }}">{% if switch_on != door_code.enabled %}{{ t('property_nav.switch_unsaved') }}{% elif door_code.enabled %}{{ t('property_nav.switch_enabled') }}{% else %}{{ t('property_nav.switch_off') }}{% endif %}</span>
```

Commit `0397 step 3`.

### Step 4: tests

Create `App/tests/test_door_code_missing_times_0397.py`:

```python
"""0397: door codes switched on without check-in/out times: never a 500."""
from __future__ import annotations

import re

from app import db
from tests.test_door_code_one_lock_one_property import (  # noqa: F401  (fixture)
    LOCK,
    _apartment,
    _client,
    two_properties,
)


def _post(client, apartment_id, entity, section, *, hours=True):
    data = {
        "internal_name": _apartment(apartment_id)["internal_name"],
        "legal_entity_id": str(entity),
        "return_to": f"/apartments/{apartment_id}?view=settings&section={section}",
        "door_code_section": "1",
        "door_codes_fields": "1",
        "door_codes": "1",
        "lock_id": LOCK["lock_id"],
    }
    if hours:
        data.update({"checkin_hour": "", "checkout_hour": ""})
    return client.post(
        f"/apartments/{apartment_id}", data=data, follow_redirects=False,
        headers={"accept": "text/html"},
    )


def test_lock_tab_save_without_times_stays_on_the_lock_tab(two_properties):
    _, entity, (a, _) = two_properties
    response = _post(_client(), a, entity, "lock")
    assert response.status_code == 400
    page = response.text
    assert 'id="door-code-times-error" role="alert"' in page
    assert "Set them first." in page
    assert re.search(r'data-settings-group="lock" id="settings-lock"', page)
    assert re.search(r'class="property-settings-group is-active" data-settings-group="lock"', page)
    switch = re.search(r'<input type="checkbox" role="switch" id="door_codes"[^>]*>', page).group(0)
    assert "checked" in switch
    option = re.search(r'<option value="%s"[^>]*>' % LOCK["lock_id"], page).group(0)
    assert "selected" in option
    assert "Not saved yet" in page or "is-unsaved" in page
    assert _apartment(a)["lock_provider"] is None


def test_lock_tab_save_without_posted_hours_does_not_crash(two_properties):
    _, entity, (a, _) = two_properties
    response = _post(_client(), a, entity, "lock", hours=False)
    assert response.status_code == 400
    assert 'id="door-code-times-error"' in response.text
    assert _apartment(a)["lock_provider"] is None


def test_property_tab_save_with_blank_times_shows_the_time_error(two_properties):
    _, entity, (a, _) = two_properties
    response = _post(_client(), a, entity, "property")
    assert response.status_code == 400
    assert "Choose the check-in and check-out hour." in response.text
    assert 'id="door-code-times-error"' not in response.text
    assert _apartment(a)["lock_provider"] is None


def test_times_set_then_codes_turn_on(two_properties):
    _, entity, (a, _) = two_properties
    db.update("apartment", a, {"checkin_hour": 15, "checkout_hour": 10})
    client = _client()
    data = {
        "internal_name": "Flat A", "legal_entity_id": str(entity),
        "return_to": f"/apartments/{a}?view=settings&section=lock",
        "door_code_section": "1", "door_codes_fields": "1", "door_codes": "1",
        "lock_id": LOCK["lock_id"], "checkin_hour": "15", "checkout_hour": "10",
    }
    assert client.post(f"/apartments/{a}", data=data, follow_redirects=False).status_code == 303
    assert _apartment(a)["lock_provider"] == "ttlock"
```

If the "is-active" regex does not match because of attribute order, read the `settings-lock` line of the rendered page once and adjust only that one assertion to the real markup (it must still prove the lock group is the active one).

Run §6 command 1. Commit `0397 step 4`.

## 5. Do not touch

The wizard (`setup_step`) paths, `_lock_section_refusal`, `app.js`, CSS, i18n files.

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_door_code_missing_times_0397.py tests/test_door_code_one_lock_one_property.py tests/test_wizard_second_lock_0394.py tests/test_ttlock.py tests/test_property_form_save.py tests/test_property_form_nav.py -q --tb=short 2>&1 | tail -30
cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome .venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_door_code_window_browser.py -q -rs --tb=short 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -30
```

If a file in command 1 does not exist, drop it from the command and note it under Deviations.

## 7. Acceptance

- [ ] All commands in §6 pass, 0 skipped.
- [ ] One commit per step.

## 8. Stop and ask

An anchor is not found, or a test fails twice: stop, write the report with `Status: blocked`. Screenshots are taken by the reviewer; do not take them. Do not push.

## 9. Report

`docs/tasks/0397-report.md`.
