# 0231: Guest link window impossible to miss (idea I)

Status: todo
Depends on: 0230 | Base commit: after 0230 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A host who opens their own guest link after setup usually sees "There's nothing to register yet" and thinks setup failed, because the link only lists stays that start within `permalink_window_days`. Say it with the host's own next stay (property editor, wizard), show "On guest link now / from 12. 11." on each waiting stay, offer the guest's own link on the stay page, and show a host-only note on the empty guest page. The window itself is NOT widened (owner decision 2026-10-22: other guests could claim a stay early).

## 2. Context

- 0230 added the template globals `link_window(reservation)` → `None | {"state": "now"|"from", "opens": date}` and `next_stay_window(apartment)` → `{"stay": row|None, "days": int, "window": dict|None}`, plus all strings (`workflow.link.*`). Module `app/workflow.py`.
- `tp(base, n)` is the counted-string template helper; `date_short` formats an ISO date string as `d. m.`.
- Outside the wizard: one short status line, the "why" behind a `help_tip` "?" (macro in `_components.html`, already imported in `reservation_detail.html`).
- Guest page rule (AGENTS hard rule 7): guest template/CSS change needs guest tests with 0 skipped. Guests must never see another stay's dates: the note is rendered only when `_host_owns_apartment(request, apartment)` is true.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_property_editor.html` | edit | next-stay line under the window field (step 1) |
| `App/app/templates/setup_wizard/guest_link.html` | edit | next-stay line + "See what guests see today" (step 2) |
| `App/app/templates/reservations.html` | edit | link-window line per waiting stay (step 3) |
| `App/app/templates/reservation_detail.html` | edit | link-window line, "?" and copy button (steps 4, 5) |
| `App/app/routes/guest.py` | edit | host-only note on the empty picker (steps 6 to 9) |
| `App/app/templates/guest/unavailable.html` | edit | render the note (step 10) |
| `App/app/static/guest.css` | edit | note style (step 11) |
| `App/app/templates/guest/base.html` | edit | new `?v=` key (step 12) |
| `App/tests/test_guest_link_window_0231.py` | create | tests (step 13) |
| `docs/tasks/0231-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. `_property_editor.html`

Anchor (exact line): `                 value="{{ apartment.permalink_window_days }}">`

Insert directly after it:

```jinja
          {%- set link_next = next_stay_window(apartment) if apartment.id else none %}
          {%- if link_next %}
          <p class="ui-sub link-window-note" data-link-window-note>{% if link_next.stay and link_next.window and link_next.window.state == 'now' %}{{ t('workflow.link.next_stay_now', stay=link_next.stay.date_from | date_short) }}{% elif link_next.stay and link_next.window %}{{ t('workflow.link.next_stay', stay=link_next.stay.date_from | date_short, date=link_next.window.opens.isoformat() | date_short) }}{% else %}{{ tp('workflow.link.no_stay', link_next.days) }}{% endif %}</p>
          {%- endif %}
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_links_preview.py -q --tb=short -x 2>&1 | tail -5` → pass. Commit `0231 step 1`.

### Step 2. `setup_wizard/guest_link.html`

Anchor (exact line): `<section class="setup-wizard-message" aria-labelledby="wizard-message-title">`

Insert directly BEFORE it:

```jinja
{% set link_next = next_stay_window(apartment) %}
<p class="setup-wizard-instruction link-window-note" data-link-window-note>
  {% if link_next.stay and link_next.window and link_next.window.state == 'now' %}{{ t('workflow.link.next_stay_now', stay=link_next.stay.date_from | date_short) }}{% elif link_next.stay and link_next.window %}{{ t('workflow.link.next_stay', stay=link_next.stay.date_from | date_short, date=link_next.window.opens.isoformat() | date_short) }}{% else %}{{ tp('workflow.link.no_stay', link_next.days) }}{% endif %}
  <a href="{{ permalink }}" target="_blank" rel="noopener" data-link-preview>{{ t('workflow.link.preview') }}</a>
</p>
```

Command: `cd App && .venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py -q --tb=short -x 2>&1 | tail -5` → pass. Commit `0231 step 2`.

### Step 3. `reservations.html`

Anchor (these three exact lines):

```jinja
          {% if check_in and reservation.status == 'active' %}
            <div class="stay-report-deadline">{{ deadline_badge(deadline_cell(progress, check_in)) }}</div>
          {% endif %}
```

Replace with:

```jinja
          {% if check_in and reservation.status == 'active' %}
            <div class="stay-report-deadline">{{ deadline_badge(deadline_cell(progress, check_in)) }}</div>
          {% endif %}
          {% if reservation.status == 'active' and progress.status in ('awaiting_guest', 'incomplete') %}
            {% set lw = link_window(reservation) %}
            {% if lw %}<div class="link-window{{ ' is-later' if lw.state == 'from' }}" data-link-window="{{ lw.state }}">{{ t('workflow.link.now') if lw.state == 'now' else t('workflow.link.from', date=lw.opens.isoformat() | date_short) }}</div>{% endif %}
          {% endif %}
```

Command: `cd App && .venv/bin/python -m pytest tests/test_host_list_cards_browser.py -q --tb=short -x -rs 2>&1 | tail -5` (browser test; if Playwright is missing it skips, note that in the report, the orchestrator runs it later). Commit `0231 step 3`.

### Step 4. `reservation_detail.html`: the line under "Next step"

Anchor (these two exact lines):

```jinja
        {% else %}{{ t('stay.detail.door_code.waiting') }}{% endif %}
      </p>{% endif %}
```

Replace with:

```jinja
        {% else %}{{ t('stay.detail.door_code.waiting') }}{% endif %}
      </p>{% endif %}
      {% set lw = link_window(reservation) if progress.status in ('awaiting_guest', 'incomplete') else none %}
      {% if lw %}<p class="ui-sub link-window-line" data-link-window="{{ lw.state }}"><span class="link-window{{ ' is-later' if lw.state == 'from' }}">{{ t('workflow.link.now') if lw.state == 'now' else t('workflow.link.from', date=lw.opens.isoformat() | date_short) }}</span>{% if lw.state == 'from' %}{{ help_tip('link-window-help', t('workflow.link.why')) }}{% endif %}</p>{% endif %}
```

Commit `0231 step 4` (test in step 13).

### Step 5. `reservation_detail.html`: the guest's own link button

Anchor (exact line): `    <div class="stay-command-actions">`

Insert directly after it:

```jinja
      {% if lw and lw.state == 'from' %}<button class="ui-btn ui-btn-secondary" type="button" data-copy="stay-link" data-copy-label="{{ t('workflow.link.copy_own') }}" data-copied-label="{{ t('stay.detail.link_copied') }}" data-copy-own-link>{{ t('workflow.link.copy_own') }}</button>{% endif %}
```

Commit `0231 step 5`.

### Step 6. `routes/guest.py`: imports

Anchor (exact line, starts with `from .. import alerts, auth, claim,`):

`from .. import alerts, auth, claim, codelists, config, cookie_inventory, db, door_codes, guest_slug, guest_uk_i18n, i18n, incidents, mail, passport_photos, rate_limit, reporting, security, turnstile, validation, validation_i18n`

Replace with:

`from .. import alerts, auth, claim, codelists, config, cookie_inventory, db, door_codes, guest_slug, guest_uk_i18n, host_i18n, i18n, incidents, mail, passport_photos, rate_limit, reporting, security, turnstile, validation, validation_i18n, workflow`

Commit `0231 step 6`.

### Step 7. `routes/guest.py`: the note helper

Anchor (exact line): `def _require_pin(request: Request, token: str, lang: str):`

Insert directly BEFORE it (keep two blank lines around it):

```python
def _host_link_note(request: Request, apartment) -> Optional[str]:
    """0231: the signed-in owner learns why their link is empty.

    Guests keep the neutral text, so no other stay's dates ever reach them.
    """
    if not apartment or not _host_owns_apartment(request, apartment):
        return None
    host_lang = host_i18n.lang_from_request(request)
    upcoming = workflow.next_stay_window(apartment)
    if upcoming["stay"] is not None and upcoming["window"]:
        return host_i18n.translate(
            host_lang,
            "workflow.link.host_note",
            stay=validation.fmt_date_short(upcoming["stay"]["date_from"]),
            date=validation.fmt_date_short(upcoming["window"]["opens"].isoformat()),
        )
    return host_i18n.translate(host_lang, "workflow.link.host_note_none")


```

Commit `0231 step 7`.

### Step 8. `routes/guest.py`: `_unavailable` takes the note

Anchor (these exact lines):

```python
    status_code: int = 404,
    token: Optional[str] = None,
):
    """The one page a guest lands on when there is nothing to fill in.
```

Replace with:

```python
    status_code: int = 404,
    token: Optional[str] = None,
    host_note: Optional[str] = None,
):
    """The one page a guest lands on when there is nothing to fill in.
```

Then anchor (exact line): `            "show_invoice_link": False,`

Replace with:

```python
            "show_invoice_link": False,
            "host_note": host_note,
```

Commit `0231 step 8`.

### Step 9. `routes/guest.py`: pass the note from the picker

Anchor (exact line): `        return _with_lang(_unavailable(request, lang, "no_stays", 200, token), lang)`

Replace with:

```python
        note = _host_link_note(request, apartment)
        return _with_lang(_unavailable(request, lang, "no_stays", 200, token, host_note=note), lang)
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_navigation.py -q --tb=short -x 2>&1 | tail -5` → pass. Commit `0231 step 9`.

### Step 10. `guest/unavailable.html`

Anchor (exact line): `    <p class="g-intro">{{ t(body_key) }}</p>`

Insert directly after it:

```jinja
    {% if host_note %}<p class="g-host-note" role="note" data-host-note>{{ host_note }}</p>{% endif %}
```

Commit `0231 step 10`.

### Step 11. `static/guest.css`

Append at the end of the file:

```css

/* 0231: the owner's own view of an empty guest link. */
.g-host-note { margin: 0 0 16px; padding: 10px 12px; border: 1px dashed #92400e; border-radius: 10px; background: #fffbeb; color: #78350f; font-size: 14px; line-height: 1.45; text-align: left; }
```

Commit `0231 step 11`.

### Step 12. `guest/base.html`

Anchor (exact line): `  <link rel="stylesheet" href="/static/guest.css?v=20261014-0102c">`

Replace with: `  <link rel="stylesheet" href="/static/guest.css?v=20261022-0231">`

Command: `cd App && grep -rn "guest.css?v=20261014-0102c" app tests 2>&1 | tail -5` → nothing (if a test pins the old key, list it in the report; do not edit it). Commit `0231 step 12`.

### Step 13. Create `App/tests/test_guest_link_window_0231.py` with exactly this content

```python
"""0231: the guest-link window is said with the host's own stays."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app import claim, db
from app.main import app
from tests.test_guest_links_bilingual import TOKEN, _apartment_id, host  # noqa: F401


def _stay(apartment_id: int, days_ahead: int) -> int:
    start = claim.prague_today() + timedelta(days=days_ahead)
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": f"wf0231-{days_ahead}",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_the_owner_sees_why_the_guest_link_is_empty(host):  # noqa: F811
    _apartment_id()
    page = host.get(f"/l/{TOKEN}?lang=en")
    assert page.status_code == 200
    assert "data-host-note" in page.text


def test_a_guest_never_sees_the_host_note(host):  # noqa: F811
    _apartment_id()
    page = TestClient(app).get(f"/l/{TOKEN}?lang=en")
    assert "data-host-note" not in page.text


def test_a_far_stay_says_when_it_reaches_the_link_and_offers_its_own_link(host):  # noqa: F811
    apartment_id = _apartment_id()
    reservation_id = _stay(apartment_id, 20)
    page = host.get(f"/reservations/{reservation_id}?lang=en")
    assert page.status_code == 200
    assert 'data-link-window="from"' in page.text
    assert "data-copy-own-link" in page.text
    listing = host.get("/reservations?lang=en")
    assert 'data-link-window="from"' in listing.text


def test_the_property_editor_names_the_next_stay(host):  # noqa: F811
    apartment_id = _apartment_id()
    _stay(apartment_id, 20)
    page = host.get(f"/apartments/{apartment_id}?view=settings&section=guests&lang=en")
    assert "data-link-window-note" in page.text
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_link_window_0231.py -q --tb=short -x 2>&1 | tail -15` → 4 passed. If the last test fails only because the property editor is on another URL, try `/apartments/{apartment_id}?view=settings` once and say so in the report. Commit `0231 step 13`.

## 5. Do not touch

Everything outside §3. `_visible_reservations` and the window default (owner decision). `App/app/workflow.py`. No new strings (0230 owns the copy).

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_guest_link_window_0231.py tests/test_guest_links_preview.py tests/test_guest_navigation.py tests/test_onboarding_wizard_survival.py tests/test_workflow_0230.py -q --tb=short 2>&1 | tail -15`

## 7. Acceptance

- [ ] The 4 new tests pass; the named older tests still pass.
- [ ] The guest page shows the note only to the owner.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0231-report.md` (600 tokens at most) with `git diff --stat` for your commits, each command with its last 5 lines, §7 ticked, deviations, questions. Set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/routes/guest.py` (host-only note, no data leak to guests).

## Owner steps

None.
