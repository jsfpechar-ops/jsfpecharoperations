# 0233: Prove the guest message is pasted, remind until it is (idea D)

Status: review
Depends on: 0232 | Base commit: after 0232 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The host's one real job is pasting the guest message into Airbnb or Booking.com, and nothing checks it. Once a stay has reached the guest link and still no real guest has claimed a stay, the dashboard shows one bordered card: "No guest has used your guest link yet. Did you paste the guest message into Airbnb or Booking.com?", the how-to behind a disclosure, and a button to the message. The card goes away by itself once a guest claims a stay.

## 2. Context

- 0230 added `workflow.link_unused(apartments)` (properties where a non-demo stay added after the property reached the link window and no `reservation_claim` row is `provisional`/`claimed`), strings `workflow.paste.*`, CSS `.paste-check*`.
- Privacy (hard rule 2): no new log, column or request; it reads stored claims only.
- Outside the wizard: one sentence, the rest behind `<details>` (works without JavaScript).
- The guest message lives at `/apartments/<id>?view=settings&section=guests#communication` (used by the stay page menu).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | import + one context key (steps 1, 2) |
| `App/app/templates/dashboard.html` | edit | the card (step 3) |
| `App/tests/test_paste_check_0233.py` | create | tests (step 4) |
| `docs/tasks/0233-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. `routes/admin.py`: import

Anchor (these three exact lines, around line 57):

```python
    validation,
)
from ..templating import render
```

Replace with:

```python
    validation,
    workflow,
)
from ..templating import render
```

Command: `cd App && .venv/bin/python -c "import app.routes.admin" 2>&1 | tail -5` → no output. Commit `0233 step 1`.

### Step 2. `routes/admin.py`: dashboard context

Anchor (exact line, in `def dashboard`): `            "minutes_saved": minutes_saved,`

Replace with:

```python
            "minutes_saved": minutes_saved,
            # 0233: remind until a real guest has used the guest link.
            "link_unused": workflow.link_unused(apartments),
```

Commit `0233 step 2`.

### Step 3. `dashboard.html`: the card

Anchor (exact line): `  {% if missing_report_display and not banner_showing %}`

Insert directly BEFORE it:

```jinja
  {% if link_unused and not banner_showing %}
  <section class="paste-check" data-paste-check aria-labelledby="paste-check-title">
    <h2 id="paste-check-title">{{ t('workflow.paste.title') }}</h2>
    <p>{{ t('workflow.paste.body') }}</p>
    <details>
      <summary>{{ t('workflow.paste.how') }}</summary>
      <ul>
        <li>{{ t('workflow.paste.airbnb') }}</li>
        <li>{{ t('workflow.paste.booking') }}</li>
        <li>{{ t('workflow.paste.direct') }}</li>
      </ul>
    </details>
    <div class="paste-check-actions">
      {% for apartment in link_unused[:3] %}
      <a class="ui-btn ui-btn-secondary" href="/apartments/{{ apartment.id }}?view=settings&amp;section=guests#communication">{{ t('workflow.paste.open') }}{% if link_unused | length > 1 %}: {{ apartment.internal_name }}{% endif %}</a>
      {% endfor %}
    </div>
  </section>
  {% endif %}
```

Commit `0233 step 3`.

### Step 4. Create `App/tests/test_paste_check_0233.py` with exactly this content

```python
"""0233: the dashboard reminds the host until a guest has used the link."""

from __future__ import annotations

from app import claim, db
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401


def _stay_today(apartment_id: int) -> int:
    today = claim.prague_today().isoformat()
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "wf0233-a", "date_from": today, "date_to": "2099-01-01",
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_no_card_before_any_stay_reaches_the_link(host):  # noqa: F811
    _apartment_id()
    assert "data-paste-check" not in host.get("/?lang=en").text


def test_card_shows_until_a_guest_claims_a_stay(host):  # noqa: F811
    reservation_id = _stay_today(_apartment_id())
    assert "data-paste-check" in host.get("/?lang=en").text
    db.insert("reservation_claim", {
        "reservation_id": reservation_id, "state": "claimed", "token_version": 0,
        "claimed_at": db.utcnow(), "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    assert "data-paste-check" not in host.get("/?lang=en").text
```

Command: `cd App && .venv/bin/python -m pytest tests/test_paste_check_0233.py -q --tb=short -x 2>&1 | tail -15` → 2 passed. If the card is hidden only because the onboarding banner shows (`banner_showing`), say so in the report and stop; do not change the condition. Commit `0233 step 4`.

## 5. Do not touch

Everything outside §3. No new tracking of link opens (privacy rule).

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_paste_check_0233.py tests/test_workflow_strip_0232.py tests/test_host_quiet_dashboard_browser.py -q --tb=short -rs 2>&1 | tail -15` (the browser file may skip without Playwright; say so).

## 7. Acceptance

- [ ] The 2 new tests pass.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0233-report.md` (600 tokens at most) and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/routes/admin.py` (dashboard query cost: one or two small queries per property).

## Owner steps

None.
