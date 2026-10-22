# 0232: One picture of the workflow and a tracker on every stay (ideas A, B, Q)

Status: review
Depends on: 0231 | Base commit: after 0231 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Hosts cannot tell what is their job and what happens by itself. Show the five-step story as one strip (first wizard screen, empty dashboard, guide) with a "You, once" / "Automatic" tag per step, give every stay page a compact tracker (five dots and "Step 2 of 5: Guest form", tap for all steps), and put the step number in the stay list pill ("2 of 5 · Waiting for guest"), using the same step names everywhere.

## 2. Context

- 0230 added: `workflow_steps(apartment_or_none)` → list of `{"n", "key", "who"}` (`who` is `you_once`, `you` or `auto`); `stay_journey(reservation, progress)` → `None` or `{"current", "total", "complete", "failed", "steps": [{"n", "key", "who", "state"}]}` (`state` is `done`, `current` or `todo`); `journey_step(status)` → `int | None`; strings `workflow.*`; CSS classes `.workflow-strip*`, `.workflow-num`, `.workflow-tag`, `.journey*` in `static/workflow.css` (already linked).
- WCAG 2.2 AA (owner rule): the strip and the tracker are real ordered lists, the current step carries `aria-current="step"`, colour is never the only signal (done steps show a tick and a screen-reader word).
- Outside the wizard no description walls: the tracker is compact first, detail on tap (`<details>`, works without JavaScript).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_workflow.html` | create | the two macros (step 1) |
| `App/app/templates/setup_wizard/property.html` | edit | strip on the first wizard screen (step 2) |
| `App/app/templates/dashboard.html` | edit | strip on the empty dashboard (step 3) |
| `App/app/templates/guide.html` | edit | strip leads the guide (step 4) |
| `App/app/templates/reservation_detail.html` | edit | tracker in the Next step panel (step 5) |
| `App/app/templates/_components.html` | edit | `progress_pill` takes `step` (step 6) |
| `App/app/templates/reservations.html` | edit | pass the step (step 7) |
| `App/tests/test_workflow_strip_0232.py` | create | tests (step 8) |
| `docs/tasks/0232-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Create `App/app/templates/_workflow.html` with exactly this content

```jinja
{#- 0232: the five-step story (A) and one stay's place in it (B). Real ordered
    lists; the current step is named for screen readers; colour is never the
    only signal. Words come from workflow.* (0230), the same on every page. -#}
{% macro workflow_strip(apartment=none, heading=true) %}
<section class="workflow-block" data-workflow-strip{% if heading %} aria-labelledby="workflow-title"{% endif %}>
  {% if heading %}<h2 id="workflow-title">{{ t('workflow.title') }}</h2>{% endif %}
  <ol class="workflow-strip"{% if not heading %} aria-label="{{ t('workflow.title') }}"{% endif %}>
    {% for step in workflow_steps(apartment) %}
    <li class="workflow-strip-step{{ ' is-you' if step.who != 'auto' }}" data-workflow-step="{{ step.key }}">
      <span class="workflow-num" aria-hidden="true">{{ step.n }}</span>
      <span class="workflow-strip-copy">
        <span class="workflow-strip-label">{{ t('workflow.step.' ~ step.key) }}</span>
        <span class="workflow-tag">{{ t('workflow.who.' ~ step.who) }}</span>
      </span>
    </li>
    {% endfor %}
  </ol>
</section>
{% endmacro %}

{% macro stay_journey_panel(journey) %}
{% if journey %}
{% set now_step = journey.steps[journey.current - 1] %}
<details class="journey" data-journey>
  <summary>
    <ol class="journey-dots" aria-hidden="true">{% for step in journey.steps %}<li class="is-{{ step.state }}"></li>{% endfor %}</ol>
    <span class="journey-label">{% if journey.complete %}{{ t('workflow.journey.complete') }}{% else %}{{ t('workflow.journey.label', n=journey.current, total=journey.total, step=t('workflow.short.' ~ now_step.key)) }}{% endif %}</span>
  </summary>
  <ol class="journey-steps">
    {% for step in journey.steps %}
    <li class="is-{{ step.state }}"{% if step.state == 'current' %} aria-current="step"{% endif %}>
      <span class="workflow-num" aria-hidden="true">{% if step.state == 'done' %}✓{% else %}{{ step.n }}{% endif %}</span>
      <span>{{ t('workflow.step.' ~ step.key) }}{% if step.state != 'todo' %} <span class="sr-only">({{ t('workflow.journey.state.' ~ step.state) }})</span>{% endif %}</span>
    </li>
    {% endfor %}
  </ol>
</details>
{% endif %}
{% endmacro %}
```

Commit `0232 step 1`.

### Step 2. `setup_wizard/property.html`

Anchor (exact line): `<p class="setup-wizard-lede">{{ t('why.property') }}</p>`

Replace with:

```jinja
<p class="setup-wizard-lede">{{ t('why.property') }}</p>
{% from "_workflow.html" import workflow_strip with context %}
{{ workflow_strip(none) }}
```

Commit `0232 step 2`.

### Step 3. `dashboard.html`

Anchor (exact line): `  {% if not rows and feed_count %}{{ ui_empty(t('dashboard.empty.no_stays')) }}`

Insert directly BEFORE it:

```jinja
  {% if not rows %}{% from "_workflow.html" import workflow_strip with context %}{{ workflow_strip(apartments[0] if apartments | length == 1 else none) }}{% endif %}
```

Commit `0232 step 3`.

### Step 4. `guide.html`

Anchor (exact line): `      <h2>{{ t('guide.nav.overview') }}</h2>`

Replace with:

```jinja
      <h2>{{ t('guide.nav.overview') }}</h2>
      {% from "_workflow.html" import workflow_strip with context %}
      {{ workflow_strip(none, heading=false) }}
```

Commit `0232 step 4`.

### Step 5. `reservation_detail.html`

Anchor (exact line): `<section class="panel stay-command-panel" id="now">`

Replace with:

```jinja
<section class="panel stay-command-panel" id="now">
  {% from "_workflow.html" import stay_journey_panel with context %}
  {{ stay_journey_panel(stay_journey(reservation, progress)) }}
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_link_window_0231.py -q --tb=short -x 2>&1 | tail -5` → pass. Commit `0232 step 5`.

### Step 6. `_components.html`: `progress_pill` takes the step

Anchor (exact line): `{% macro progress_pill(status, automation_mode=none, compact=false, is_demo=false) %}`

Replace with: `{% macro progress_pill(status, automation_mode=none, compact=false, is_demo=false, step=none) %}`

Then anchor (exact line):

```jinja
  <span class="ui-badge ui-badge-{{ UI_KINDS.get(tone, 'neutral') }}{{ ' ui-badge-overdue' if tone == 'red' }}" data-tone="{{ tone }}"{% if tip %} title="{{ tip }}"{% endif %}>{{ label }}</span>
```

Replace with:

```jinja
  <span class="ui-badge ui-badge-{{ UI_KINDS.get(tone, 'neutral') }}{{ ' ui-badge-overdue' if tone == 'red' }}" data-tone="{{ tone }}"{% if tip %} title="{{ tip }}"{% endif %}>{% if step %}<span class="ui-badge-step" data-journey-step="{{ step }}">{{ t('workflow.step_of', n=step, total=5) }} · </span>{% endif %}{{ label }}</span>
```

Commit `0232 step 6`.

### Step 7. `reservations.html`

Anchor (exact line):

```jinja
          {% else %}{{ progress_pill(progress.status, reservation.automation_mode, is_demo=('(demo)' in reservation.internal_name or reservation.source == 'demo')) }}{% endif %}
```

Replace with:

```jinja
          {% else %}{{ progress_pill(progress.status, reservation.automation_mode, is_demo=('(demo)' in reservation.internal_name or reservation.source == 'demo'), step=journey_step(progress.status)) }}{% endif %}
```

Commit `0232 step 7`.

### Step 8. Create `App/tests/test_workflow_strip_0232.py` with exactly this content

```python
"""0232: the five-step strip and the stay tracker."""

from __future__ import annotations

from datetime import timedelta

from app import claim, db
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401


def _stay(apartment_id: int) -> int:
    start = claim.prague_today() + timedelta(days=1)
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "wf0232-a",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_the_empty_dashboard_tells_the_whole_story_with_the_hosts_own_option(host):  # noqa: F811
    _apartment_id()  # automation_mode manual
    page = host.get("/?lang=en")
    assert page.status_code == 200
    assert "data-workflow-strip" in page.text
    assert 'data-workflow-step="paste"' in page.text
    assert 'data-workflow-step="police_manual"' in page.text


def test_the_guide_opens_with_the_strip(host):  # noqa: F811
    page = host.get("/guide?lang=en")
    assert "data-workflow-strip" in page.text


def test_a_waiting_stay_shows_step_2_of_5(host):  # noqa: F811
    reservation_id = _stay(_apartment_id())
    page = host.get(f"/reservations/{reservation_id}?lang=en")
    assert "data-journey" in page.text
    assert 'aria-current="step"' in page.text
    assert "Step 2 of 5: Guest form" in page.text
    listing = host.get("/reservations?lang=en")
    assert 'data-journey-step="2"' in listing.text
```

Command: `cd App && .venv/bin/python -m pytest tests/test_workflow_strip_0232.py -q --tb=short -x 2>&1 | tail -15` → 3 passed. Commit `0232 step 8`.

## 5. Do not touch

Everything outside §3. Other `progress_pill` callers keep their calls (the new argument defaults to none). No new strings, no CSS (0230 owns both).

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_workflow_strip_0232.py tests/test_guest_link_window_0231.py tests/test_workflow_0230.py tests/test_onboarding_wizard_survival.py -q --tb=short 2>&1 | tail -15`

## 7. Acceptance

- [ ] The 3 new tests pass; the named older tests still pass.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0232-report.md` (600 tokens at most) and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/templates/_components.html` (shared macro).

## Owner steps

None.
