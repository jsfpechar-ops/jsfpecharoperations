# 0210: Check-in and check-out times are required, and the lock step keeps you in the wizard

Status: todo
Depends on: 0208 | Base commit: f547ef0 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The test user reached the door-lock step with no check-in/check-out times, and the only way to set them left the wizard. Times become required on wizard step 1 (Josef: "100% mandatory"); the lock step lets the host set or change them in place; the settings lock section warns when they are missing.

## 2. Context

Times are already on wizard step 1 (`App/app/templates/setup_wizard/property.html`) as two `<select>`s with an empty first option, and in settings (`_property_editor.html`, section `arrival-departure`). The server already:
- parses posted hours in `_property_hour_changes` (`App/app/routes/admin.py`); a posted blank becomes `None`;
- accepts hours posted on the `door_lock` wizard step (`owns_shared_hours`);
- refuses to switch door codes on without both hours.

The wizard error path for an hour error (verbatim, `admin.py` in `_save_apartment_form`):

```
    hour_values, hour_error = (
        _property_hour_changes(form, apartment_data) if owns_shared_hours else ({}, None)
    )
    if hour_error:
```

Settings is one big `<form>` with hidden tabs, so `required` must NOT be added in settings (the browser would block saves on a hidden tab). Wizard forms are one step each, so `required` is safe there.

The wizard URL of a step is `/apartments/<id>/setup/<step>` (`property_setup.wizard_url`).

`why.times` and `host.property_times_edit` already exist (0206).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/setup_wizard/property.html | edit | `required` on both selects |
| App/app/templates/setup_wizard/door_lock.html | edit | selects in place |
| App/app/templates/_property_editor.html | edit | missing-times warning in the lock section |
| App/app/routes/admin.py | edit | refuse a blank time on wizard step 1 |
| App/app/host_i18n.py | edit | `_ONBOARDING_TEST_0210_STRINGS` |
| App/app/host_vi_i18n.py | edit | Vietnamese |
| App/tests/test_times_required_0210.py | create | tests |

No other file may change.

## 4. Steps

### Step 1. `setup_wizard/property.html`

Replace `      <select id="{{ name }}" name="{{ name }}"><option value="">` with `      <select id="{{ name }}" name="{{ name }}" required><option value="">` (one occurrence, inside the `for` loop; it covers both selects).

### Step 2. `admin.py`

Directly after the three lines

```
    hour_values, hour_error = (
        _property_hour_changes(form, apartment_data) if owns_shared_hours else ({}, None)
    )
```

add:

```python
    # 0210: wizard step 1 needs both times; a blank posted select is refused.
    if not hour_error and setup_step == "property" and any(
        name in form and hour_values.get(name) is None for name in ("checkin_hour", "checkout_hour")
    ):
        hour_error = "flash.error.times_required"
```

(A post that has no hour fields at all is not refused; old tests post like that.)

### Step 3. `setup_wizard/door_lock.html`

Replace the whole paragraph

```
  <p class="setup-wizard-instruction">{{ t('why.times') }}
    {{ t('apartment.form.door_code.checkin') }} {{ '%02d:00' | format(apartment.checkin_hour) if apartment.checkin_hour is not none else '—' }} ·
    {{ t('apartment.form.door_code.checkout') }} {{ '%02d:00' | format(apartment.checkout_hour) if apartment.checkout_hour is not none else '—' }}.
    <a href="/apartments/{{ apartment.id }}?view=settings&amp;section=property#arrival-departure">{{ t('host.property_times_edit') }}</a>
  </p>
```

with

```
  <p class="setup-wizard-instruction">{{ t('why.times') }}</p>
  {% if door_code.account and door_code.locks %}
  {#- 0210: set or change the times here, without leaving the wizard. -#}
  <div class="grid two">
    {% for name, label in [('checkin_hour', 'apartment.form.door_code.checkin'), ('checkout_hour', 'apartment.form.door_code.checkout')] %}
    <div class="field"><label for="{{ name }}">{{ t(label) }}</label>
      <select id="{{ name }}" name="{{ name }}" required><option value="">{{ t('apartment.form.door_code.choose') }}</option>
        {% for h in range(24) %}<option value="{{ h }}" {% if apartment[name]|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
      </select></div>
    {% endfor %}
  </div>
  {% else %}
  <p class="setup-wizard-instruction">
    {{ t('apartment.form.door_code.checkin') }} {{ '%02d:00' | format(apartment.checkin_hour) if apartment.checkin_hour is not none else '—' }} ·
    {{ t('apartment.form.door_code.checkout') }} {{ '%02d:00' | format(apartment.checkout_hour) if apartment.checkout_hour is not none else '—' }}.
    <a href="/apartments/{{ apartment.id }}/setup/property">{{ t('wizard.times_change') }}</a>
  </p>
  {% endif %}
```

If the paragraph is not verbatim (0206 changed its first line to `why.times`; check with `grep -n "why.times" App/app/templates/setup_wizard/door_lock.html`), read lines 14-22 and replace that same paragraph; say so in the report.

### Step 4. `_property_editor.html` (settings lock section)

Find the lock-section paragraph that starts `      <p class="ui-sub">{{ t('why.times') }}` (0206) and ends with the `host.property_times_edit` link and `</p>`. Directly after its `</p>` add:

```
      {% if apartment.checkin_hour is none or apartment.checkout_hour is none %}<p class="small warn-text">{{ t('why.times_missing') }}</p>{% endif %}
```

`warn-text` and `small` are existing classes (`grep -n "warn-text" App/app/templates/_property_editor.html` shows one already used).

### Step 5. Text

`host_i18n.py`, insert above `STRINGS["vi"] = dict(_VI_STRINGS)` after the last `_ONBOARDING_TEST_..._STRINGS` loop:

```python
_ONBOARDING_TEST_0210_STRINGS = {
    "en": {
        "flash.error.times_required": "Choose the check-in and check-out time. UbyHost needs them for door codes and cleaning.",
        "why.times_missing": "Check-in and check-out times are missing, so door codes cannot work yet. Set them first.",
        "wizard.times_change": "Change in step 1",
    },
    "cs": {
        "flash.error.times_required": "Vyberte čas příjezdu a odjezdu. UbyHost je potřebuje pro kódy ke dveřím a úklid.",
        "why.times_missing": "Chybí čas příjezdu a odjezdu, takže kódy ke dveřím zatím nemohou fungovat. Nejdřív je nastavte.",
        "wizard.times_change": "Změnit v kroku 1",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0210_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Append to `host_vi_i18n.py`:

```python

# 0210: times are required.
STRINGS.update({
    "flash.error.times_required": "Hãy chọn giờ nhận phòng và trả phòng. UbyHost cần chúng cho mã cửa và lịch dọn dẹp.",
    "why.times_missing": "Thiếu giờ nhận phòng và trả phòng, nên mã cửa chưa thể hoạt động. Hãy đặt chúng trước.",
    "wizard.times_change": "Đổi ở bước 1",
})
```

### Step 6. Tests: `App/tests/test_times_required_0210.py`

Read `tests/test_onboarding_wizard_survival.py` lines 620-660 (the test that posts `checkin_hour` 16 / `checkout_hour` 10 on the property step) and reuse its fixtures and payload. Write:

1. Posting the property step with `checkin_hour=""` and `checkout_hour="10"` returns 400, the page contains the English `flash.error.times_required` text, and the stored hours are unchanged.
2. Posting it with `16` / `10` returns 303 and stores both (same as the existing test; keep it short).
3. GET `/apartments/<id>/setup/property?lang=en`: both selects carry `required` (`'id="checkin_hour" name="checkin_hour" required'` in the HTML).

### Step 7. Commit

`0210 times required`, only §3 files, trailers from your prompt, never PNGs.

## 5. Do not touch

Settings `arrival-departure` selects (no `required` there), filing code, guest templates, CSS, JS. AGENTS hard rules 1, 3, 5, 6, 8.

## 6. Commands

1. From `App/`: `.venv/bin/python -m pytest tests/test_times_required_0210.py tests/test_onboarding_wizard_survival.py tests/test_smart_locks_page.py tests/test_door_code_one_lock_one_property.py -q --tb=short 2>&1 | tail -30`
2. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_lock_navigation_browser.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped). If a browser test now stops on step 1 because a time select is empty, add `page.select_option("#checkin_hour", "15")` and `page.select_option("#checkout_hour", "10")` before its save click and list it in the report.
3. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` → `OK`
4. 390 px screenshot of the wizard lock step with a connected synthetic lock (reuse a fixture from `tests/test_lock_navigation_browser.py` if one renders it) to `/mnt/project-files/onboarding-0210/`. Do not commit it.

## 7. Acceptance

- [ ] Step 1 cannot be saved without both times; the lock step shows editable times when a lock is connected and never links out of the wizard; settings warns when times are missing.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0210-report.md`, as in TEMPLATE.md §9.
