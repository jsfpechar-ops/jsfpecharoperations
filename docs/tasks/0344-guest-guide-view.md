# 0344: Guest side of the guest guide (stay link and QR page)

Status: todo
Depends on: 0343 merged | Base commit: after 0343 | Branch: task/0294-guest-guide-view
Executor: Haiku 5.5 (critical: Fable reviews the diff before merge) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give guests the guide through two read-only doors: "Your guide" behind the stay link (booked cards from the day before check-in until the checkout day, the everyone level outside that window) and a public QR page per property that shows everyone cards only, behind an unguessable token the host can rotate later (0345). Photos are served to a guest only for a card that guest level may read; both pages are no-index, no-referrer, no-store ([plan](../plans/guest-guide.md)).

## 2. Context

- Data gate: `guest_guide.for_guest(apartment_id, level)` (0341) returns only `state == 'done'` cards of the allowed visibility and nothing while `progress()["live"]` is false. The routes here never filter cards themselves; they call it, and serve a photo only when its card is in that list.
- The stay door reuses the stay page's own guards from `App/app/routes/guest.py`: `_open_link` (bad link 404, slug redirect), `_require_pin`, `_reservation_for_guest`, `claim.guest_access_open`, and the claim or device check that `stay_overview` makes when mail is on. These are module-private names imported on purpose, so the guide can never be reached by a stay the stay page would refuse.
- Window rule (owner decision 2026-10-24): `booked` when `date_from - 1 day <= today <= date_to`, with `today = claim.prague_today()`, the same Czech civil date the stay picker uses. Hours are ignored: a guest on the checkout evening still reads the checkout card.
- QR token: `apartment.guide_token` (migration 0014), `secrets.token_urlsafe(24)` = 192 bits, created when the host first opens the guide page, matched exactly, so a rotated token is a plain 404 with no detail. It is never `permalink_token`: the public page must not open a registration form, and the privacy link (which carries the stay token) is left off the QR page.
- Guest copy: every key in `App/app/i18n.py` must exist in en, cs, de, es, fr and in `App/app/guest_uk_i18n.py` (`tests/test_guest_languages.py::test_every_guest_key_exists_in_all_five_languages`, same placeholders). Card and topic titles are host copy (`guest_guide.kind.<kind>.title`, `guest_guide.topic.<topic>`, en and cs); the other guest languages read them in English until 0353 translates the guide.
- Guest pages: rule 7 of AGENTS.md (browser test, 0 skipped, one 390 px screenshot per changed page). `guest.css` change: new `?v=` key in `templates/guest/base.html`, then `tests/test_static_versions.py --write`. Tokens only (`--g-*`, defined in the `:root` block of `guest.css`).
- Rate limit: GETs on the QR page count against `rate_limit` scope `guide_qr`, keyed on the peer address, 120 per 15 minutes; photos are not counted. The stay door keeps the stay page's PIN and claim gates.
- Privacy: no guest data is written or logged by these routes. Hard rules 2, 3, 5, 6 and 7 apply.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0014_guide_token.sql` | create | `apartment.guide_token` plus unique index |
| `App/app/guide_token.py` | create | `ensure`, `rotate`, `current`, `apartment_for` |
| `App/app/routes/guest_guide_view.py` | create | Both doors, photo serving, headers, rate limit |
| `App/app/templates/guest/guide.html` | create | The guide page (both doors, not-ready state) |
| `App/tests/test_guest_guide_view.py` | create | Route tests |
| `App/tests/test_guest_guide_browser.py` | create | 390 px layout check and screenshots of the QR page |
| `App/app/i18n.py` | edit | 12 keys in en, cs, de, es, fr |
| `App/app/guest_uk_i18n.py` | edit | The same 12 keys in uk |
| `App/app/templates/guest/base.html` | edit | Three blocks, new `guest.css?v=` key |
| `App/app/templates/guest/stay.html` | edit | One link to the guide |
| `App/app/static/guest.css` | edit | Two tokens, one rule block at the end |
| `App/app/main.py` | edit | Register the router |
| `App/app/routes/guest_guide.py` | edit | `guide_token.ensure` on the host guide page |
| `App/tests/static_versions.json` | regenerate | `tests/test_static_versions.py --write` |

No other file may change.

## 4. Steps

### Step 1: migration

Create `App/app/migrations/0014_guide_token.sql`. The number is fixed (0015 and later are reserved).

```sql
-- Brief 0344: the public QR door of the guest guide (plan: docs/plans/guest-guide.md).
--
-- apartment.guide_token: the unguessable key in the QR code at the property
-- (/g/{token}). Separate from permalink_token, which opens the stay link and
-- the registration form: the QR token only ever shows "everyone" cards and
-- the host can rotate it (brief 0345) without breaking the stay links.
-- NULL until the host first opens the guide page.
ALTER TABLE apartment ADD COLUMN guide_token TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_apartment_guide_token ON apartment (guide_token) WHERE guide_token IS NOT NULL;
```

Command: `.venv/bin/python -m pytest tests/test_migrations.py -q --tb=short 2>&1 | tail -5`. Expected: 0 failed.

### Step 2: `App/app/guide_token.py` (new)

```python
"""The QR token of a property's guest guide (brief 0344).

One token per property, 192 random bits, stored in ``apartment.guide_token``.
It opens ``/g/{token}``: the "everyone" cards only, for anyone standing at the
property. It is never the stay link token, so rotating it (brief 0345) does not
break a single stay link, and a leaked QR photo never opens a registration form.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from . import db

TOKEN_BYTES = 24  # 192 bits, 32 url-safe characters


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def current(apartment_id: int) -> Optional[str]:
    row = db.query_one("SELECT guide_token FROM apartment WHERE id = ?", (apartment_id,))
    return row["guide_token"] if row and row["guide_token"] else None


def ensure(apartment_id: int) -> str:
    """The property's token, created on first use. Never replaces one that exists."""
    token = current(apartment_id)
    if token:
        return token
    token = new_token()
    db.execute(
        "UPDATE apartment SET guide_token = ? WHERE id = ? AND guide_token IS NULL",
        (token, apartment_id),
    )
    return current(apartment_id) or token


def rotate(apartment_id: int) -> str:
    """A fresh token; the old QR code stops working at once (UI in brief 0345)."""
    token = new_token()
    db.update("apartment", apartment_id, {"guide_token": token})
    return token


def apartment_for(token: str) -> Optional[Dict[str, Any]]:
    """The live property behind a QR token, or None for anything else.

    Length-checked first so a database lookup never runs for junk, and the
    row is matched exactly: an old, rotated token matches nothing.
    """
    if not token or len(token) > 64:
        return None
    row = db.query_one(
        "SELECT * FROM apartment WHERE guide_token = ? AND active = 1 AND archived_at IS NULL",
        (token,),
    )
    return dict(row) if row else None
```

### Step 3: `App/app/routes/guest_guide_view.py` (new)

```python
"""The guest side of the guest guide (brief 0344): two read-only doors.

* ``/l/{token}/{reservation_id}/guide``: "Your guide" for a booked guest, behind
  the same link, PIN and claim checks as the stay page. "booked" cards from the
  day before check-in until checkout; the "everyone" level outside that window.
* ``/g/{token}``: the QR code at the property. "everyone" cards only, for
  anyone who scanned it. The token is ``apartment.guide_token`` (guide_token.py),
  never the stay link token.

Both doors render only what ``guest_guide.for_guest`` returns (confirmed cards
of the allowed visibility, nothing until the guide is live) and serve a photo
only when its card is in that list. Nothing here writes guest data or logs it.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from .. import claim, guest_guide, guide_photos, guide_token, host_i18n, mail, rate_limit
from ..templating import render_guest
from .guest import (
    _device_holds_claim,
    _host_owns_apartment,
    _language,
    _open_link,
    _require_pin,
    _reservation_for_guest,
    _shared,
    _unavailable,
    _with_lang,
)

router = APIRouter()

# A QR page is public, so one address gets a generous but finite number of
# page views per rate_limit window (15 minutes). Photos are not counted.
QR_MAX_VIEWS = 120

HARDEN = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
}
PHOTO_HEADERS = {
    "Cache-Control": "private, max-age=3600",
    "X-Robots-Tag": "noindex",
    "Referrer-Policy": "no-referrer",
}


def booked_level(reservation, today: Optional[date] = None) -> str:
    """"booked" from the day before check-in through the checkout day, else "everyone"."""
    today = today or claim.prague_today()
    try:
        date_from = date.fromisoformat(reservation["date_from"])
        date_to = date.fromisoformat(reservation["date_to"])
    except (TypeError, ValueError):
        return "everyone"
    if date_from - timedelta(days=1) <= today <= date_to:
        return "booked"
    return "everyone"


def _copy_lang(lang: str) -> str:
    """Card and topic titles are host copy (en, cs); other guest languages read English."""
    return "cs" if lang == "cs" else "en"


def _cards(apartment_id: int, level: str, lang: str, photo_url) -> List[Dict[str, Any]]:
    hl = _copy_lang(lang)
    out = []
    for item in guest_guide.for_guest(apartment_id, level):
        title = item["title"] if item["kind"] == "custom" else host_i18n.translate(hl, f"guest_guide.kind.{item['kind']}.title")
        out.append(
            {
                "id": item["id"],
                "topic": item["topic"],
                "title": title,
                "location": item["location"],
                "steps": [line.strip() for line in item["steps"].splitlines() if line.strip()],
                "watch_out": item["watch_out"],
                "video_url": item["video_url"] if item["video_url"].startswith("https://") else "",
                "photos": [photo_url(item["id"], p["id"]) for p in guide_photos.photos(apartment_id, item["id"])],
            }
        )
    return out


def _groups(cards: List[Dict[str, Any]], lang: str):
    hl = _copy_lang(lang)
    groups = []
    for topic in guest_guide.TOPICS:
        mine = [c for c in cards if c["topic"] == topic]
        if mine:
            groups.append({"title": host_i18n.translate(hl, f"guest_guide.topic.{topic}"), "cards": mine})
    return groups


def _page(request: Request, lang: str, apartment, context: Dict[str, Any], level: str, photo_url, back_url: str = ""):
    live = guest_guide.progress(apartment["id"])["live"]
    cards = _cards(apartment["id"], level, lang, photo_url) if live else []
    context.update(
        {
            "not_ready": not live,
            "level": level,
            "groups": _groups(cards, lang),
            "back_url": back_url,
        }
    )
    response = render_guest(request, "guest/guide.html", context)
    response.headers.update(HARDEN)
    return _with_lang(response, lang)


def _photo(apartment_id: int, level: str, item_id: int, photo_id: int):
    """The file, only when the card is one this level may read; else a bare 404."""
    if not any(item["id"] == item_id for item in guest_guide.for_guest(apartment_id, level)):
        return None
    photo = guide_photos.get(apartment_id, item_id, photo_id)
    path = guide_photos.path_for(photo) if photo else None
    if not path or not path.is_file():
        return None
    return FileResponse(path, media_type="image/jpeg", headers=PHOTO_HEADERS)


def _not_found(request: Request, lang: str, status_code: int = 404):
    response = _unavailable(request, lang, "bad_link", status_code)
    response.headers.update(HARDEN)
    return response


# --- the stay link door -------------------------------------------------------

def _stay_gate(request: Request, token: str, reservation_id: int):
    """Same checks as the stay page. Returns (apartment, reservation, lang, early response)."""
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return None, None, token, lang, early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return None, None, token, lang, pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return None, None, token, lang, _unavailable(request, lang, "stay_gone", 404, token)
    claim_row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, claim_row):
        return None, None, token, lang, _unavailable(request, lang, "stay_gone", 404, token)
    if mail.mail_enabled() and not _host_owns_apartment(request, apartment):
        if not claim.is_claimed(claim_row) or not _device_holds_claim(request, reservation["id"], claim_row):
            # The stay page explains the claim step; the guide waits behind it.
            stay = RedirectResponse(f"/l/{token}/{reservation['id']}?lang={lang}", status_code=303)
            return None, None, token, lang, stay
    return apartment, reservation, token, lang, None


@router.get("/l/{token}/{reservation_id}/guide")
def stay_guide(token: str, reservation_id: int, request: Request):
    apartment, reservation, token, lang, early = _stay_gate(request, token, reservation_id)
    if early:
        return early
    level = booked_level(reservation)
    base = f"/l/{token}/{reservation['id']}"
    context = _shared(request, token, lang, apartment)
    context.update({"apartment": apartment, "reservation": reservation, "door": "stay"})
    return _page(
        request, lang, apartment, context, level,
        lambda item_id, photo_id: f"{base}/guide/photos/{item_id}/{photo_id}",
        back_url=f"{base}?lang={lang}",
    )


@router.get("/l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}")
def stay_guide_photo(token: str, reservation_id: int, item_id: int, photo_id: int, request: Request):
    apartment, reservation, token, lang, early = _stay_gate(request, token, reservation_id)
    if early:
        return early
    return _photo(apartment["id"], booked_level(reservation), item_id, photo_id) or _not_found(request, lang)


# --- the QR door ----------------------------------------------------------------

def _qr_apartment(request: Request, token: str):
    lang = _language(request)
    key = rate_limit.client_key(request, "guide_qr")
    if rate_limit.blocked("guide_qr", key, QR_MAX_VIEWS):
        return None, lang, _not_found(request, lang, 429)
    apartment = guide_token.apartment_for(token)
    if not apartment:
        return None, lang, _not_found(request, lang)
    return apartment, lang, None


@router.get("/g/{token}")
def qr_guide(token: str, request: Request):
    apartment, lang, early = _qr_apartment(request, token)
    if early:
        return early
    rate_limit.record("guide_qr", rate_limit.client_key(request, "guide_qr"))
    context = _shared(request, "", lang, apartment)
    # No stay link on a public page: the privacy notice link carries the stay token.
    context.update({"token": "", "privacy_url": None, "door": "qr"})
    # A QR sticker outlives every stay: anyone who scans it sees the host's name,
    # never the phone or e-mail (owner, 2026-10-24). Booked guests get those on the stay page.
    context["host"] = {"name": (context.get("host") or {}).get("name", "")}
    return _page(
        request, lang, apartment, context, "everyone",
        lambda item_id, photo_id: f"/g/{token}/photos/{item_id}/{photo_id}",
    )


@router.get("/g/{token}/photos/{item_id}/{photo_id}")
def qr_guide_photo(token: str, item_id: int, photo_id: int, request: Request):
    apartment, lang, early = _qr_apartment(request, token)
    if early:
        return early
    return _photo(apartment["id"], "everyone", item_id, photo_id) or _not_found(request, lang)
```

### Step 4: register the router in `App/app/main.py`

Anchor (once): `guest_guide as guest_guide_routes, invoices` becomes `guest_guide as guest_guide_routes, guest_guide_view, invoices`.

Anchor (once): `app.include_router(guest_guide_routes.router)`. Add directly after it:

```python
app.include_router(guest_guide_view.router)
```

### Step 5: create the token from the host guide page, `App/app/routes/guest_guide.py`

Anchor (once): `from .. import access, auth, guest_guide, guide_photos, security, templating` becomes `from .. import access, auth, guest_guide, guide_photos, guide_token, security, templating`.

Anchor (once), in `guide_index`:

```python
    guest_guide.ensure_defaults(apartment)
    rows = guest_guide.items(apartment_id)
```

becomes

```python
    guest_guide.ensure_defaults(apartment)
    guide_token.ensure(apartment_id)
    rows = guest_guide.items(apartment_id)
```

### Step 6: guest base template blocks, `App/app/templates/guest/base.html`

Three anchors, each once:

- `<title>{{ t('title') }}</title>` becomes `<title>{% block title %}{{ t('title') }}{% endblock %}</title>`
- `        <h1>{{ t('title') }}</h1>` becomes `        <h1>{% block heading %}{{ t('title') }}{% endblock %}</h1>`
- the footer:

```html
  <div class="g-foot">
    <p>{{ t('privacy') }}</p>
    <p>{{ t('privacy_first_line') }}</p>
    {% if privacy_url %}<p><a href="{{ privacy_url }}">{{ t('privacy_link') }}</a></p>{% endif %}
  </div>
```

becomes

```html
  <div class="g-foot">
    {% block foot %}
    <p>{{ t('privacy') }}</p>
    <p>{{ t('privacy_first_line') }}</p>
    {% if privacy_url %}<p><a href="{{ privacy_url }}">{{ t('privacy_link') }}</a></p>{% endif %}
    {% endblock %}
  </div>
```

Leave the `guest.css?v=` key for step 10.

### Step 7: `App/app/templates/guest/guide.html` (new)

```html
{% extends "guest/base.html" %}
{% block title %}{{ t('guide_title') }}{% endblock %}
{% block heading %}{{ t('guide_title') }}{% endblock %}
{% block foot %}
  {% if door == 'qr' %}<p>{{ t('guide_qr_foot') }}</p>{% else %}{{ super() }}{% endif %}
{% endblock %}
{% block content %}

{% if back_url %}
  <a class="g-back" href="{{ back_url }}">{{ t('guide_back_to_stay') }}</a>
{% endif %}

{% if not_ready %}
  <div class="g-card" data-guide-not-ready>
    <h2>{{ t('guide_not_ready_title') }}</h2>
    <p class="g-intro" style="margin-bottom:0">{{ t('guide_not_ready_help') }}</p>
  </div>
{% else %}
  {% if door == 'stay' and level == 'everyone' %}
    <p class="g-intro" data-guide-window-note>{{ t('guide_more_from_arrival') }}</p>
  {% endif %}
  {% if not groups %}
    <div class="g-card" data-guide-empty>
      <p class="g-intro" style="margin-bottom:0">{{ t('guide_empty') }}</p>
    </div>
  {% endif %}
  {% for group in groups %}
    <p class="g-question-kicker" data-guide-topic>{{ group.title }}</p>
    {% for card in group.cards %}
      <div class="g-card g-guide-card" data-guide-card="{{ card.id }}">
        <h2>{{ card.title }}</h2>
        {% if card.location %}<p class="g-guide-where"><span>{{ t('guide_where') }}</span> {{ card.location }}</p>{% endif %}
        {% if card.steps %}
          <ol class="g-guide-steps">
            {% for step in card.steps %}<li>{{ step }}</li>{% endfor %}
          </ol>
        {% endif %}
        {% if card.watch_out %}
          <div class="g-guide-warn" role="note"><strong>{{ t('guide_watch_out') }}</strong> {{ card.watch_out }}</div>
        {% endif %}
        {% if card.photos %}
          <div class="g-guide-photos">
            {% for url in card.photos %}
              <a href="{{ url }}"><img src="{{ url }}" alt="{{ t('guide_photo_alt', n=loop.index) }}" loading="lazy"></a>
            {% endfor %}
          </div>
        {% endif %}
        {% if card.video_url %}
          <p class="g-guide-video"><a href="{{ card.video_url }}" rel="noopener noreferrer" target="_blank">{{ t('guide_video') }}</a></p>
        {% endif %}
      </div>
    {% endfor %}
  {% endfor %}
{% endif %}

{% endblock %}
```

### Step 8: the link on the stay page, `App/app/templates/guest/stay.html`

Anchor (once):

```html
<div class="g-card g-stay-summary">
  <strong>{{ reservation.date_from | date_cz }} &ndash; {{ reservation.date_to | date_cz }}</strong>
  <span>{{ nights_label(reservation.date_from, reservation.date_to) }}</span>
</div>
```

Add directly after it (one blank line, then the link):

```html

<a class="g-card g-guide-link" href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}" data-guide-link>{{ t('guide_title') }}</a>
```

### Step 9: guest copy

`App/app/i18n.py`: in each of the five language tables, find the line `"privacy_door_code_title": ...` (one per language; en is line 659 in the current file: `        "privacy_door_code_title": "Door code",`, cs `"Kód ke dveřím"`, de `"Türcode"`, es `"Código de la puerta"`, fr `"Code de porte"`) and insert the language's block directly after that line, with the same eight-space indent.

en:

```python
        # 0344: the guest guide pages.
        "guide_title": "Your guide",
        "guide_back_to_stay": "Back to your stay",
        "guide_not_ready_title": "This guide is not ready yet",
        "guide_not_ready_help": "The host is still writing it. In the meantime, ask the host directly.",
        "guide_more_from_arrival": "More instructions appear here from the day before your arrival until checkout.",
        "guide_empty": "The host has not added instructions yet.",
        "guide_where": "Where:",
        "guide_watch_out": "Watch out:",
        "guide_video": "Watch the video",
        "guide_qr_foot": "This page shows the host's instructions for this property. Nothing about you is stored here.",
        "guide_photo_alt": "Photo %(n)s",
```

cs:

```python
        # 0344: the guest guide pages.
        "guide_title": "Váš průvodce",
        "guide_back_to_stay": "Zpět na váš pobyt",
        "guide_not_ready_title": "Tento průvodce ještě není hotový",
        "guide_not_ready_help": "Hostitel ho teprve píše. Zatím se zeptejte hostitele přímo.",
        "guide_more_from_arrival": "Další pokyny se tu objeví ode dne před vaším příjezdem až do odjezdu.",
        "guide_empty": "Hostitel zatím žádné pokyny nepřidal.",
        "guide_where": "Kde:",
        "guide_watch_out": "Pozor:",
        "guide_video": "Přehrát video",
        "guide_qr_foot": "Tato stránka ukazuje pokyny hostitele k tomuto ubytování. Nic o vás se tu neukládá.",
        "guide_photo_alt": "Fotka %(n)s",
```

de:

```python
        # 0344: the guest guide pages.
        "guide_title": "Ihr Guide",
        "guide_back_to_stay": "Zurück zu Ihrem Aufenthalt",
        "guide_not_ready_title": "Dieser Guide ist noch nicht fertig",
        "guide_not_ready_help": "Der Gastgeber schreibt ihn noch. Fragen Sie den Gastgeber in der Zwischenzeit direkt.",
        "guide_more_from_arrival": "Weitere Hinweise erscheinen hier ab dem Tag vor Ihrer Anreise bis zum Check-out.",
        "guide_empty": "Der Gastgeber hat noch keine Hinweise hinzugefügt.",
        "guide_where": "Wo:",
        "guide_watch_out": "Achtung:",
        "guide_video": "Video ansehen",
        "guide_qr_foot": "Diese Seite zeigt die Hinweise des Gastgebers zu dieser Unterkunft. Es wird nichts über Sie gespeichert.",
        "guide_photo_alt": "Foto %(n)s",
```

es:

```python
        # 0344: the guest guide pages.
        "guide_title": "Su guía",
        "guide_back_to_stay": "Volver a su estancia",
        "guide_not_ready_title": "Esta guía aún no está lista",
        "guide_not_ready_help": "El anfitrión todavía la está escribiendo. Mientras tanto, pregunte directamente al anfitrión.",
        "guide_more_from_arrival": "Aquí aparecerán más instrucciones desde el día anterior a su llegada hasta la salida.",
        "guide_empty": "El anfitrión aún no ha añadido instrucciones.",
        "guide_where": "Dónde:",
        "guide_watch_out": "Atención:",
        "guide_video": "Ver el vídeo",
        "guide_qr_foot": "Esta página muestra las instrucciones del anfitrión para este alojamiento. Aquí no se guarda nada sobre usted.",
        "guide_photo_alt": "Foto %(n)s",
```

fr:

```python
        # 0344: the guest guide pages.
        "guide_title": "Votre guide",
        "guide_back_to_stay": "Retour à votre séjour",
        "guide_not_ready_title": "Ce guide n'est pas encore prêt",
        "guide_not_ready_help": "L'hôte est encore en train de l'écrire. En attendant, demandez directement à l'hôte.",
        "guide_more_from_arrival": "D'autres consignes apparaîtront ici à partir de la veille de votre arrivée et jusqu'au départ.",
        "guide_empty": "L'hôte n'a pas encore ajouté de consignes.",
        "guide_where": "Où :",
        "guide_watch_out": "Attention :",
        "guide_video": "Voir la vidéo",
        "guide_qr_foot": "Cette page présente les consignes de l'hôte pour ce logement. Rien vous concernant n'y est enregistré.",
        "guide_photo_alt": "Photo %(n)s",
```

`App/app/guest_uk_i18n.py`: anchor (once) `    "privacy_door_code_title": "Код від дверей",`. Insert directly after it (four-space indent):

```python
    # 0344: the guest guide pages.
    "guide_title": "Ваш путівник",
    "guide_back_to_stay": "Назад до вашого проживання",
    "guide_not_ready_title": "Цей путівник ще не готовий",
    "guide_not_ready_help": "Господар ще пише його. Поки що зверніться до господаря напряму.",
    "guide_more_from_arrival": "Додаткові інструкції з'являться тут від дня перед вашим приїздом і до виїзду.",
    "guide_empty": "Господар ще не додав інструкцій.",
    "guide_where": "Де:",
    "guide_watch_out": "Увага:",
    "guide_video": "Переглянути відео",
    "guide_qr_foot": "Ця сторінка показує інструкції господаря щодо цього помешкання. Нічого про вас тут не зберігається.",
    "guide_photo_alt": "Фото %(n)s",
```

Command: `.venv/bin/python -m pytest tests/test_guest_languages.py -q --tb=short 2>&1 | tail -5`. Expected: 0 failed.

### Step 10: `App/app/static/guest.css`, then the cache key

Anchor (once) in the `:root` block: `  --g-bad-soft: var(--red-bg);`. Add directly after it:

```css
  --g-warn: var(--warn);
  --g-warn-soft: var(--warn-soft);
```

Append at the end of the file (after the `.g-host-note` rule):

```css

/* 0344: the guest guide cards (stay link and QR page). */
.g-guide-where { margin: 0 0 12px; font-size: 14.5px; color: var(--g-ink-2); }
.g-guide-where span { color: var(--g-muted); }
.g-guide-steps { margin: 0 0 14px; padding-left: 22px; font-size: 16px; line-height: 1.5; color: var(--g-ink); }
.g-guide-steps li { margin: 0 0 8px; padding-left: 4px; }
.g-guide-warn { margin: 0 0 14px; padding: 10px 12px; border-left: 3px solid var(--g-warn); border-radius: var(--g-radius-sm); background: var(--g-warn-soft); color: var(--g-ink); font-size: 14.5px; line-height: 1.45; }
.g-guide-photos { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 0 0 14px; }
.g-guide-photos img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: var(--g-radius-sm); border: 1px solid var(--g-line); }
.g-guide-video { margin: 0; font-size: 15px; }
.g-guide-video a { color: var(--g-accent); font-weight: 600; }
.g-guide-card h2 { font-size: 19px; }
.g-guide-link { display: block; padding: 16px 20px; text-decoration: none; font-size: 16.5px; font-weight: 600; color: var(--g-accent); }
.g-guide-link::after { content: " \2192"; }
```

Then in `App/app/templates/guest/base.html`, anchor (once) `guest.css?v=20261022-0231` becomes `guest.css?v=20261024-0294`. Then, from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -2`. Expected: `wrote .../tests/static_versions.json (35 files)`. If it prints `refusing`, the CSS changed after the key was set: do not edit the CSS again, just run the command once more after checking the key is in place.

### Step 11: `App/tests/test_guest_guide_view.py` (new)

```python
"""0344: the guest side of the guest guide, both doors."""
from __future__ import annotations

import io
import pathlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, claim, config, db, guest_guide, guide_photos, guide_token, mail, rate_limit
from app.main import app
from app.routes.guest_guide_view import QR_MAX_VIEWS, booked_level
from tests.conftest import login_as

TOKEN = "guideviewtok0344"
TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "app" / "templates" / "guest"


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (640, 480), (120, 90, 60)).save(out, format="JPEG")
    return out.getvalue()


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "guide.sqlite3")
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    monkeypatch.setattr(guide_photos, "PHOTOS_DIR", tmp_path / "guide_photos")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("view-owner@example.test", "View owner", username="view-owner", role="host")
    other = auth.create_account("view-other@example.test", "Other owner", username="view-other", role="host")
    now = db.utcnow()

    def home(name, user, token):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", "permalink_token": token, "permalink_window_days": 14,
        })
    mine = home("Vivus / 3", owner, TOKEN)
    foreign = home("Other flat", other, "otherflattok0344")
    for apt in (mine, foreign):
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt,)))
    yield {"home": mine, "foreign": foreign, "client": TestClient(app)}


def _cards(apt_id):
    return {r["kind"]: r for r in guest_guide.items(apt_id)}


def _go_live(apt_id, **fields):
    """Fill every must-have card so the guide is live; extra kinds get the given fields."""
    cards = _cards(apt_id)
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apt_id, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    for kind, values in fields.items():
        guest_guide.save(apt_id, cards[kind]["id"], values)
    assert guest_guide.progress(apt_id)["live"]
    return _cards(apt_id)


def _stay(apt_id, start_in_days, nights=2):
    start = claim.prague_today() + timedelta(days=start_in_days)
    return db.insert("reservation", {
        "apartment_id": apt_id, "uid": f"g0344-{start_in_days}", "source": "airbnb", "status": "active",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=nights)).isoformat(),
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def _qr(ws):
    return guide_token.ensure(ws["home"])


HARDENED = {"cache-control": "no-store", "x-robots-tag": "noindex, nofollow", "referrer-policy": "no-referrer"}


def _assert_hardened(response):
    for name, value in HARDENED.items():
        assert response.headers.get(name) == value, (name, response.headers.get(name))


# --- the QR token ------------------------------------------------------------

def test_the_token_is_long_random_created_once_and_rotates(ws):
    first = guide_token.ensure(ws["home"])
    assert len(first) >= 32 and first == guide_token.ensure(ws["home"])
    second = guide_token.rotate(ws["home"])
    assert second != first and guide_token.current(ws["home"]) == second
    assert guide_token.apartment_for(first) is None
    assert guide_token.apartment_for(second)["id"] == ws["home"]
    assert guide_token.apartment_for("") is None and guide_token.apartment_for("x" * 65) is None


def test_opening_the_host_guide_page_creates_the_token(ws):
    assert guide_token.current(ws["home"]) is None
    client = ws["client"]
    assert login_as(client, "view-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    assert client.get(f"/apartments/{ws['home']}/guide").status_code == 200
    assert guide_token.current(ws["home"])


def test_unknown_and_rotated_tokens_are_a_plain_404(ws):
    client = ws["client"]
    old = _qr(ws)
    _go_live(ws["home"])
    assert client.get(f"/g/{old}").status_code == 200
    guide_token.rotate(ws["home"])
    for token in (old, "nonsense", "a" * 100, TOKEN):
        response = client.get(f"/g/{token}?lang=en")
        assert response.status_code == 404, token
        assert "Vivus" not in response.text and "guide_" not in response.text
        _assert_hardened(response)
    assert client.get(f"/g/{old}/photos/1/1").status_code == 404


def test_a_guide_that_is_not_live_shows_the_not_ready_page(ws):
    response = ws["client"].get(f"/g/{_qr(ws)}?lang=en")
    assert response.status_code == 200
    assert "data-guide-not-ready" in response.text
    assert "This guide is not ready yet" in response.text
    assert "data-guide-card" not in response.text
    _assert_hardened(response)
    czech = ws["client"].get(f"/g/{_qr(ws)}?lang=cs")
    assert "Tento průvodce ještě není hotový" in czech.text


# --- what each level sees -------------------------------------------------------

def _seed_levels(ws):
    cards = _go_live(
        ws["home"],
        wifi={"location": "Hall cupboard", "steps": "Open the cupboard\nRead the sticker", "watch_out": "Do not unplug the router", "video_url": "https://example.test/wifi"},
        keys={"steps": "Spare key in box 7", "visibility": "booked"},
        trash={"steps": "Bins are in the yard", "visibility": "host"},
        hot_water={"steps": "Fill the tank"},
    )
    db.update("guide_item", cards["hot_water"]["id"], {"state": "check"})  # a draft
    guest_guide.skip(ws["home"], cards["house_rules"]["id"])
    return _cards(ws["home"])


def test_the_qr_page_shows_everyone_cards_only(ws):
    _seed_levels(ws)
    response = ws["client"].get(f"/g/{_qr(ws)}?lang=en")
    assert response.status_code == 200
    body = response.text
    _assert_hardened(response)
    assert "Wi-Fi" in body and "Hall cupboard" in body
    assert '<ol class="g-guide-steps">' in body and "<li>Read the sticker</li>" in body
    assert 'class="g-guide-warn"' in body and "Do not unplug the router" in body
    assert 'href="https://example.test/wifi"' in body
    for hidden in ("Spare key in box 7", "Bins are in the yard", "Fill the tank", "House rules"):
        assert hidden not in body, hidden
    assert "data-guide-window-note" not in body
    assert "guide_" not in body  # every key has copy
    assert f"/l/{TOKEN}" not in body  # the stay link token never leaks onto the public page
    # Must-have topics come in TOPICS order: arrival before wifi before heating.
    assert body.index("Arrival") < body.index("Wi-Fi") < body.index("Heating")


def test_the_czech_qr_page_is_czech(ws):
    _seed_levels(ws)
    body = ws["client"].get(f"/g/{_qr(ws)}?lang=cs").text
    assert "<h1>Váš průvodce</h1>" in body and "Příjezd" in body and "Pozor:" in body and "Nic o vás se tu neukládá." in body


def test_booked_level_window_edges():
    today = claim.prague_today()

    def stay(start, nights=2):
        s = today + timedelta(days=start)
        return {"date_from": s.isoformat(), "date_to": (s + timedelta(days=nights)).isoformat()}
    assert booked_level(stay(2), today) == "everyone"
    assert booked_level(stay(1), today) == "booked"  # the day before check-in
    assert booked_level(stay(0), today) == "booked"
    assert booked_level(stay(-2), today) == "booked"  # checkout day
    assert booked_level(stay(-3), today) == "everyone"  # checked out yesterday
    assert booked_level({"date_from": "", "date_to": None}, today) == "everyone"


@pytest.mark.parametrize("start_in_days,level", [(2, "everyone"), (1, "booked"), (-1, "booked"), (-2, "booked"), (-3, "everyone")])
def test_the_stay_door_follows_the_window(ws, start_in_days, level):
    _seed_levels(ws)
    reservation_id = _stay(ws["home"], start_in_days)
    response = ws["client"].get(f"/l/{TOKEN}/{reservation_id}/guide?lang=en")
    assert response.status_code == 200, response.text[:300]
    body = response.text
    _assert_hardened(response)
    assert "Hall cupboard" in body
    assert ("Spare key in box 7" in body) == (level == "booked")
    assert ("data-guide-window-note" in body) == (level == "everyone")
    for hidden in ("Bins are in the yard", "Fill the tank"):
        assert hidden not in body


def test_the_stay_door_keeps_the_stay_page_checks(ws):
    _seed_levels(ws)
    reservation_id = _stay(ws["home"], 0)
    client = ws["client"]
    assert client.get(f"/l/{TOKEN}/{reservation_id + 100}/guide").status_code == 404
    assert client.get(f"/l/wrongtoken/{reservation_id}/guide").status_code == 404
    foreign_stay = _stay(ws["foreign"], 0)
    assert client.get(f"/l/{TOKEN}/{foreign_stay}/guide").status_code == 404
    db.update("reservation", reservation_id, {"status": "cancelled"})
    assert client.get(f"/l/{TOKEN}/{reservation_id}/guide").status_code == 404


def test_the_stay_door_says_not_ready_until_live(ws):
    reservation_id = _stay(ws["home"], 0)
    response = ws["client"].get(f"/l/{TOKEN}/{reservation_id}/guide?lang=en")
    assert response.status_code == 200 and "data-guide-not-ready" in response.text


def test_the_stay_page_links_to_the_guide():
    stay = (TEMPLATES / "stay.html").read_text(encoding="utf-8")
    assert 'href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}"' in stay
    assert "t('guide_title')" in stay


# --- photos --------------------------------------------------------------------

def _photos(ws):
    cards = _seed_levels(ws)
    wifi = guide_photos.add(ws["home"], cards["wifi"]["id"], _jpeg(), "image/jpeg")
    keys_photo = guide_photos.add(ws["home"], cards["keys"]["id"], _jpeg(), "image/jpeg")
    return cards, wifi, keys_photo


def test_photos_follow_the_card_level_on_both_doors(ws):
    cards, wifi, keys_photo = _photos(ws)
    client = ws["client"]
    qr = _qr(ws)
    page = client.get(f"/g/{qr}")
    assert f"/g/{qr}/photos/{cards['wifi']['id']}/{wifi}" in page.text
    shown = client.get(f"/g/{qr}/photos/{cards['wifi']['id']}/{wifi}")
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/jpeg"
    assert shown.headers["cache-control"] == "private, max-age=3600"
    assert shown.headers["x-robots-tag"] == "noindex" and shown.headers["referrer-policy"] == "no-referrer"
    # A booked card's photo: never through the QR door.
    assert client.get(f"/g/{qr}/photos/{cards['keys']['id']}/{keys_photo}").status_code == 404
    # The photo id alone is not enough: it must sit on the card named in the URL.
    assert client.get(f"/g/{qr}/photos/{cards['wifi']['id']}/{keys_photo}").status_code == 404
    assert client.get(f"/g/{qr}/photos/{cards['heating']['id']}/{wifi}").status_code == 404
    # The stay door: booked photo inside the window, not outside it.
    inside = _stay(ws["home"], 0)
    outside = _stay(ws["home"], 5)
    assert client.get(f"/l/{TOKEN}/{inside}/guide/photos/{cards['keys']['id']}/{keys_photo}").status_code == 200
    assert client.get(f"/l/{TOKEN}/{outside}/guide/photos/{cards['keys']['id']}/{keys_photo}").status_code == 404
    assert client.get(f"/l/{TOKEN}/{outside}/guide/photos/{cards['wifi']['id']}/{wifi}").status_code == 200


def test_a_photo_of_another_property_is_not_found(ws):
    cards, wifi, _ = _photos(ws)
    foreign_token = guide_token.ensure(ws["foreign"])
    _go_live(ws["foreign"])
    assert ws["client"].get(f"/g/{foreign_token}/photos/{cards['wifi']['id']}/{wifi}").status_code == 404


# --- rate limit ----------------------------------------------------------------

def test_the_qr_page_is_rate_limited_per_address(ws):
    _go_live(ws["home"])
    client = ws["client"]
    qr = _qr(ws)
    key = rate_limit.client_key(_request_stub(), "guide_qr")  # TestClient's peer address
    for _ in range(QR_MAX_VIEWS):
        rate_limit.record("guide_qr", key)
    response = client.get(f"/g/{qr}?lang=en")
    assert response.status_code == 429
    _assert_hardened(response)
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'guide_qr'", ())
    assert client.get(f"/g/{qr}").status_code == 200


def _request_stub():
    class _Client:
        host = "testclient"

    class _Request:
        client = _Client()
    return _Request()


def test_the_qr_page_shows_the_host_name_but_not_phone_or_email(ws):
    entity = db.insert("legal_entity", {
        "name": "Jana Fiktivni", "contact_email": "jana@example.test", "contact_phone": "+420 600 000 000",
        "created_at": db.utcnow(),
    })
    db.execute("UPDATE apartment SET legal_entity_id = ? WHERE id = ?", (entity, ws["home"]))
    _go_live(ws["home"])
    body = ws["client"].get(f"/g/{_qr(ws)}?lang=en").text
    assert "Jana Fiktivni" in body
    assert "jana@example.test" not in body and "600 000 000" not in body
```

Command: `.venv/bin/python -m pytest tests/test_guest_guide_view.py -q --tb=short 2>&1 | tail -5`. Expected: 19 passed.

### Step 12: `App/tests/test_guest_guide_browser.py` (new)

```python
"""0344: the QR guide page in a real browser at phone width (layout rules and a screenshot).

Reuses the live server, browser and layout checker of test_guest_browser_e2e.
Skipped when Chromium is missing, unless UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import db, guest_guide, guide_token
from tests.test_guest_browser_e2e import LAYOUT_JS, browser, live_server  # noqa: F401

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or Path(__file__).resolve().parents[1] / ".screenshots")
NAME = "Guide browser flat 0344"


def _seed() -> str:
    _cleanup()
    now = db.utcnow()
    apartment_id = db.insert("apartment", {
        "internal_name": NAME, "uby_name": NAME, "permalink_token": "guidebrowsertok0344",
        "automation_mode": "manual", "active": 1, "created_at": now,
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
    cards = {r["kind"]: r for r in guest_guide.items(apartment_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apartment_id, cards[kind]["id"], {"location": "By the door", "steps": "Step one\nStep two", "watch_out": "Mind the step"})
    return guide_token.ensure(apartment_id)


def _cleanup():
    for row in db.query("SELECT id FROM apartment WHERE internal_name = ?", (NAME,)):
        db.execute("DELETE FROM guide_item WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_qr_guide_page_lays_out_on_a_phone(live_server, browser, lang):  # noqa: F811
    token = _seed()
    try:
        context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = context.new_page()
        page.goto(f"{live_server}/g/{token}?lang={lang}")
        assert page.locator("[data-guide-card]").count() == len(guest_guide.MUST_HAVE)
        problems = page.evaluate(LAYOUT_JS)
        assert not problems, problems
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"0344-guide-qr-{lang}-390.png"), full_page=True)
        context.close()
    finally:
        _cleanup()
```

Command: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_guide_browser.py -q --tb=short 2>&1 | tail -5`. Expected: 2 passed, and `App/.screenshots/0294-guide-qr-en-390.png` and `-cs-` exist (`.screenshots/` is git-ignored; attach them to the report).

## 5. Do not touch

`App/app/guest_guide.py`, `App/app/guide_photos.py`, `App/app/routes/guest.py`, `App/app/host_i18n.py`, `App/app/db.py`, migrations 0001 to 0013, `guest/stay.html` beyond step 8, any host template or CSS. No new dependency. Never log a token, a reservation id or page content. Hard rules 2, 3, 5, 6, 7 and 8 of AGENTS.md apply.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_guide_view.py tests/test_guest_guide.py tests/test_guest_guide_pages.py tests/test_guide_photos.py tests/test_guest_languages.py tests/test_guest_css_tokens.py tests/test_migrations.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short 2>&1 | tail -5`. Expected: 143 passed.
- `.venv/bin/python -m pytest tests/test_*_i18n.py -q --tb=short 2>&1 | tail -5`. Expected: 0 failed outside `test_host_i18n.py` (three Vietnamese tests there fail before this brief; say so in the report, do not fix them).
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short 2>&1 | tail -5`. Expected: 435 passed, 0 skipped (about 4 minutes).

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: both OK.

## 7. Acceptance

- [ ] Only the fourteen files of §3 change (plus the report and the screenshots).
- [ ] 19 tests in `test_guest_guide_view.py` pass; the guest row passes with 0 skipped; both lints OK.
- [ ] `App/.screenshots/0294-guide-qr-en-390.png` and `0344-guide-qr-cs-390.png` attached to the report, showing cards with numbered steps and the amber watch-out callout.
- [ ] `curl -sI` style check in the report: the QR page answers with `Cache-Control: no-store`, `X-Robots-Tag: noindex, nofollow`, `Referrer-Policy: no-referrer` (the test asserts the same).

## 8. Stop and ask

Stop, and write the report, if: 0343 is not merged; a migration `0014_*.sql` already exists; an anchor in steps 4, 5, 6, 8, 9 or 10 is not found exactly once; a test fails twice; the browser test skips; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0344-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `routes/guest_guide_view.py::_stay_gate`: must match `stay_overview` in `routes/guest.py` check for check (link, PIN, reservation, access open, claim and device). A missing check opens booked cards to a stranger with a reservation id.
- `_photo`: the card id must be in `for_guest(level)` before the photo is looked up; the photo must belong to that card and property (`guide_photos.get` joins both). Tests cover a booked photo on the QR door, a swapped card id, a foreign property.
- `qr_guide`: `privacy_url=None` and `token=""` so the stay token never appears on the public page (asserted by `test_the_qr_page_shows_everyone_cards_only`).
- `guide_token.apartment_for`: exact match, active and not archived; `ensure` never overwrites.
- Migration 0014: one column, one partial unique index, no SQLite-only syntax.

## Owner steps

1. Review and merge once CI is green.
2. After deploy, open one property's "Guest guide" page once: that creates its QR token. The printable QR sheet and the "new QR code" button come with 0345; until then the link is `/g/<guide_token>` from the database.
3. The QR page shows only the host's name in the "Your host" box (owner, 2026-10-24: guests have the contact on Booking.com or Airbnb); phone and e-mail stay on the stay page.
