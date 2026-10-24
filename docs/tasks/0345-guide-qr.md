# 0295: QR code for guests (print and new link)

Status: todo
Depends on: 0344 merged | Base commit: after 0344 | Branch: task/0295-guide-qr
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give the host a "QR code for guests" page per property: the code on screen, the guest link, a print-sized PNG download, a button to open the guest page, and "Make a new link" that rotates the token so every printed code stops working ([plan](../plans/guest-guide.md)).

## 2. Context

- 0344 added `App/app/guide_token.py` (`ensure`, `rotate`, `current`, `apartment_for`) and the public page `/g/{token}`. This brief only adds the host side.
- `payments.qr_data_uri(payload)` already renders a small QR PNG as a data URI (used on stay fees); the page reuses it. `qrcode[pil]` is already a dependency.
- The QR routes are declared before `/apartments/{apartment_id}/guide/{item_id}`, so `qr` is never parsed as an item id.
- Rotating is safe for stay links: the QR token is separate from the stay link token.
- Owner decision (2026-10-24): the public QR page shows the host's name only; guests have the contact on Booking.com or Airbnb.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/guide_token.py` | edit | Imports and `qr_png` |
| `App/app/routes/guest_guide.py` | replace | Adds the three QR routes |
| `App/app/templates/guest_guide_qr.html` | create | The QR page |
| `App/app/templates/guest_guide.html` | edit | One secondary action |
| `App/app/host_i18n.py` | edit | `_GUIDE_QR_STRINGS` |
| `docs/design/catalog.json` | edit | One `enforced_templates` entry |
| `App/tests/test_design_guardrails_browser.py` | edit | One route |
| `App/tests/test_guide_qr.py` | create | Tests |

No other file may change.

## 4. Steps

1. Check 0344 is in: `ls App/app/guide_token.py App/app/routes/guest_guide_view.py 2>&1 | tail -30`. If either is missing, STOP (§8).

2. In `App/app/guide_token.py`, replace the import block

```python
import secrets
from typing import Any, Dict, Optional

from . import db
```

with

```python
import io
import secrets
from typing import Any, Dict, Optional

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from . import db
```

and append at the end of the file:

```python

def qr_png(url: str) -> bytes:
    """A print-sized PNG of the QR code (brief 0345): about 6 cm at 300 dpi."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=20, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    out = io.BytesIO()
    qr.make_image().save(out, format="PNG")
    return out.getvalue()
```

3. Replace the whole content of `App/app/routes/guest_guide.py` with:

```python
"""0292: the host's guest guide pages: the card list and one card's editor.

The data and every rule about it live in ``app.guest_guide``; these routes only
check the property belongs to the host, call it, and redirect.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from .. import access, auth, config, guest_guide, guide_photos, guide_token, payments, security, templating
from .admin_helpers import back, flash

router = APIRouter(dependencies=[Depends(security.protect_host_post)])
PRIVATE = {"Cache-Control": "no-store"}


def _home(request: Request, apartment_id: int) -> Dict[str, Any]:
    row = access.apartment(request, apartment_id)
    if not row or row["archived_at"]:
        raise HTTPException(404)
    return dict(row)


def _base(apartment_id: int) -> str:
    return f"/apartments/{apartment_id}/guide"


def _render(request: Request, name: str, status_code: int = 200, **values):
    context = {"nav": "apartments", "visibility": guest_guide.VISIBILITY, **values}
    response = templating.render(request, name, context, status_code=status_code)
    response.headers.update(PRIVATE)
    return response


def _card(request: Request, apartment, item, values, error: str = "", status_code: int = 200):
    return _render(
        request, "guest_guide_card.html", status_code=status_code,
        apartment=apartment, item=item, values=values, error=error,
        photos=guide_photos.photos(apartment["id"], item["id"]),
        max_photos=guide_photos.MAX_PER_ITEM,
    )


def _next_open(apartment_id: int, after_id: int) -> Optional[int]:
    """The next card in guest order that still needs the host, wrapping around."""
    rows = guest_guide.items(apartment_id)
    ids = [r["id"] for r in rows]
    start = ids.index(after_id) + 1 if after_id in ids else 0
    for row in rows[start:] + rows[:start]:
        if row["id"] != after_id and row["state"] in ("missing", "check"):
            return row["id"]
    return None


@router.get("/apartments/{apartment_id}/guide")
def guide_index(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    guest_guide.ensure_defaults(apartment)
    guide_token.ensure(apartment_id)
    rows = guest_guide.items(apartment_id)
    groups = [(topic, [r for r in rows if r["topic"] == topic]) for topic in guest_guide.TOPICS]
    return _render(
        request,
        "guest_guide.html",
        apartment=apartment,
        groups=[(topic, cards) for topic, cards in groups if cards],
        topics=guest_guide.TOPICS,
        must_have=guest_guide.MUST_HAVE,
        progress=guest_guide.progress(apartment_id),
        next_id=_next_open(apartment_id, 0),
    )


@router.post("/apartments/{apartment_id}/guide/cards")
async def guide_add(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        item_id = guest_guide.add_custom(apartment_id, str(form.get("topic", "")), str(form.get("title", "")))
    except guest_guide.GuideError as exc:
        return back(_base(apartment_id), err=flash(request, exc.key))
    return back(f"{_base(apartment_id)}/{item_id}")


def _guest_url(apartment_id: int) -> str:
    return f"{config.PUBLIC_BASE_URL}/g/{guide_token.ensure(apartment_id)}"


@router.get("/apartments/{apartment_id}/guide/qr")
def guide_qr(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    url = _guest_url(apartment_id)
    return _render(
        request, "guest_guide_qr.html", apartment=apartment, guest_url=url,
        qr=payments.qr_data_uri(url), progress=guest_guide.progress(apartment_id),
    )


@router.get("/apartments/{apartment_id}/guide/qr.png")
def guide_qr_png(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    return Response(
        guide_token.qr_png(_guest_url(apartment_id)),
        media_type="image/png",
        headers={**PRIVATE, "Content-Disposition": 'attachment; filename="guest-guide-qr.png"'},
    )


@router.post("/apartments/{apartment_id}/guide/qr/rotate")
def guide_qr_rotate(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    guide_token.rotate(apartment_id)
    return back(f"{_base(apartment_id)}/qr", msg=flash(request, "flash.guest_guide.qr_rotated"))


@router.get("/apartments/{apartment_id}/guide/{item_id}")
def guide_card(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item:
        raise HTTPException(404)
    return _card(request, apartment, item, item)


@router.post("/apartments/{apartment_id}/guide/{item_id}")
async def guide_card_save(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item:
        raise HTTPException(404)
    form = await request.form()
    fields = {name: form.get(name, "") for name in guest_guide.LIMITS if name in form}
    fields["visibility"] = form.get("visibility", item["visibility"])
    try:
        guest_guide.save(apartment_id, item_id, fields)
    except guest_guide.GuideError as exc:
        values = {**item, **{k: str(v) for k, v in fields.items()}}
        return _card(request, apartment, item, values, error=exc.key, status_code=422)
    if form.get("then") == "next":
        next_id = _next_open(apartment_id, item_id)
        if next_id:
            return back(f"{_base(apartment_id)}/{next_id}", msg=flash(request, "flash.guest_guide.saved"))
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.saved"))


@router.post("/apartments/{apartment_id}/guide/{item_id}/skip")
async def guide_card_skip(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        guest_guide.skip(apartment_id, item_id, skipped=form.get("skip") == "1")
    except guest_guide.GuideError:
        raise HTTPException(404) from None
    return back(_base(apartment_id))


@router.post("/apartments/{apartment_id}/guide/{item_id}/delete")
def guide_card_delete(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item or item["kind"] != "custom":
        raise HTTPException(404)
    for photo in guide_photos.photos(apartment_id, item_id):
        guide_photos.delete(apartment_id, item_id, photo["id"])
    guest_guide.delete_custom(apartment_id, item_id)
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.deleted"))


@router.post("/apartments/{apartment_id}/guide/{item_id}/photos")
async def guide_photo_add(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guest_guide.get(apartment_id, item_id):
        raise HTTPException(404)
    card_url = f"{_base(apartment_id)}/{item_id}"
    form = await request.form()
    upload = form.get("photo")
    if upload is None or not hasattr(upload, "read"):
        return back(card_url, err=flash(request, "flash.error.guide_photo_type"))
    content = await upload.read(guide_photos.MAX_UPLOAD_BYTES + 1)
    try:
        # Decoding and shrinking a phone photo is CPU work; keep it off the event loop.
        await run_in_threadpool(guide_photos.add, apartment_id, item_id, content, upload.content_type or "")
    except guest_guide.GuideError as exc:
        return back(card_url, err=flash(request, exc.key))
    return back(card_url, msg=flash(request, "flash.guest_guide.photo_added"))


@router.get("/apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}")
def guide_photo_file(request: Request, apartment_id: int, item_id: int, photo_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    photo = guide_photos.get(apartment_id, item_id, photo_id)
    path = guide_photos.path_for(photo) if photo else None
    if not path or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}/delete")
def guide_photo_delete(request: Request, apartment_id: int, item_id: int, photo_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guide_photos.delete(apartment_id, item_id, photo_id):
        raise HTTPException(404)
    return back(f"{_base(apartment_id)}/{item_id}", msg=flash(request, "flash.guest_guide.photo_deleted"))
```

4. Create `App/app/templates/guest_guide_qr.html`:

```html
{#- 0295: the guide's QR code for the host to print. The code opens /g/<token>,
    the public "everyone" cards only. A new link makes every printed code stop. -#}
{% extends "host_page.html" %}
{% set body_kind = 'form' %}
{% set base_url = '/apartments/' ~ apartment.id ~ '/guide' %}
{% block title %}{{ t('guest_guide.qr.title') }} · {{ apartment.internal_name }} · UbyHost{% endblock %}
{% block page_title %}{{ t('guest_guide.qr.title') }}{% endblock %}
{% block back_url %}{{ base_url }}{% endblock %}
{% block back_label %}{{ t('guest_guide.title') }}{% endblock %}
{% block meta %}{{ t('guest_guide.qr.meta') }}{% endblock %}
{% block body %}
{% if not progress.live %}{{ ui_banner('attention', t('guest_guide.qr.not_live')) }}{% endif %}
{% call ui_section(apartment.internal_name, id='qr-code') %}
<img src="{{ qr }}" width="240" height="240" alt="{{ t('guest_guide.qr.alt') }}">
<p class="ui-help">{{ t('guest_guide.qr.print_help') }}</p>
<p class="ui-mono">{{ guest_url }}</p>
<div class="ui-form-actions">
{{ ui_button(t('guest_guide.qr.download'), 'primary', href=base_url ~ '/qr.png', icon_name='download') }}
{{ ui_button(t('guest_guide.qr.open'), 'secondary', href=guest_url, icon_name='external-link', attrs='target="_blank" rel="noopener"') }}
</div>
{% endcall %}
{% call ui_section(t('guest_guide.qr.rotate_title'), id='qr-rotate') %}
<p class="ui-help">{{ t('guest_guide.qr.rotate_help') }}</p>
<form method="post" action="{{ base_url }}/qr/rotate" data-confirm data-confirm-message="{{ t('guest_guide.qr.rotate_confirm') }}">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_button(t('guest_guide.qr.rotate'), 'danger', type='submit', icon_name='refresh-cw') }}
</form>
{% endcall %}
{% endblock %}
```

5. In `App/app/templates/guest_guide.html`, directly before the line that starts with `{% block primary_action %}`, add:

```html
{% block secondary_actions %}{{ ui_button(t('guest_guide.qr.link'), 'secondary', href=base_url ~ '/qr') }}{% endblock %}
```

6. In `App/app/host_i18n.py`, find (once):

```python
for _lang, _strings in _GUIDE_PHOTO_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Directly after them, insert one blank line and:

```python
# 0295: the guide's QR code for the host to print.
_GUIDE_QR_STRINGS = {
    "en": {
        "guest_guide.qr.link": "QR code for guests",
        "guest_guide.qr.title": "QR code for guests",
        "guest_guide.qr.meta": "Anyone who scans it sees the cards marked Everyone with the QR code. Booked guests see more on their stay link.",
        "guest_guide.qr.not_live": "Until the must-have cards are done, the code opens a page that says the guide is not ready yet. You can print it now.",
        "guest_guide.qr.alt": "QR code that opens the guest guide",
        "guest_guide.qr.print_help": "Print it at least 5 cm wide and put it where guests look first: inside the front door or on the fridge.",
        "guest_guide.qr.download": "Download for printing",
        "guest_guide.qr.open": "Open the guest page",
        "guest_guide.qr.rotate_title": "New link",
        "guest_guide.qr.rotate_help": "Use this if the code is somewhere it should not be, for example in an old listing photo. Every printed code stops working at once, so print the new one straight away.",
        "guest_guide.qr.rotate": "Make a new link",
        "guest_guide.qr.rotate_confirm": "Every printed code for this property stops working now. Make a new link?",
        "flash.guest_guide.qr_rotated": "New link made. Print the new code; the old one no longer works.",
    },
    "cs": {
        "guest_guide.qr.link": "QR kód pro hosty",
        "guest_guide.qr.title": "QR kód pro hosty",
        "guest_guide.qr.meta": "Kdo ho naskenuje, uvidí karty označené Každý s QR kódem. Hosté s rezervací uvidí víc přes odkaz na pobyt.",
        "guest_guide.qr.not_live": "Dokud nebudou hotové povinné karty, kód otevře stránku, že průvodce ještě není připravený. Vytisknout ho můžete už teď.",
        "guest_guide.qr.alt": "QR kód, který otevře průvodce pro hosty",
        "guest_guide.qr.print_help": "Vytiskněte ho aspoň 5 cm široký a dejte ho tam, kam se hosté podívají nejdřív: na vnitřní stranu vchodových dveří nebo na lednici.",
        "guest_guide.qr.download": "Stáhnout pro tisk",
        "guest_guide.qr.open": "Otevřít stránku pro hosty",
        "guest_guide.qr.rotate_title": "Nový odkaz",
        "guest_guide.qr.rotate_help": "Použijte, pokud je kód někde, kde být nemá, třeba na staré fotce z inzerátu. Všechny vytištěné kódy hned přestanou fungovat, tak nový hned vytiskněte.",
        "guest_guide.qr.rotate": "Vytvořit nový odkaz",
        "guest_guide.qr.rotate_confirm": "Všechny vytištěné kódy pro toto ubytování teď přestanou fungovat. Vytvořit nový odkaz?",
        "flash.guest_guide.qr_rotated": "Nový odkaz je hotový. Vytiskněte nový kód, starý už nefunguje.",
    },
}

for _lang, _strings in _GUIDE_QR_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

7. In `docs/design/catalog.json`, append `"App/app/templates/guest_guide_qr.html"` to the end of `enforced_templates`.

8. In `App/tests/test_design_guardrails_browser.py`, after the line `    "guest-guide": "/apartments/{property_id}/guide",` add:

```python
    "guest-guide-qr": "/apartments/{property_id}/guide/qr",
```

9. Create `App/tests/test_guide_qr.py`:

```python
"""0295: the guide's QR code for the host."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, config, db, guide_token
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "qr.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("qr-owner@example.test", "QR owner", username="qr-owner", role="host")
    other = auth.create_account("qr-other@example.test", "Other owner", username="qr-other", role="host")
    now = db.utcnow()

    def home(name, user):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "qr-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def test_qr_page_shows_the_code_and_the_guest_link(ws):
    response = ws["client"].get(f"/apartments/{ws['home']}/guide/qr")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    token = guide_token.current(ws["home"])
    assert token
    assert f"{config.PUBLIC_BASE_URL}/g/{token}" in response.text
    assert 'src="data:image/png;base64,' in response.text
    assert "not ready yet" in response.text  # guide not live
    assert "guest_guide." not in response.text


def test_guide_page_links_to_the_qr_page(ws):
    body = ws["client"].get(f"/apartments/{ws['home']}/guide").text
    assert f'href="/apartments/{ws["home"]}/guide/qr"' in body


def test_png_download_is_a_print_sized_image(ws):
    response = ws["client"].get(f"/apartments/{ws['home']}/guide/qr.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "attachment" in response.headers["content-disposition"]
    with Image.open(io.BytesIO(response.content)) as image:
        assert min(image.size) >= 600


def test_new_link_stops_the_old_code(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide/qr")
    old = guide_token.current(ws["home"])
    response = client.post(f"/apartments/{ws['home']}/guide/qr/rotate", follow_redirects=False)
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    new = guide_token.current(ws["home"])
    assert new and new != old
    assert client.get(f"/g/{old}").status_code == 404
    assert client.get(f"/g/{new}").status_code == 200


def test_another_hosts_property_is_out_of_reach(ws):
    client = ws["client"]
    assert client.get(f"/apartments/{ws['foreign']}/guide/qr").status_code == 404
    assert client.get(f"/apartments/{ws['foreign']}/guide/qr.png").status_code == 404
    assert client.post(f"/apartments/{ws['foreign']}/guide/qr/rotate").status_code == 404
    assert guide_token.current(ws["foreign"]) is None


def test_czech_qr_page(ws):
    body = ws["client"].get(f"/apartments/{ws['home']}/guide/qr?lang=cs").text
    assert "QR kód pro hosty" in body and "Stáhnout pro tisk" in body
```

## 5. Do not touch

`App/app/guide_token.py` functions other than the import block and the new `qr_png`; `routes/guest_guide_view.py`; `payments.py`; guest templates; CSS. No new dependency.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guide_qr.py tests/test_guest_guide_pages.py tests/test_guest_guide_view.py tests/test_guide_photos.py tests/test_guest_guide.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.
- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -k every_host_page 2>&1 | tail -30`. Expected: 1 passed (or say Chromium was missing).

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: both OK.

## 7. Acceptance

- [ ] Only the eight files of §3 change (plus the report).
- [ ] `test_guide_qr.py`: 6 passed; the other rows pass.
- [ ] Both lints OK.

## 8. Stop and ask

Stop, and write the report, if: 0344 is not merged; an anchor in steps 2, 5, 6 or 8 is not found exactly once; a test fails twice; the design lint names a class; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0295-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `guide_qr_rotate`: ownership via `_home` before `rotate`; the test covers a foreign property.
- Route order: the QR routes must stay above `/guide/{item_id}`.

## Owner steps

1. Review and merge once CI is green.
2. After deploy, open a property, Guest guide, "QR code for guests", download, print at least 5 cm wide, and stick it inside the front door.
3. `UBYHOST_PUBLIC_BASE_URL` must be the real public address, or the printed code points to the wrong host. It is already set in production.

