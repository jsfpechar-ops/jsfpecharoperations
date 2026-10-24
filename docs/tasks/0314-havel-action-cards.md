# 0314: Havel (AI): confirm cards for the five actions

Status: todo
Depends on: 0324 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0314-havel-action-cards
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When Havel's reply is an action (add a stay, add a cleaning, refresh calendars, make a new PIN, show the guest link), the thread shows a confirm card instead of a link to the form: facts to check, the editable fields behind "Change", Cancel and one verb button that posts to the **existing** route. Havel never writes to the database and never claims success; the page the host lands on shows the normal flash.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 7 (actions table), 17d (cards), 17e (copy keys `havel.card.*`, `havel.reason.*`). Rules: AGENTS.md 6, 7 (390 px screenshot), 9; MASTER 7.1 (buttons: `primary` for the confirm, `danger` only for the PIN, `quiet` for Cancel), 7.5 (card), 10 (never do). No new route: the four write routes below already exist and carry CSRF through `security.protect_host_post` (`_csrf` field, token in `csrf_token`).

Excerpts (verbatim; if one is not found, stop, section 8):

- `App/app/routes/admin.py` line 3096: `@router.post("/reservations")`, fields `apartment_id`, `date_from`, `date_to`, `expected_guests` (1–60), `guest_email`, `host_note`; errors redirect to `/reservations` with `?err=`, success redirects to the stays list. Line 3108: `apartment = access.apartment(request, apartment_id) if apartment_id else None` then `if not apartment or not apartment["active"] or apartment["archived_at"]:`. Line 3127: `    if date_to <= date_from:`.
- `App/app/routes/cleaning.py` line 139: `@router.post("/cleaning/events")`, fields `apartment_id`, `scheduled_date`, `start_time`, `end_time`, `notes`; `_home(request, property_id)` (line 46) raises 404 when the property is not the host's, inactive or archived; success redirects to the cleaning page.
- `App/app/routes/admin.py` line 2453: `@router.post("/apartments/{apartment_id}/regenerate-pin")`; the default `return_to` is `f"/apartments/{apartment_id}?view=settings&section=guests#communication"`, where the new PIN is shown (the PIN never goes into a flash). The form sends only `_csrf`.
- `App/app/routes/admin.py` line 2822: `@router.post("/sync")`, field `return_to` (`_form_return_to(form, "/")`), flashes `flash.feeds.synced`.
- `App/app/routes/dashboard_calendar.py` line 15: `def parse_dates(start: str, end: str) -> tuple[date, date]:`; line 54: `def overlapping_count(apartment_id: int, start: str, end: str) -> int:`.
- `App/app/access.py` line 64: `def apartment(request: Request, apartment_id: int):` returns the full `apartment` row (`id`, `internal_name`, `active`, `archived_at`, `permalink_pin`, `permalink_token`, …) or `None`. `App/app/guest_slug.py` line 144: `def link_key(apartment) -> str:`; the guest link is `f"{config.PUBLIC_BASE_URL}/l/{guest_slug.link_key(apartment)}"`. `App/app/db.py` line 180: table `ical_feed(apartment_id, url, active, …)`.
- `App/app/templating.py` line 379: `templates.env.filters["date_short"] = validation.fmt_date_short`; line 381: `templates.env.filters["weekday"] = _weekday` (`Fri`); `_nights(date_from, date_to)` at line 61 (check whether it is a filter: `grep -n '"nights"' App/app/templating.py`; if not, the card computes nights in Python).
- `App/app/templates/_components.html` line 290: `{% macro copy_button(target_id) %}` renders a quiet icon button with `data-copy="{{ target_id }}"` (app.js copies the element's text or value). `App/app/templates/_ui.html` line 125: `{% macro ui_pdot(index, name) %}` (property identity dot). Button classes: `ui-btn ui-btn-primary|ui-btn-secondary|ui-btn-quiet|ui-btn-danger`, `ui-btn-compact`.
- Copy keys that already exist (0312, en/cs/vi): `havel.card.title_stay|title_cleaning|title_sync|title_pin|title_link`, `havel.card.confirm_stay|confirm_cleaning|confirm_sync|confirm_pin`, `havel.card.change|cancel|nights|guests|pin|copy_link|open_guest_links|overlap|pin_warning|not_prepared|open_form`, `havel.reason.property|dates|no_calendar|no_link|archived`; `stays.add_panel.apartment|arrival|departure|guests|email`. Cleaning words via `cleaning_i18n.translator(lang)`: `property`, `date`, `start`, `end`, `notes`.
- From 0311 (`App/app/havel.py`): `ACTIONS = ("show_guest_link", "create_stay", "create_cleaning", "sync_calendars", "new_pin")`; a validated `Reply.action` dict has the keys `type, property_id, date_from, date_to, guests, guest_email, start_time, end_time, note`, `property_id` already checked for ownership (and filled in when the host has one property), dates ISO, times `HH:MM`, `create_stay` has both dates with `date_to > date_from`, `create_cleaning` has `date_from`.
- From 0312/0313 (`App/app/routes/havel.py`), verbatim, inside `havel_send`:

```python
                        if reply.action:  # 0314 replaces this with the confirm card
                            page_id = ACTION_FALLBACK_PAGE[reply.action["type"]]
                            url = havel.page_url(page_id, reply.action.get("property_id"), host.property_ids)
                            links.append((_t(request, "havel.card.open_form"), url))
                        items.append(_item("havel", reply_text, links=links, support=reply.kind == "escalate",
                                           support_summary=reply.support_summary))
```

  and `_havel_thread.html` has `    {% if item.card %}{% include "_havel_card.html" %}{% endif %}` (the include runs only when a card exists). `_item(role, text, **extra)` puts extra keys on the item dict.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/havel_actions.py | new | checks and card data for the five actions |
| App/app/routes/havel.py | edit | build the card; "not prepared" sentence |
| App/app/templates/_havel_card.html | new | the card |
| App/app/static/host2.css | edit | append card rules; new `?v=` key in base.html |
| App/app/templates/base.html | edit | the CSS key only |
| App/tests/test_havel_actions.py | new | unit and route tests |
| App/tests/test_havel_cards_browser.py | new | card at 390 and 1280, screenshots |
| docs/design/catalog.json | edit | enforced template |
| docs/design/pages/havel.md | edit | card notes |
| docs/tasks/screenshots-0314/*.png | new | |

No other file may change. (`havel-card*` classes were added to the catalog by 0312.)

## 4. Steps

1. **Branch** from the 0324 branch (or `origin/main` once merged): `git checkout -b task/0314-havel-action-cards`. Then `grep -n "0314 replaces this" App/app/routes/havel.py` must print one line, else stop.

2. **Checks and card data.** Create `App/app/havel_actions.py`:

```python
"""Confirm cards for Havel's actions (plan 7 and 17d).

The model proposes; this module checks the proposal against the host's data and
builds what the card shows and posts. The post goes to the existing route, which
checks everything again, so a card is never the only guard. Nothing here writes.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from . import config, guest_slug

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DAYS_BACK = 365
DAYS_AHEAD = 730


class NotPrepared(Exception):
    """The card cannot be built; ``reason`` is the tail of a ``havel.reason.*`` key."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _iso(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _in_window(day: date, today: date) -> bool:
    return today - timedelta(days=DAYS_BACK) <= day <= today + timedelta(days=DAYS_AHEAD)


def _property(action: Dict[str, Any], properties: List[Any]) -> Dict[str, Any]:
    pid = action.get("property_id")
    for index, row in enumerate(properties):
        if int(row["id"]) == pid:
            if not row["active"] or row["archived_at"]:
                raise NotPrepared("archived")
            return {"id": int(row["id"]), "name": row["internal_name"] or f"#{row['id']}", "index": index + 1,
                    "row": row}
    raise NotPrepared("property")


def prepare(action: Dict[str, Any], properties: List[Any], today: date, *, return_to: str,
            overlaps: Callable[[int, str, str], int], feed_count: Callable[[int], int]) -> Dict[str, Any]:
    """Card data for a validated action, or NotPrepared.

    ``properties`` are the host's apartment rows (``access.apartments(request, "*")``),
    in the order the host sees them (the identity dot uses that index).
    """
    kind = action["type"]
    if kind == "sync_calendars":
        if not any(feed_count(int(p["id"])) for p in properties if p["active"] and not p["archived_at"]):
            raise NotPrepared("no_calendar")
        return {"type": kind, "title": "havel.card.title_sync", "confirm": "havel.card.confirm_sync",
                "action": "/sync", "hidden": {"return_to": return_to}, "fields": [], "facts": [], "property": None}

    prop = _property(action, properties)
    if kind == "show_guest_link":
        key = guest_slug.link_key(prop["row"])
        if not key:
            raise NotPrepared("no_link")
        return {"type": kind, "title": "havel.card.title_link", "property": prop,
                "link": f"{config.PUBLIC_BASE_URL}/l/{key}", "pin": prop["row"]["permalink_pin"] or "",
                "guests_url": f"/apartments/{prop['id']}?view=settings&section=guests#communication"}

    if kind == "new_pin":
        return {"type": kind, "title": "havel.card.title_pin", "confirm": "havel.card.confirm_pin", "danger": True,
                "action": f"/apartments/{prop['id']}/regenerate-pin", "hidden": {}, "fields": [], "facts": [],
                "warning": "havel.card.pin_warning", "property": prop}

    start = _iso(action.get("date_from"))
    if not start or not _in_window(start, today):
        raise NotPrepared("dates")

    if kind == "create_cleaning":
        for name in ("start_time", "end_time"):
            if action.get(name) and not _HHMM.match(str(action[name])):
                raise NotPrepared("dates")
        if action.get("start_time") and action.get("end_time") and action["end_time"] <= action["start_time"]:
            raise NotPrepared("dates")
        return {"type": kind, "title": "havel.card.title_cleaning", "confirm": "havel.card.confirm_cleaning",
                "action": "/cleaning/events", "hidden": {"apartment_id": prop["id"]}, "property": prop,
                "date_from": start.isoformat(), "start_time": action.get("start_time") or "",
                "end_time": action.get("end_time") or "", "note": (action.get("note") or "")[:500],
                "fields": [
                    {"name": "scheduled_date", "label": ("cleaning", "date"), "type": "date", "value": start.isoformat()},
                    {"name": "start_time", "label": ("cleaning", "start"), "type": "time", "value": action.get("start_time") or ""},
                    {"name": "end_time", "label": ("cleaning", "end"), "type": "time", "value": action.get("end_time") or ""},
                    {"name": "notes", "label": ("cleaning", "notes"), "type": "text", "value": (action.get("note") or "")[:500]},
                ], "facts": []}

    # create_stay
    end = _iso(action.get("date_to"))
    if not end or end <= start or (end - start).days > 365:
        raise NotPrepared("dates")
    guests = action.get("guests")
    if guests is not None and not 1 <= int(guests) <= 60:
        raise NotPrepared("dates")
    email = (action.get("guest_email") or "").strip()
    if email and not _EMAIL.match(email):
        email = ""
    return {"type": kind, "title": "havel.card.title_stay", "confirm": "havel.card.confirm_stay",
            "action": "/reservations", "hidden": {"host_note": (action.get("note") or "")[:500]}, "property": prop,
            "date_from": start.isoformat(), "date_to": end.isoformat(), "nights": (end - start).days,
            "guests": guests, "guest_email": email,
            "overlap": overlaps(prop["id"], start.isoformat(), end.isoformat()) > 0,
            "fields": [
                {"name": "apartment_id", "label": ("host", "stays.add_panel.apartment"), "type": "select",
                 "value": prop["id"], "options": [(int(p["id"]), p["internal_name"] or f"#{p['id']}")
                                                  for p in properties if p["active"] and not p["archived_at"]]},
                {"name": "date_from", "label": ("host", "stays.add_panel.arrival"), "type": "date", "value": start.isoformat()},
                {"name": "date_to", "label": ("host", "stays.add_panel.departure"), "type": "date", "value": end.isoformat()},
                {"name": "expected_guests", "label": ("host", "stays.add_panel.guests"), "type": "number",
                 "value": guests or "", "min": 1, "max": 60},
                {"name": "guest_email", "label": ("host", "stays.add_panel.email"), "type": "email", "value": email},
            ], "facts": []}
```

   Command: `cd App && .venv/bin/python -c "from app import havel_actions; print(havel_actions.DAYS_AHEAD)"`. Expected: `730`.

3. **Route.** In `App/app/routes/havel.py`:

   a. Import line: `from .. import access, ai, auth, havel, havel_topics, host_i18n, security` → `from .. import access, ai, auth, cleaning_i18n, db, havel, havel_actions, havel_topics, host_i18n, security`. Add `from datetime import date` with the standard-library imports and `from . import dashboard_calendar` after the `from .. import` line (`dashboard_calendar` lives in `App/app/routes/`).

   b. Add after `_properties`:

```python
def _feed_count(apartment_id: int) -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM ical_feed WHERE apartment_id = ? AND active = 1", (apartment_id,))
    return int(row["n"]) if row else 0


def _card(request: Request, action: Dict[str, Any], return_to: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(card, None) or (None, reason sentence)."""
    rows = list(access.apartments(request, "*"))
    try:
        card = havel_actions.prepare(action, rows, date.today(), return_to=return_to,
                                     overlaps=dashboard_calendar.overlapping_count, feed_count=_feed_count)
    except havel_actions.NotPrepared as exc:
        return None, _t(request, "havel.card.not_prepared", reason=_t(request, f"havel.reason.{exc.reason}"))
    card["cleaning_words"] = cleaning_i18n.translator(request.state.lang)
    return card, None
```

   If `access.apartments(request, "*")` excludes archived rows by default (`include_archived=False` at `App/app/access.py` line 141), that is fine: an archived property then raises `NotPrepared("property")` and the sentence says "I'm not sure which property you mean", which is acceptable; note it in the report.

   c. Replace the five lines quoted in section 2 (from `if reply.action:` to the `support_summary=reply.support_summary))` line) with:

```python
                        card = None
                        if reply.action:
                            card, not_prepared = _card(request, reply.action, return_to)
                            if not_prepared:
                                reply_text = f"{reply_text}\n{not_prepared}".strip()
                                page_id = ACTION_FALLBACK_PAGE[reply.action["type"]]
                                url = havel.page_url(page_id, reply.action.get("property_id"), host.property_ids)
                                links.append((_t(request, "havel.card.open_form"), url))
                        items.append(_item("havel", reply_text, links=links, support=reply.kind == "escalate",
                                           support_summary=reply.support_summary, card=card))
```

   d. `_item` must default `card` to `None`: check `grep -n "def _item" -A6 App/app/routes/havel.py`; if the dict it builds has no `"card"` key, add `"card": None,` before `**extra` is applied (so `item.card` is always defined).

   Command: `cd App && .venv/bin/python -c "from app.main import app" && grep -c "havel_actions" app/routes/havel.py`. Expected: no error, `3`.

4. **Card template.** Create `App/app/templates/_havel_card.html`:

```jinja
{#- 0314: a confirm card under Havel's bubble (plan 17d). The facts are what the
    host checks; the real inputs sit behind "Change" (a closed <details> still
    submits its fields). The form posts to the existing route, which validates
    again and redirects with its own flash. Havel never claims success. -#}
{% from "_icons.html" import icon with context %}
{% from "_ui.html" import ui_pdot with context %}
{% from "_components.html" import copy_button with context %}
{% set card = item.card %}
<div class="ui-card havel-card" data-havel-card="{{ card.type }}">
  <p class="havel-card-title">{{ t(card.title) }}</p>
  {% if card.type == 'show_guest_link' %}
  <dl class="havel-card-facts">
    <div><dt class="sr-only">{{ t('stays.add_panel.apartment') }}</dt><dd>{{ ui_pdot(card.property.index, card.property.name) }}</dd></div>
    <div><dt class="sr-only">{{ t('havel.card.title_link') }}</dt><dd class="havel-card-link"><span id="havel-link-{{ card.property.id }}">{{ card.link }}</span>{{ copy_button('havel-link-' ~ card.property.id) }}</dd></div>
    {% if card.pin %}<div><dt>{{ t('havel.card.pin') }}</dt><dd class="havel-card-pin">{{ card.pin }}</dd></div>{% endif %}
  </dl>
  <div class="havel-card-actions"><a class="ui-btn ui-btn-quiet ui-btn-compact" href="{{ card.guests_url }}">{{ t('havel.card.open_guest_links') }}{{ icon('chevron-right', 16) }}</a></div>
  {% else %}
  <form method="post" action="{{ card.action }}" class="havel-card-form">
    <input type="hidden" name="_csrf" value="{{ csrf_token }}">
    {% for name, value in card.hidden.items() %}<input type="hidden" name="{{ name }}" value="{{ value }}">{% endfor %}
    <dl class="havel-card-facts">
      {% if card.property %}<div><dt class="sr-only">{{ t('stays.add_panel.apartment') }}</dt><dd>{{ ui_pdot(card.property.index, card.property.name) }}</dd></div>{% endif %}
      {% if card.date_from %}<div><dt class="sr-only">{{ t('stays.add_panel.arrival') }}</dt><dd>{{ card.date_from | weekday }} {{ card.date_from | date_short }}{% if card.date_to %} – {{ card.date_to | weekday }} {{ card.date_to | date_short }}{% endif %}{% if card.start_time %} · {{ card.start_time }}{% if card.end_time %}–{{ card.end_time }}{% endif %}{% endif %}</dd></div>{% endif %}
      {% if card.nights %}<div><dd>{{ t('havel.card.nights', n=card.nights) }}</dd></div>{% endif %}
      {% if card.guests %}<div><dd>{{ t('havel.card.guests', n=card.guests) }}</dd></div>{% endif %}
      {% if card.guest_email %}<div><dd>{{ card.guest_email }}</dd></div>{% endif %}
      {% if card.note %}<div><dd>{{ card.note }}</dd></div>{% endif %}
    </dl>
    {% if card.overlap %}<p class="havel-card-warning">{{ icon('triangle-alert', 16) }}{{ t('havel.card.overlap') }}</p>{% endif %}
    {% if card.warning %}<p class="havel-card-warning havel-card-danger">{{ icon('triangle-alert', 16) }}{{ t(card.warning) }}</p>{% endif %}
    {% if card.fields %}
    <details class="havel-card-change">
      <summary class="ui-btn ui-btn-quiet ui-btn-compact">{{ t('havel.card.change') }}</summary>
      {% for f in card.fields %}
      {% set label = card.cleaning_words(f.label[1]) if f.label[0] == 'cleaning' else t(f.label[1]) %}
      <label class="ui-field">
        <span>{{ label }}</span>
        {% if f.type == 'select' %}
        <select class="ui-select" name="{{ f.name }}">{% for value, name in f.options %}<option value="{{ value }}"{% if value == f.value %} selected{% endif %}>{{ name }}</option>{% endfor %}</select>
        {% else %}
        <input class="ui-input" type="{{ f.type }}" name="{{ f.name }}" value="{{ f.value }}"{% if f.min is defined %} min="{{ f.min }}"{% endif %}{% if f.max is defined %} max="{{ f.max }}"{% endif %}{% if f.type == 'date' %} required{% endif %}>
        {% endif %}
      </label>
      {% endfor %}
    </details>
    {% endif %}
    <div class="havel-card-actions">
      <button class="ui-btn ui-btn-quiet" type="button" data-havel-cancel>{{ t('havel.card.cancel') }}</button>
      <button class="ui-btn {{ 'ui-btn-danger' if card.danger else 'ui-btn-primary' }}" type="submit">{{ t(card.confirm) }}</button>
    </div>
  </form>
  {% endif %}
</div>
```

   Check the `ui_field`-free markup is allowed: `ui-field`, `ui-input`, `ui-select` are catalog classes (they are, 2026-10-24). If `_ui.html`'s `ui_pdot` macro is named differently, use the real name. Cancel: `havel.js` (0324) handles `[data-havel-cancel]`? It does not yet; add to `App/app/static/havel.js`, inside the `root.addEventListener("click", ...)` handler, before `var retry = ...`:

```js
    var cancel = event.target.closest ? event.target.closest("[data-havel-cancel]") : null;
    if (cancel) { var card = cancel.closest(".havel-card"); if (card) card.remove(); var ta = textarea(); if (ta) ta.focus(); return; }
```

   and bump its key in `base.html`: `havel.js?v=20261024-0324` → `havel.js?v=20261024-0314`. Add `App/app/static/havel.js` to your report's file list (one handler; allowed here). Without JavaScript Cancel does nothing, which is the same as ignoring the card.

   Command: `cd App && .venv/bin/python -c "from app.main import app" && echo ok`.

5. **CSS.** Append to the end of `App/app/static/host2.css`:

```css

/* 0314: Havel confirm cards (plan 17d). A card sits under the bubble, never inside it. */
.host-workspace .havel-card { margin-top: var(--space-2); max-width: 100%; }
.host-workspace .havel-card-title { margin: 0 0 var(--space-2); font-size: var(--size-15); font-weight: 600; color: var(--ink); }
.host-workspace .havel-card-facts { display: flex; flex-direction: column; gap: var(--space-1); margin: 0; }
.host-workspace .havel-card-facts div { display: flex; gap: var(--space-2); align-items: baseline; }
.host-workspace .havel-card-facts dt { font-size: var(--size-13); color: var(--ink-3); }
.host-workspace .havel-card-facts dd { margin: 0; font-size: var(--size-15); color: var(--ink); overflow-wrap: anywhere; }
.host-workspace .havel-card-link { display: flex; align-items: center; gap: var(--space-1); font-family: var(--font-mono); font-size: var(--size-13); }
.host-workspace .havel-card-pin { font-family: var(--font-mono); font-size: var(--size-18); font-weight: 600; letter-spacing: 0.08em; }
.host-workspace .havel-card-warning { display: flex; gap: var(--space-2); align-items: flex-start; margin: var(--space-2) 0 0; font-size: var(--size-13); color: var(--ink-2); }
.host-workspace .havel-card-danger { color: var(--danger); }
.host-workspace .havel-card-change { margin-top: var(--space-2); }
.host-workspace .havel-card-change summary { list-style: none; display: inline-flex; }
.host-workspace .havel-card-change summary::-webkit-details-marker { display: none; }
.host-workspace .havel-card-change[open] summary { margin-bottom: var(--space-2); }
.host-workspace .havel-card-change .ui-field { margin-bottom: var(--space-2); }
.host-workspace .havel-card-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); flex-wrap: wrap; }
```

   Then `sed -i 's/host2.css?v=20261024-0324"/host2.css?v=20261024-0314"/' App/app/templates/base.html && grep -c 'host2.css?v=20261024-0314"' App/app/templates/base.html` (expected `1`), `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`, and from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3` (expected OK; `0.08em` is not a px value).

6. **Catalog and page notes.** From the repo root:

```python
import json
from pathlib import Path
p = Path("docs/design/catalog.json")
c = json.loads(p.read_text(encoding="utf-8"))
for k in ["havel-card-title", "havel-card-actions", "havel-card-form", "havel-card-change", "havel-card-danger"]:
    if k not in c["classes"]:
        c["classes"].append(k)
if "App/app/templates/_havel_card.html" not in c["enforced_templates"]:
    c["enforced_templates"].append("App/app/templates/_havel_card.html")
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("catalog ok")
```

   Append to `docs/design/pages/havel.md`:

```markdown

## Confirm cards (0314)
- `_havel_card.html` under the bubble: title is a question, facts, "Change" `<details>` with the real inputs, Cancel (`quiet`) and the verb button (`primary`; `danger` only for the new PIN). Posts to `/reservations`, `/cleaning/events`, `/apartments/{id}/regenerate-pin`, `/sync`. The guest-link card is read-only (mono link, Copy, PIN 18/600, quiet link to Guest links).
- Checks in `havel_actions.prepare`: property owned, active, not archived; dates ISO, within a year back and two ahead, departure after arrival; guests 1–60; e-mail shape; times HH:MM, end after start; a connected calendar for sync; a link key for the guest link. A failed check adds `havel.card.not_prepared` + `havel.reason.*` to the bubble and a link to the form instead of a card.
```

7. **Unit and route tests.** Create `App/tests/test_havel_actions.py`:

```python
"""0314: confirm cards for Havel's actions."""
from __future__ import annotations

import re
from datetime import date

import pytest

from app import ai, config, db, havel_actions, host_i18n
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import USERNAME, host as host  # noqa: F401

TODAY = date(2026, 10, 23)


def _row(id=11, name="Riverside / 4", active=1, archived=None, pin="482913", token="tok11"):
    return {"id": id, "internal_name": name, "active": active, "archived_at": archived, "permalink_pin": pin,
            "permalink_token": token, "owner_user_id": 1}


def _action(**kw):
    base = {"type": "create_stay", "property_id": 11, "date_from": "2026-10-30", "date_to": "2026-11-01", "guests": 3,
            "guest_email": "guest@example.test", "start_time": None, "end_time": None, "note": None}
    base.update(kw)
    return base


def _prepare(action, rows=None, overlaps=lambda *a: 0, feeds=lambda *a: 1):
    return havel_actions.prepare(action, rows or [_row()], TODAY, return_to="/", overlaps=overlaps, feed_count=feeds)


def test_stay_card_has_facts_fields_and_overlap_flag():
    card = _prepare(_action(), overlaps=lambda *a: 1)
    assert card["action"] == "/reservations" and card["nights"] == 2 and card["guests"] == 3 and card["overlap"]
    assert [f["name"] for f in card["fields"]] == ["apartment_id", "date_from", "date_to", "expected_guests", "guest_email"]
    assert card["property"]["index"] == 1 and card["guest_email"] == "guest@example.test"
    assert _prepare(_action(guest_email="not an e-mail"))["guest_email"] == ""


@pytest.mark.parametrize("bad", [
    {"date_from": "2026-11-01", "date_to": "2026-10-30"},
    {"date_from": "2020-01-01", "date_to": "2020-01-03"},
    {"date_from": "2029-01-01", "date_to": "2029-01-03"},
    {"guests": 0},
    {"date_from": "nope"},
])
def test_bad_stay_values_are_not_prepared(bad):
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(**bad))
    assert exc.value.reason == "dates"


def test_property_checks():
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(property_id=99))
    assert exc.value.reason == "property"
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(), rows=[_row(archived="2026-01-01T00:00:00")])
    assert exc.value.reason == "archived"


def test_cleaning_sync_pin_and_link_cards():
    card = _prepare(_action(type="create_cleaning", date_to=None, start_time="10:00", end_time="12:00", note="Towels"))
    assert card["action"] == "/cleaning/events" and card["hidden"] == {"apartment_id": 11}
    assert [f["name"] for f in card["fields"]] == ["scheduled_date", "start_time", "end_time", "notes"]
    with pytest.raises(havel_actions.NotPrepared):
        _prepare(_action(type="create_cleaning", date_to=None, start_time="12:00", end_time="10:00"))
    card = _prepare(_action(type="sync_calendars", property_id=None))
    assert card["action"] == "/sync" and card["hidden"] == {"return_to": "/"}
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(type="sync_calendars", property_id=None), feeds=lambda *a: 0)
    assert exc.value.reason == "no_calendar"
    card = _prepare(_action(type="new_pin"))
    assert card["action"] == "/apartments/11/regenerate-pin" and card["danger"] and card["hidden"] == {}
    card = _prepare(_action(type="show_guest_link"))
    assert card["link"].endswith("/l/tok11") and card["pin"] == "482913" and "confirm" not in card
    with pytest.raises(havel_actions.NotPrepared) as exc:
        _prepare(_action(type="show_guest_link"), rows=[_row(token="")])
    assert exc.value.reason == "no_link"


# --- through the route ------------------------------------------------------------------

def _reply(action, text="Here is what I prepared."):
    return reply({"kind": "action", "reply": text, "sources": ["guide.stays.body"], "links": [], "action": action,
                  "support_summary": None})


@pytest.fixture
def ready(host, monkeypatch):
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    account = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    pid = db.insert("apartment", {"owner_user_id": account["id"], "internal_name": "Riverside / 4", "active": 1,
                                  "created_at": db.utcnow(), "automation_mode": "manual", "checkin_hour": 15,
                                  "checkout_hour": 11, "permalink_pin": "482913", "permalink_token": "tok-havel"})
    yield host, pid
    ai.set_client_for_tests(None)
    db.execute("DELETE FROM apartment WHERE id = ?", (pid,))


def _send(client, text):
    page = client.get("/havel").text
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
    return client.post("/havel", data={"_csrf": csrf, "message": text, "history": "", "history_sig": "",
                                       "page": "stays", "device": "computer", "topic": "", "q": ""},
                       headers={"X-Havel": "1"})


def test_stay_card_renders_and_posts_to_the_existing_route(ready):
    client, pid = ready
    ai.set_client_for_tests(FakeClient([_reply(_action(property_id=pid, date_from="2026-10-30", date_to="2026-11-01"))]))
    res = _send(client, "Add a stay from Friday to Sunday for 3 guests")
    assert res.status_code == 200
    html = res.text
    assert 'data-havel-card="create_stay"' in html and 'action="/reservations"' in html and 'name="_csrf"' in html
    assert any(host_i18n.translate(lang, "havel.card.nights", n=2) in html for lang in ("en", "cs", "vi"))
    assert 'name="expected_guests"' in html and 'value="3"' in html and "Riverside / 4" in html
    assert html.count("ui-btn-primary") >= 1 and "ui-btn-danger" not in html.split('data-havel-card="create_stay"')[1]
    assert "Open the form" not in html


def test_pin_card_is_red_and_link_card_is_read_only(ready):
    client, pid = ready
    ai.set_client_for_tests(FakeClient([_reply(_action(type="new_pin", property_id=pid)),
                                        _reply(_action(type="show_guest_link", property_id=pid))]))
    html = _send(client, "New PIN please").text
    assert f'action="/apartments/{pid}/regenerate-pin"' in html and "ui-btn-danger" in html and "triangle-alert" in html
    html = _send(client, "Show me the guest link").text
    assert "/l/tok-havel" in html and "482913" in html and "<form" not in html.split('data-havel-card="show_guest_link"')[1]
    assert 'data-copy="havel-link-' in html


def test_not_prepared_falls_back_to_the_sentence_and_the_form_link(ready):
    client, pid = ready
    ai.set_client_for_tests(FakeClient([_reply(_action(type="sync_calendars", property_id=None))]))
    html = _send(client, "Refresh my calendars").text
    assert "data-havel-card" not in html
    assert "No calendar is connected yet" in html or "zatím" in html
    assert "Open the form" in html or "Otevřít formulář" in html
```

   The `_action(property_id=pid, ...)` dict passes 0311's ownership check only when the `host` fixture's user owns the apartment, which the `ready` fixture ensures. Command: `cd App && .venv/bin/python -m pytest tests/test_havel_actions.py tests/test_havel_page.py tests/test_havel_topics.py -q 2>&1 | tail -30`. Expected: all pass. (`USERNAME = "retry-cap-admin"` is at `App/tests/test_submission_retry_cap.py` line 46.)

8. **Browser screenshots** (rule 7). Create `App/tests/test_havel_cards_browser.py` by copying the `origin` fixture and `_context` helper from `tests/test_havel_browser.py` (0324) verbatim, with the FakeClient replies replaced by one stay card and one PIN card (use `_reply` and `_action` from step 7, importing them: `from tests.test_havel_actions import _action, _reply`; the apartment comes from the `ready` fixture, so the `origin` fixture here takes `ready` instead of `host` and yields `ready[0].cookies.get(auth.SESSION_COOKIE)`), and these tests:

```python
def test_cards_at_390_and_1280(origin):
    SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0314"
    SHOTS.mkdir(parents=True, exist_ok=True)
    for width in (390, 1280):
        with sync_api.sync_playwright() as pw:
            browser, context = _context(pw, origin, width)
            page = context.new_page()
            page.goto(origin[0] + "/havel")
            page.fill("#havel-message", "Add a stay from Friday to Sunday for 3 guests")
            page.keyboard.press("Enter")
            page.locator("[data-havel-card='create_stay']").wait_for()
            card = page.locator("[data-havel-card='create_stay']")
            assert card.locator("form[action='/reservations'] input[name='_csrf']").count() == 1
            assert not card.locator("input[name='date_from']").is_visible()
            card.locator("summary").click()
            assert card.locator("input[name='date_from']").is_visible()
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            page.screenshot(path=str(SHOTS / f"card-stay-{width}.png"), full_page=True)
            card.locator("[data-havel-cancel]").click()
            assert page.locator("[data-havel-card='create_stay']").count() == 0
            assert page.evaluate("document.activeElement.id") == "havel-message"
            browser.close()


def test_pin_card_confirm_lands_on_the_guest_links_card(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/havel")
        page.fill("#havel-message", "Make a new PIN")
        page.keyboard.press("Enter")
        page.locator("[data-havel-card='new_pin']").wait_for()
        assert page.locator("[data-havel-card='new_pin'] .ui-btn-danger").count() == 1
        page.screenshot(path=str(Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0314" / "card-pin-390.png"))
        page.locator("[data-havel-card='new_pin'] .ui-btn-danger").click()
        page.wait_for_url("**/apartments/*view=settings*section=guests*")
        browser.close()
```

   The FakeClient queue must hold the stay reply twice (390 and 1280) and then the PIN reply, in that order, or give each test its own fixture instance (the `origin` fixture is function-scoped, so set the queue per test with `ai.set_client_for_tests(...)` at the top of each test, before `page.goto`). Commands, from `App/` with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`: `.venv/bin/python -m pytest tests/test_havel_cards_browser.py -q 2>&1 | tail -30` (expected 2 passed, 0 skipped; three PNGs; look at each once: the card's title is a question, the fields are hidden until Change, the PIN button is the only red element).

## 5. Do not touch

`App/app/ai.py`, `App/app/havel.py`, `App/app/havel_prompt.py`, `App/app/havel_topics.py`, `App/app/routes/admin.py`, `App/app/routes/cleaning.py`, `App/app/routes/dashboard_calendar.py` (the routes are used, never changed), migrations, `requirements*.txt`, `tokens.css`, `shell.js`, `app.js`, `host.js`. No write to the database from Havel's code, no success message from Havel, no `danger` button except the PIN, no new copy keys (all exist from 0312), no push.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -c "from app.main import app" && echo import-ok` → `import-ok`.
2. `.venv/bin/python -m pytest tests/test_havel_actions.py tests/test_havel_page.py tests/test_havel_topics.py tests/test_havel_engine.py -q 2>&1 | tail -30` → all passed.
3. `.venv/bin/python -m pytest tests/test_havel_cards_browser.py tests/test_havel_browser.py -q 2>&1 | tail -30` → passed, 0 skipped.
4. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_static_versions.py -q 2>&1 | tail -30` → passed, 0 skipped.
5. Repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] An action reply shows a card under the bubble: question title, property dot, dates with weekday, nights, guests, e-mail; the inputs appear only after "Change"; Cancel (quiet) removes the card and returns focus to the box; the confirm button is `primary` and posts, with `_csrf`, to the existing route; the host lands on that route's page with its normal flash.
- [ ] The PIN card has the red warning and a `danger` button; after confirming, the browser lands on the property's Guest links card where the new PIN is visible; nothing else in Havel is red.
- [ ] The guest-link card has no form: mono link with Copy, PIN in mono, quiet link to Guest links.
- [ ] Sync without any connected calendar, an unknown or archived property, impossible dates: no card, the bubble gets `havel.card.not_prepared` with the reason and a link to the form.
- [ ] Three screenshots in `docs/tasks/screenshots-0314/`, looked at; guards pass, 0 skipped; design lint OK; static manifest written.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: the five quoted route lines are not in `routes/havel.py` (0313/0324 not merged), `access.apartments(request, "*")` does not accept `"*"`, the `weekday`/`date_short` filters are missing, `_components.html` has no `copy_button`, or any existing route needs a change to accept the card's fields (then stop; the card adapts to the route, never the other way).

## 9. Report

Write `docs/tasks/0314-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, one sentence per screenshot.

## Risk list (for the reviewer)

`App/app/havel_actions.py` (every check; the e-mail regex; the date window), `App/app/templates/_havel_card.html` (CSRF field, no autofocus, no success wording, `danger` only on the PIN), `App/app/routes/havel.py` (the card path and the fallback), the `havel.js` cancel handler.

## Owner steps

1. On staging, open Havel and write "Add a stay at Riverside from Friday to Sunday for 2 guests". A card appears. Click "Change", check the dates, click "Add stay". You land on Stays and the green message says the stay was added. Check the stay is there.
2. Write "Make a new PIN for Riverside". The card's warning is red. Click "Make a new PIN". You land on the property's Guest links card with the new PIN. Tell the guests who are registering right now.
3. Write "Refresh the calendars" on a property with no calendar: Havel says no calendar is connected and offers the form. That is the expected answer, not a bug.
4. Write "Show me the guest link": copy it with the Copy button and open it in a private window; the guest page should open.
