# 0234: Door lock as one question with two clear answers (idea J)

Status: todo
Depends on: 0233 | Base commit: after 0233 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The wizard's lock step opens with "Optional. Do you have a TTLock smart lock with a gateway?" and its main button says "Skip this step", so a host without a lock feels they left something undone, and the summary shows "Skipped". Ask first, as two big choices ("No smart lock" / "Yes, I have a TTLock lock"); "No" saves the new mark `not_needed`, moves on, and every summary shows "Not needed" in calm grey. Optional steps carry "(optional)" in the step line.

## 2. Context

- `App/app/property_setup.py` stores `{"steps": {"<step>": "done" | "skipped" | "waiting"}}`; `load()` drops any value not in `MARKS`. Step 5 of the workflow strip already follows the lock (0230 `has_door_code`).
- `App/app/routes/onboarding_wizard.py` maps a POST `action` to a mark via `_SETUP_ACTIONS` (which steps allow it) and `_SETUP_MARKS`.
- 0230 added strings `wizard.door_lock.question|no|no_hint|yes|yes_hint|other_brands`, `wizard.summary.status.not_needed`, `wizard.optional_suffix`, a new `why.door_lock` without the question, and CSS `.lock-choice*`.
- The old `skip` action stays valid (tests and old forms post it).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/property_setup.py` | edit | the `not_needed` mark (steps 1 to 5) |
| `App/app/routes/onboarding_wizard.py` | edit | the `none` action (step 6) |
| `App/app/routes/admin.py` | edit | treat `not_needed` as answered (step 7) |
| `App/app/templates/setup_wizard/door_lock.html` | replace | the question (step 8) |
| `App/app/templates/setup_wizard/done.html` | edit | summary status (step 9) |
| `App/app/templates/_property_overview.html` | edit | overview status (step 10) |
| `App/app/templates/setup_wizard/_layout.html` | edit | "(optional)" (step 11) |
| `App/tests/test_lock_question_0234.py` | create | tests (step 12) |
| `docs/tasks/0234-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. `property_setup.py`: the mark

Anchor (exact line): `MARKS = ("done", "skipped", "waiting")`

Replace with: `MARKS = ("done", "skipped", "waiting", "not_needed")`

### Step 2. `property_setup.py`: `step_status`

Anchor (these two exact lines):

```python
    if marks.get(step) == "skipped":
        return "skipped"
```

Replace with:

```python
    if marks.get(step) == "skipped":
        return "skipped"
    # 0234: "No smart lock" is an answer, not a skip.
    if marks.get(step) == "not_needed":
        return "not_needed"
```

Also in the docstring line `    """done | skipped | waiting | todo | current — for checklist and progress."""` replace with `    """done | skipped | not_needed | waiting | todo | current — for checklist and progress."""`.

### Step 3. `property_setup.py`: `done_count`

Anchor (exact line): `        if step_status(step, state, apartment, facts) in ("done", "skipped"):`

Replace with: `        if step_status(step, state, apartment, facts) in ("done", "skipped", "not_needed"):`

### Step 4. `property_setup.py`: `current`

Anchor (these two exact lines):

```python
        if status in ("done", "skipped"):
            progress.append({"key": step, "state": "done" if status == "done" else "skipped"})
```

Replace with:

```python
        if status in ("done", "skipped", "not_needed"):
            progress.append({"key": step, "state": "skipped" if status == "skipped" else "done"})
```

### Step 5. `property_setup.py`: `may_view_step` and `checklist`

Anchor (exact line): `    if step_status(step, state, apartment, facts) in ("done", "skipped", "waiting"):`

Replace with: `    if step_status(step, state, apartment, facts) in ("done", "skipped", "waiting", "not_needed"):`

Then anchor (exact line): `            rows.append({"key": step, "status": "skipped"})`

Replace with: `            rows.append({"key": step, "status": "not_needed"})`

Command: `cd App && .venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py -q --tb=short -x 2>&1 | tail -8`. If a test asserts `"skipped"` for the door lock on a deployment without door codes, change only that expected value to `"not_needed"` in that test (allowed, one place) and name it in the report. Commit `0234 step 1-5`.

### Step 6. `routes/onboarding_wizard.py`

Anchor (exact line): `    "skip": property_setup.SKIPPABLE,`

Replace with:

```python
    "skip": property_setup.SKIPPABLE,
    "none": frozenset({"door_lock"}),
```

Then anchor (exact line): `_SETUP_MARKS = {"skip": "skipped", "wait": "waiting"}`

Replace with: `_SETUP_MARKS = {"skip": "skipped", "wait": "waiting", "none": "not_needed"}`

Commit `0234 step 6`.

### Step 7. `routes/admin.py`

Anchor (exact line): `    if status not in ("done", "skipped"):`

Replace with: `    if status not in ("done", "skipped", "not_needed"):`

Commit `0234 step 7`.

### Step 8. Replace the whole content of `setup_wizard/door_lock.html` with exactly this

```jinja
{% extends "setup_wizard/_layout.html" %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% from "_components.html" import field_label, help_tip with context %}
{% block wizard_content %}
<p class="setup-wizard-lede">{{ t('why.door_lock') }} {{ help_tip('wizard-lock-help', t('apartment.form.door_code.connect_first')) }}</p>
{% if door_code and door_code.account and door_code.locks %}
<form method="post" action="/apartments/{{ apartment.id }}" class="setup-wizard-form" id="door-lock-form">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="return_to" value="{{ wizard_next_return_to }}">
  <input type="hidden" name="setup_step" value="door_lock">
  <input type="hidden" name="door_code_section" value="1">
  <input type="hidden" name="internal_name" value="{{ apartment.internal_name }}">
  <input type="hidden" name="legal_entity_id" value="{{ apartment.legal_entity_id }}">
  <input type="hidden" name="city_en" value="{{ apartment.city_en or '' }}">
  <input type="hidden" name="default_purpose" value="{{ apartment.default_purpose or '10' }}">
  <p class="setup-wizard-instruction">{{ t('why.times') }}</p>
  {#- 0210: set or change the times here, without leaving the wizard. -#}
  <div class="grid two">
    {% for name, label in [('checkin_hour', 'apartment.form.door_code.checkin'), ('checkout_hour', 'apartment.form.door_code.checkout')] %}
    <div class="field"><label for="{{ name }}">{{ t(label) }}</label>
      <select id="{{ name }}" name="{{ name }}" required><option value="">{{ t('apartment.form.door_code.choose') }}</option>
        {% for h in range(24) %}<option value="{{ h }}" {% if apartment[name]|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
      </select></div>
    {% endfor %}
  </div>
  <input type="hidden" name="door_codes_fields" value="1">
  <div class="feature-switch-row">
    <label class="switch feature-switch" for="door_codes">
      <input type="checkbox" role="switch" id="door_codes" name="door_codes" value="1" {% if door_code.enabled %}checked{% endif %}>
      <span>{{ t('property_nav.door_switch') }}</span>
    </label>
  </div>
  <div class="field setup-wizard-lock-field"><label for="lock_id">{{ t('apartment.form.door_code.lock') }}</label>
    <select id="lock_id" name="lock_id"><option value="">{{ t('apartment.form.door_code.choose') }}</option>
      {% for lock in door_code.locks %}<option value="{{ lock.lock_id }}" {% if lock.lock_id == door_code.lock_id or (not door_code.lock_id and lock.lock_id == door_code.default_lock_id) %}selected{% endif %}>{{ lock.alias }}</option>{% endfor %}
    </select>
  </div>
</form>
{% elif door_code %}
{#- 0234: one question, two answers. "No" is a real answer (not_needed), never a skip. -#}
<h2 class="setup-wizard-section-title" id="lock-question">{{ t('wizard.door_lock.question') }}</h2>
<div class="lock-choice" role="group" aria-labelledby="lock-question">
  <form method="post" action="/apartments/{{ apartment.id }}/setup" class="lock-choice-form">
    <input type="hidden" name="_csrf" value="{{ csrf_token }}">
    <input type="hidden" name="step" value="door_lock">
    <button class="lock-choice-option" type="submit" name="action" value="none" data-lock-choice="no">
      <strong>{{ t('wizard.door_lock.no') }}</strong>
      <span>{{ t('wizard.door_lock.no_hint') }}</span>
    </button>
  </form>
  <details class="lock-choice-yes" data-lock-choice="yes"{% if door_code.account %} open{% endif %}>
    <summary class="lock-choice-option">
      <strong>{{ t('wizard.door_lock.yes') }}</strong>
      <span>{{ t('wizard.door_lock.yes_hint') }}</span>
    </summary>
    {% if lock_panel and lock_panel.smart_locks_enabled %}
    <section class="setup-wizard-lock-panel" id="door-code">
      {% with account=lock_panel.account, receiver=lock_panel.receiver, locks=lock_panel.locks, fetched_at=lock_panel.fetched_at, reauth=lock_panel.reauth, return_to=lock_panel.return_to, properties_using=lock_panel.properties_using %}
      {% include "_smart_locks_panel.html" %}
      {% endwith %}
    </section>
    {% endif %}
  </details>
</div>
<p class="lock-choice-note">{{ t('wizard.door_lock.other_brands') }}</p>
{% else %}
<p class="setup-wizard-instruction">{{ t('wizard.door_lock.unavailable') }}</p>
{% endif %}
{% endblock %}
{% block wizard_actions %}
{% if door_code and door_code.account and door_code.locks %}
<form method="post" action="/apartments/{{ apartment.id }}/setup" class="inline setup-wizard-skip">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="step" value="door_lock">
  <button class="ui-btn ui-btn-secondary" type="submit" name="action" value="none" formnovalidate>{{ t('wizard.door_lock.no') }}</button>
</form>
<button class="{{ cta }}" type="submit" form="door-lock-form">{{ t('wizard.save_continue') }}</button>
{% elif not door_code %}
<form method="post" action="/apartments/{{ apartment.id }}/setup" class="inline setup-wizard-skip">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="step" value="door_lock">
  <button class="{{ cta }}" type="submit" name="action" value="none">{{ t('wizard.save_continue') }}</button>
</form>
{% else %}
<span></span>
{% endif %}
{% endblock %}
```

Command: `cd App && .venv/bin/python -m pytest tests/test_smart_locks_page.py tests/test_onboarding_wizard_survival.py -q --tb=short -x 2>&1 | tail -8`. A test that looks for the text "Skip this step" on the lock step may fail: change only that expectation to the new "No smart lock" text and name it in the report. Commit `0234 step 8`.

### Step 9. `setup_wizard/done.html`

Anchor (exact line): `  {% set status = row.status if row.status in ['done', 'skipped', 'waiting'] else 'todo' %}`

Replace with: `  {% set status = row.status if row.status in ['done', 'skipped', 'waiting', 'not_needed'] else 'todo' %}`

Commit `0234 step 9`.

### Step 10. `_property_overview.html`

Anchor (exact line): `    {% set status = row.status if row.status in ['done', 'skipped', 'waiting'] else 'todo' %}`

Replace with: `    {% set status = row.status if row.status in ['done', 'skipped', 'waiting', 'not_needed'] else 'todo' %}`

Commit `0234 step 10`.

### Step 11. `setup_wizard/_layout.html`: "(optional)"

Anchor (exact line, starts with `{% block meta %}`):

```jinja
{% block meta %}{% if wizard_number %}{{ t('wizard.count', n=wizard_number, total=wizard_total, step=t('wizard.step.' ~ wizard_step)) }}{% elif guide %}{{ t('wizard.count', n=guide.number, total=guide.total, step=t('wizard.step.' ~ guide.key)) }}{% endif %}{% endblock %}
```

Replace with:

```jinja
{% block meta %}{% if wizard_number %}{{ t('wizard.count', n=wizard_number, total=wizard_total, step=t('wizard.step.' ~ wizard_step) ~ (t('wizard.optional_suffix') if wizard_step in ('stay_fee', 'door_lock') else '')) }}{% elif guide %}{{ t('wizard.count', n=guide.number, total=guide.total, step=t('wizard.step.' ~ guide.key) ~ (t('wizard.optional_suffix') if guide.key in ('stay_fee', 'door_lock') else '')) }}{% endif %}{% endblock %}
```

Commit `0234 step 11`.

### Step 12. Create `App/tests/test_lock_question_0234.py` with exactly this content

```python
"""0234: "No smart lock" is an answer, saved as not_needed, shown as Not needed."""

from __future__ import annotations

from app import property_setup


def _state(**steps):
    return {"steps": steps, "finished": False, "hidden": False}


def test_not_needed_is_a_stored_mark():
    assert "not_needed" in property_setup.MARKS


def test_not_needed_counts_as_answered():
    state = _state(door_lock="not_needed")
    apartment = {"lock_provider": None, "stay_fee_rate_czk": 0}
    facts = {"feeds": 0, "stays": 0, "guests_registered": False, "report_complete": False}
    assert property_setup.step_status("door_lock", state, apartment, facts) == "not_needed"


def test_the_summary_reads_not_needed_in_every_language():
    from app import host_i18n

    assert host_i18n.STRINGS["en"]["wizard.summary.status.not_needed"] == "Not needed"
    assert host_i18n.STRINGS["cs"]["wizard.summary.status.not_needed"] == "Není potřeba"
```

Command: `cd App && .venv/bin/python -m pytest tests/test_lock_question_0234.py -q --tb=short -x 2>&1 | tail -10` → 3 passed. Commit `0234 step 12`.

## 5. Do not touch

Everything outside §3 (except the one expected value allowed in steps 5 and 8). The `skip` action and `SKIPPABLE`. `_smart_locks_panel.html`.

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_lock_question_0234.py tests/test_onboarding_wizard_survival.py tests/test_smart_locks_page.py tests/test_onboarding_why_0206.py tests/test_property_setup*.py -q --tb=short 2>&1 | tail -15`

## 7. Acceptance

- [ ] The 3 new tests pass; the named older tests still pass.
- [ ] Without a lock, the step shows two big choices and no "Skip this step" button.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change beyond the two allowed expectations; a step is unclear.

## 9. Report

Write `docs/tasks/0234-report.md` (600 tokens at most) and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/property_setup.py` (stored wizard state), `App/app/templates/setup_wizard/door_lock.html`.

## Owner steps

None.
